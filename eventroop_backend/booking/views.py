from venue_manager.models import Venue, Service, Resource
from venue_manager.serializers import VenueSerializer, ServiceSerializer
from rest_framework import viewsets, permissions, status
from .serializers import *
from .models import *
from .filters import EntityFilter
from django.db.models import Q, Sum, Count,Prefetch
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from dateutil import parser

class PublicVenueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Single API for:
      - GET /venues/          → list venues with filters
      - GET /venues/<id>/     → venue details
    """
    serializer_class = VenueSerializer
    permission_classes = [permissions.AllowAny]
    
    lookup_field = "pk"
    queryset = Venue.objects.filter(is_deleted=False, is_active=True).order_by("id")

    filterset_fields = {
        "location__city": ["iexact", "icontains"],
        "location__state": ["iexact", "icontains"],
        "capacity": ["gte", "lte", "exact"],
        "price_per_event": ["gte", "lte"],
        "rooms": ["gte", "lte"],
        "floors": ["gte", "lte"],
        "external_decorators_allow": ["iexact"],
        "external_caterers_allow": ["iexact"],
    }

    search_fields = [
        "name",
        "description",
        "location__building_name",
        "location__address_line1",
        "location__address_line2",
        "location__locality",
        "location__city",
        "location__state",
    ]

class PublicServiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Single API for:
      - GET /services/          → list services with filters
      - GET /services/<id>/     → service details
    """
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]
    
    filterset_class = EntityFilter
    lookup_field = "pk"

    queryset = Service.objects.filter(is_deleted=False, is_active=True).order_by("id")

    filterset_fields = {
        "city": ["iexact", "icontains"],
    }

    search_fields = [
        "venue__name",
        "name",
        "description",
        "address",
        "city",
        "contact",
        "website",
        "tags",
        "quick_info"
    ]

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Patient.objects.all()
            
        # Owner → return all patient data
        if user.is_owner:
            return Patient.objects.filter(
                Q(registered_by__hierarchy__owner=user) |
                Q(registered_by=user)
            )

        # Manager/Staff/customer → only their own patients
        return Patient.objects.filter(registered_by=user)

    def perform_create(self, serializer):
        """
        Set registered_by = request.user automatically
        """
        serializer.save(registered_by=self.request.user)

class LocationViewSet(viewsets.ModelViewSet):
    serializer_class = LocationSerializer

    filterset_fields = ["location_type","user__first_name","user__email","user__mobile_number", "city", "state"]
    search_fields = [
        "user__first_name",
        "user__email",
        "user__mobile_number",
        "building_name",
        "address_line1",
        "locality",
        "city",
        "state",
        "postal_code",
    ]
    
    def get_queryset(self):
        user = self.request.user

        # Admin → see all locations
        if user.is_superuser:
            qs = Location.objects.all()
        else:
            qs = Location.objects.filter(user=user)

        return qs.order_by("-id")
    
    def perform_create(self, serializer):
        # Automatically set the user to the requesting user
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        # Ensure user cannot be changed on update
        serializer.save(user=self.request.user)

class PackageViewSet(viewsets.ModelViewSet):
    queryset = Package.objects.all()
    serializer_class = PackageSerializer
    filterset_fields = ['package_type', 'is_active', 'owner', 'content_type__model']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'price', 'name']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return PackageListSerializer
        return PackageSerializer

    def get_queryset(self):
        user = self.request.user
        # Owners can only see their own packages, staff can see all
        if user.is_superuser:
            return Package.objects.all()
        elif user.is_owner:
            return Package.objects.filter(owner=user)
        elif user.is_vsre_staff:
            return Package.objects.filter(owner=user.hierarchy.owner)
        return Package.objects.none()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        if not self.request.user.is_owner:
            return Response(
                {'detail': 'You do not have permission to update this package.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_owner:
            return Response(
                {'detail': 'You do not have permission to delete this package.'},
                status=status.HTTP_403_FORBIDDEN
            )
        instance.delete()

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Filter packages by type"""
        pkg_type = request.query_params.get('type')
        if not pkg_type:
            return Response(
                {'error': 'type parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        packages = self.get_queryset().filter(package_type=pkg_type)
        serializer = self.get_serializer(packages, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_belongs_to(self, request):
        """
        Examples:

        /booking/packages/by_belongs_to/?entity=venue
            -> returns all venues (id, name)

        /booking/packages/by_belongs_to/?entity=venue&id=3
            -> returns packages of venue 3
        """

        content_type_name = request.query_params.get("entity")
        object_id = request.query_params.get("id")

        if not content_type_name:
            return Response(
                {"error": "content_type is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ENTITY_MAP = {
            "venue": Venue,
            "service": Service,
            "resource": Resource,
        }

        content_type_name = content_type_name.lower()

        if content_type_name not in ENTITY_MAP:
            return Response(
                {"error": "content_type must be venue, service, or resource"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Model = ENTITY_MAP[content_type_name]

        # ==================================================
        # CASE 1 → Only content_type → return entities
        # ==================================================
        if not object_id:
            queryset = Model.objects.filter(owner=request.user, is_active=True)

            data = queryset.values("id", "name")

            return Response(data)

        # ==================================================
        # CASE 2 → content_type + object_id → return packages
        # ==================================================
        try:
            obj = Model.objects.get(
                id=object_id,
                owner=request.user,
                is_active=True,
            )
        except Model.DoesNotExist:
            return Response(
                {"error": f"{content_type_name.title()} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ⭐ GenericRelation
        packages = obj.packages.all()

        serializer = PackageListSerializer(packages, many=True)
        return Response(serializer.data)

class InvoiceBookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing invoice bookings.
    
    Handles:
    - Creating venue bookings with nested services
    - Creating standalone service bookings
    - Managing parent-child booking relationships
    - Cancelling bookings with cascading updates
    """


    search_fields = ['patient__first_name','patient__last_name', 'booking_entity', 'status']  
    filterset_fields = {
        'start_datetime': ['month'],
        'end_datetime': ['month'],
        'booking_type': ['exact'],
        'status': ['exact'],
    }

    ordering_fields = ['user','patient','created_at', 'start_datetime', 'end_datetime']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get bookings filtered by user and optional parameters"""
        user=self.request.user
        queryset = InvoiceBooking.objects.filter(
            parent__isnull=True
        ).select_related(
            'patient',
            'venue',
            'service',
            'package',
            'parent'
        ).prefetch_related('children')

        if user.is_customer:
            queryset = queryset.filter(user=user)

        ongoing = self.request.query_params.get('ongoing')
        upcoming = self.request.query_params.get('upcoming')
        past_order = self.request.query_params.get('past_order')

        now = timezone.now() 
        if ongoing:
            queryset = queryset.filter(
                start_datetime__lte=now,
                end_datetime__gte=now,
            )
        if upcoming:
            queryset = queryset.filter(start_datetime__gt=now)

        if past_order:
            queryset = queryset.filter(end_datetime__lt=now)
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return InvoiceBookingCreateSerializer
        return InvoiceBookingSerializer
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new booking.
        
        For venue bookings: Creates parent booking that can have child service bookings
        For standalone services: Creates standalone booking
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Automatically set user to current authenticated user
        serializer.validated_data['user'] = request.user
        serializer.validated_data['status'] = BookingStatus.BOOKED
        serializer.validated_data['booking_type'] = BookingType.IN_HOUSE
        serializer.validated_data['booking_entity'] = BookingEntity.VENUE
        
        serializer.save()
        
        return Response({"message":"Booked successfully"}, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def add_service(self, request, pk=None):
        """
        Add a service booking as a child to a venue booking.
        
        Only works for VENUE type parent bookings.
        Payload:
        {
            "service": 5,
            "package": 2,
            "start_datetime": "2026-02-05T10:00:00Z",
            "end_datetime": "2026-02-05T11:00:00Z",
            "discount_amount": "100.00",
            "premium_amount": "50.00"
        }

        """
        
        serializer = ServiceBookingCreateSerializer(
            data=request.data,
            context={
                "parent": self.get_object(),
            },
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message":"Booked successfully"}, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def cancel_venue(self, request, pk=None):
        """
        Cancel a booking and all its child bookings.
        Sets status to CANCELLED and subtotal to 0.
        """
        booking = self.get_object()
        
        if booking.status == 'CANCELLED':
            return Response(
                {'message': 'Booking is already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.cancel()
        
        serializer = InvoiceBookingSerializer(booking)
        return Response(serializer.data)
    @action(detail=True, methods=['post'])
    def cancel_venue(self, request, pk=None):
        """
        Cancel a booking and all its child bookings.
        Sets status to CANCELLED and subtotal to 0.
        """
        booking = self.get_object()
        
        if booking.status == 'CANCELLED':
            return Response(
                {'message': 'Booking is already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.cancel()
        
        serializer = InvoiceBookingSerializer(booking)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel_venue(self, request, pk=None):
        """
        Cancel a booking and all its child bookings.
        Sets status to CANCELLED and subtotal to 0.
        """
        booking = self.get_object()
        
        if booking.status == 'CANCELLED':
            return Response(
                {'message': 'Booking is already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        booking.cancel()
        return Response({'message': 'Booking is cancelled Successfully'})
    
    @action(detail=True, methods=['post'])
    def cancel_service(self, request, pk=None):
        """
        Cancel a booking and all its child bookings.
        Sets status to CANCELLED and subtotal to 0.
        payload:
        {
            "service_id":22
        }
        """
        booking = self.get_object()
        
        if booking.status == 'CANCELLED':
            return Response(
                {'message': 'Booking is already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        child_booking = booking.children.get(id=request.data.get('service_id'))
        child_booking.cancel()
        
        return Response({'message': 'Booking is cancelled Successfully'})
        
    @action(detail=False, methods=['get'])
    def by_venue(self, request):
        """Get all venue bookings grouped with their services"""
        venue_bookings = self.get_queryset().filter(
            booking_entity='VENUE'
        )
        
        serializer = InvoiceBookingSerializer(venue_bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def standalone_services(self, request):
        """Get all standalone service bookings (those without parent)"""
        service_bookings = self.get_queryset().filter(
            booking_entity='SERVICE'
        )
        
        serializer = InvoiceBookingSerializer(service_bookings, many=True)
        return Response(serializer.data)

class TotalInvoiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing invoices.
    
    Handles:
    - Creating invoices from bookings
    - Calculating venue and service portions
    - Managing invoice status and payments
    - Generating invoice numbers
    """
    # pagination_class = None
    serializer_class = TotalInvoiceSerializer
    search_fields = ['invoice_number', 'patient__first_name','patient__last_name', 'status']
    filterset_fields = {
        'period_start': ['month'],
        'period_end': ['month'],
        'booking__booking_type': ['exact'],
        'status': ['exact'],
    }

    ordering_fields = [
        'user',
        'patient',
        'created_at',
        'period_start',
        'period_end',
        'issued_date',
        'status', 'total_amount'
    ]
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get invoices filtered by user"""
        queryset = TotalInvoice.objects.select_related(
            'booking',
            'patient',
            'user'
        ).prefetch_related('payments')

        user = self.request.user
        if user.is_customer:
            queryset = queryset.filter(user=user)
            
        
        # Filter by date range if specified
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(issued_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(issued_date__lte=end_date)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """
        Override list() to return grouped response by user and patient.
        
        Response format:
        [
            {
                "user_id": 2,
                "user_name": "Owner One",
                "patient_id": 16,
                "patient_name": "Shreya Joshi",
                "total_invoice_amount": "31800.00",
                "total_paid": "16000.00",
                "total_balance": "15800.00",
                "invoices": [
                    {
                        "invoice_date": "2026-02-05",
                        "invoice_number": "INV-1B655E2E58",
                        "invoice_amount": "15000.00",
                        "paid": "0.00",
                        "balance": "15000.00",
                        "payment_details": "-"
                    }
                ]
            }
        ]
        """
        queryset = self.filter_queryset(self.get_queryset()).order_by('user_id', 'patient_id')

        page = self.paginate_queryset(queryset)
        if page is not None:
            queryset = page
        
        grouped_data = []

        from itertools import groupby
        for (user_id, patient_id), invoices_group in groupby(
            queryset,
            key=lambda x: (x.user_id, x.patient_id)
        ):
            invoices_list = list(invoices_group)
            
            if not invoices_list:
                continue
            
            # Get user and patient info from first invoice
            first_invoice = invoices_list[0]
            user = first_invoice.user
            patient = first_invoice.patient
            
            # Calculate totals
            total_invoice_amount = sum(
                inv.total_amount for inv in invoices_list
            )
            total_paid = sum(
                inv.paid_amount for inv in invoices_list
            )
            total_balance = total_invoice_amount - total_paid
            
            # Build invoices array
            invoices_array = []
            for invoice in invoices_list:
                # Get payment details
                payments = invoice.payments.all()
                
                payment_details = []
                if payments.exists():
                    PaymentSerializer
                    payment_details = [
                        {
                            'id': str(payment.id),
                            'payment_date': str(payment.created_at),
                            'amount': str(payment.amount),
                            'method': payment.method, 
                            'is_verified': str(payment.is_verified),
                            'reference': payment.reference or '-'
                        }
                        for payment in payments
                    ]
                
                invoices_array.append({
                    'invoice_date': str(invoice.issued_date),
                    'invoice_number': invoice.invoice_number,
                    'invoice_amount': str(invoice.total_amount),
                    'paid': str(invoice.paid_amount),
                    'balance': str(invoice.remaining_amount),
                    'payment_details': payment_details
                })
            
            grouped_data.append({
                'user_id': user.id,
                'user_name': user.get_full_name(),
                'patient_id': patient.id,
                'patient_name': patient.get_full_name(),
                'total_invoice_amount': str(total_invoice_amount),
                'total_paid': str(total_paid),
                'total_balance': str(total_balance),
                'invoices': invoices_array
            })
        
        if page is not None:
            return self.get_paginated_response(grouped_data)

        return Response(grouped_data)
        
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create invoices for a booking.
        
        For VENUE bookings: Creates one invoice covering the venue + all services
        For standalone SERVICE bookings: Creates separate invoice for that service
        """
        booking_id = request.data.get('booking_id')
        period_start = request.data.get('period_start')
        period_end = request.data.get('period_end')
        
        if not all([booking_id, period_start, period_end]):
            return Response(
                {'error': 'booking_id, period_start, and period_end are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            booking = InvoiceBooking.objects.select_related('patient', 'user').get(
                id=booking_id,
                user=request.user
            )
        except InvoiceBooking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        invoices_created = []
        
        # CASE 1: Venue booking - create single invoice for venue + services
        if booking.booking_entity == 'VENUE' and booking.parent is None:
            invoice = TotalInvoice.objects.create(
                booking=booking,
                period_start=period_start,
                period_end=period_end,
                patient=booking.patient,
                user=booking.user
            )
            invoice.recalculate_totals()
            invoices_created.append(invoice)
        
        # CASE 2: Standalone service booking - create separate invoice
        elif booking.booking_entity == 'SERVICE' and booking.parent is None:
            invoice = TotalInvoice.objects.create(
                booking=booking,
                period_start=period_start,
                period_end=period_end,
                patient=booking.patient,
                user=booking.user
            )
            invoice.recalculate_totals()
            invoices_created.append(invoice)
        
        # CASE 3: Child service booking - create invoice for parent (venue)
        elif booking.parent:
            invoice = TotalInvoice.objects.create(
                booking=booking.parent,
                period_start=period_start,
                period_end=period_end,
                patient=booking.patient,
                user=booking.user
            )
            invoice.recalculate_totals()
            invoices_created.append(invoice)
        
        serializer = TotalInvoiceSerializer(invoices_created, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def recalculate(self, request, pk=None):
        """
        Recalculate invoice totals based on current bookings and payments.
        """
        invoice = self.get_object()
        invoice.recalculate_totals()
        
        serializer = TotalInvoiceSerializer(invoice)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_payment(self, request, pk=None):
        """
        Add a payment to an invoice.
        Automatically recalculates invoice status.
        """
        invoice = self.get_object()
        
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        payment = Payment.objects.create(
            invoice=invoice,
            patient=invoice.patient,
            **serializer.validated_data
        )
        
        payment_serializer = PaymentSerializer(payment)
        return Response(payment_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get invoice summary statistics for the current user.
        """
        queryset = self.filter_queryset(self.get_queryset())

        total_stats = queryset.aggregate(
            total_invoices=Count('id'),
            total_amount=Sum('total_amount'),
            paid_amount=Sum('paid_amount'),
            remaining_amount=Sum('remaining_amount')
        )
        
        status_counts = queryset.values('status').annotate(count=Count('id'))
        
        summary_data = {
            'total_invoices': total_stats['total_invoices'] or 0,
            'total_amount': total_stats['total_amount'] or Decimal('0.00'),
            'paid_amount': total_stats['paid_amount'] or Decimal('0.00'),
            'remaining_amount': total_stats['remaining_amount'] or Decimal('0.00'),
            'unpaid_count': 0,
            'partially_paid_count': 0,
            'paid_count': 0
        }
        
        for status_item in status_counts:
            if status_item['status'] == 'UNPAID':
                summary_data['unpaid_count'] = status_item['count']
            elif status_item['status'] == 'PARTIALLY_PAID':
                summary_data['partially_paid_count'] = status_item['count']
            elif status_item['status'] == 'PAID':
                summary_data['paid_count'] = status_item['count']
        
        serializer = InvoiceSummarySerializer(summary_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Get all overdue invoices (due_date has passed and status is not PAID).
        """
        today = timezone.now().date()
        overdue_invoices = self.get_queryset().filter(
            due_date__lt=today,
            status__in=['UNPAID', 'PARTIALLY_PAID']
        )
        
        serializer = self.serializer_class(overdue_invoices, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def payments(self, request, pk=None):
        """
        Get all payments for a specific invoice.
        """
        invoice = self.get_object()
        payments = invoice.payments.all()
        
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)

class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payments.
    
    Handles:
    - Recording payments against invoices
    - Verifying payments
    - Tracking payment methods and references
    """
    filterset_fields = ['invoice_id','is_verified','method']  
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get payments for invoices belonging to current user"""
        queryset = Payment.objects.select_related('invoice', 'patient')
        user=self.request.user
        if user.is_customer:
            queryset = queryset.filter(invoice__user = user)
    
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return PaymentCreateSerializer
        return PaymentSerializer
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a new payment"""
        invoice_id = request.data.get('invoice_id')
        
        try:
            invoice = TotalInvoice.objects.get(
                id=invoice_id,
                user=request.user
            )
        except TotalInvoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        payment = Payment.objects.create(
            invoice=invoice,
            patient=invoice.patient,
            **serializer.validated_data
        )
        
        # Recalculate invoice status after payment
        invoice.recalculate_payments()
        
        output_serializer = PaymentSerializer(payment)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Mark a payment as verified"""
        payment = self.get_object()
        payment.is_verified = True
        payment.save()
        
        # Recalculate invoice payments
        payment.invoice.recalculate_payments()
        
        serializer = PaymentSerializer(payment)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_verification(self, request):
        """Get all payments pending verification"""
        pending_payments = self.get_queryset().filter(is_verified=False)
        
        serializer = PaymentSerializer(pending_payments, many=True)
        return Response(serializer.data)
    