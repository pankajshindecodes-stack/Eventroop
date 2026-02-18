from venue_manager.models import Venue, Service, Resource
from venue_manager.serializers import VenueSerializer, ServiceSerializer
from rest_framework import viewsets, permissions, status
from .serializers import *
from .models import *
from .utils import generate_order_id
from .filters import EntityFilter
from django.db.models import Q, Sum, Count,Prefetch
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.dateparse import parse_datetime
from itertools import groupby
from datetime import datetime, time

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
    
    # Simple filtering
    filterset_fields = [
        "gender",
        "blood_group",
        "payment_mode",
        "registered_by",
        "id_proof",
        "registration_date",
    ]

    # Search 
    search_fields = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "patient_id",
    ]

    # Ordering
    ordering_fields = [
        "registration_date",
        "first_name",
        "age",
        "registration_fee",
    ]

    ordering = ['-registration_date']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_owner:
            return Patient.objects.all()
        
        # Manager/Staff/customer → only their own patients
        return Patient.objects.filter(registered_by=user)
    
    def perform_create(self, serializer):
        """
        Set registered_by = request.user automatically
        """
        serializer.save(registered_by=self.request.user)
    
    @action(detail=False, methods=["get"])
    def patient_dropdown(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        # Select only required fields (IMPORTANT for performance)
        queryset = queryset.only("id", "first_name", "last_name")

        # Build lightweight response
        data = [
            {
                "id": obj.id,
                "name": obj.get_full_name()
            }
            for obj in queryset
        ]

        return Response(data,status=status.HTTP_200_OK)
    

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
        # CASE 1 → Only content_type → return entities (Service + Venue)
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

        # GenericRelation
        packages = obj.packages.all()

        serializer = PackageListSerializer(packages, many=True)
        return Response(serializer.data)

class InvoiceBookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing invoice bookings.    
    Handles:
    - Creating venue bookings (auto-creates monthly invoices)
    - Creating service bookings as children
    - Cancelling bookings (auto-cascades to invoices)
    - Rescheduling bookings (auto-updates invoices)
    """

    search_fields = ['patient__first_name', 'patient__last_name', 'booking_entity', 'status']  
    filterset_fields = {
        'patient': ['exact'],
        'start_datetime': ['month'],
        'end_datetime': ['month'],
        'booking_type': ['exact'],
        'status': ['exact'],
    }

    ordering_fields = ['user', 'patient', 'created_at', 'start_datetime', 'end_datetime']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get bookings filtered by user and optional parameters"""
        user = self.request.user
        queryset = InvoiceBooking.objects.filter(
            parent__isnull=True
        ).select_related(
            'patient',
            'venue',
            'service',
            'package',
            'parent'
        ).prefetch_related('children', 'invoices')

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

        service_id = self.request.query_params.get("service_id")
        if service_id:
            queryset = queryset.filter(
                Q(service=service_id) | Q(children__service=service_id) 
            ).distinct()

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
        Automatically creates monthly invoices if booking spans multiple months.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Set defaults
        serializer.validated_data['user'] = request.user
        serializer.validated_data['status'] = BookingStatus.BOOKED
        serializer.validated_data['booking_type'] = BookingType.IN_HOUSE
        serializer.validated_data['booking_entity'] = BookingEntity.VENUE
        
        # Save booking - this triggers invoice creation
        booking = serializer.save()
        booking.order_id = generate_order_id(instance=booking,created_by=request.user)
        booking.save(update_fields=["order_id"])
        
        response_serializer = InvoiceBookingSerializer(booking)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def add_service(self, request, pk=None):
        """
        Add a service booking as a child to a venue booking.
        
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
        parent = self.get_object()
        
        serializer = ServiceBookingCreateSerializer(
            data=request.data,
            context={"parent": parent},
        )

        serializer.is_valid(raise_exception=True)
        child_booking = serializer.save()
        
        # Recalculate parent invoices since child service was added
        parent._recalculate_invoices()
        
        response_serializer = InvoiceBookingSerializer(child_booking)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def cancel_venue(self, request, pk=None):
        """
        Cancel a venue booking and all its child bookings.
        Automatically updates associated invoices.
        """
        booking = self.get_object()
        
        if booking.status == BookingStatus.CANCELLED:
            return Response(
                {'message': 'Booking is already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Model's cancel() method handles everything
        booking.cancel()
        
        serializer = InvoiceBookingSerializer(booking)
        return Response(serializer.data)
   
    @action(detail=True, methods=['post'])
    def cancel_service(self, request, pk=None):
        """
        Cancel a child service booking.
        Automatically updates parent invoices.
        
        Payload:
        {
            "service_id": 22
        }
        """
        parent = self.get_object()
        
        if parent.status == BookingStatus.CANCELLED:
            return Response(
                {'message': 'Booking is already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        service_id = request.data.get('service_id')
        if not service_id:
            return Response(
                {'message': 'service_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            child_booking = parent.children.get(id=service_id)
        except InvoiceBooking.DoesNotExist:
            return Response(
                {'message': 'Service not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Cancel child and recalculate parent invoices
        child_booking.cancel()
        parent._recalculate_invoices()
        
        return Response({'message': 'Service cancelled successfully'})

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def reschedule_venue(self, request, pk=None):
        """
        Reschedule venue booking with automatic child service shifting.
        Automatically updates invoices.
        
        Payload:
        {
            "start_datetime": "2026-03-01T10:00:00Z",
            "end_datetime": "2026-05-31T18:00:00Z",
            "package": 3  # Optional
        }
        """
        booking = self.get_object()
        
        new_start = request.data.get("start_datetime")
        new_end = request.data.get("end_datetime")
        new_package = request.data.get("package")

        if not new_start or not new_end:
            return Response(
                {"message": "start_datetime and end_datetime are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_start_dt = parse_datetime(new_start)
            new_end_dt = parse_datetime(new_end)
            
            if not new_start_dt or not new_end_dt:
                raise ValueError("Invalid datetime format")
            
            # Model's reschedule method handles everything
            booking.reschedule(new_start_dt, new_end_dt, new_package)
        except ValidationError as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (ValueError, TypeError) as e:
            return Response(
                {"message": f"Invalid input: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = InvoiceBookingSerializer(booking)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def reschedule_service(self, request, pk=None):
        """
        Reschedule a single service child booking.
        Automatically updates its invoices.
        
        Payload:
        {
            "service_id": 5,
            "start_datetime": "2026-02-10T10:00:00Z",
            "end_datetime": "2026-02-10T12:00:00Z",
            "package": 2  # Optional
        }
        """
        parent = self.get_object()
        
        service_id = request.data.get("service_id")
        new_start = request.data.get("start_datetime")
        new_end = request.data.get("end_datetime")
        new_package = request.data.get("package")

        if not new_start or not new_end:
            return Response(
                {"message": "start_datetime and end_datetime are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            child = parent.children.get(id=service_id)
        except InvoiceBooking.DoesNotExist:
            return Response(
                {"message": "Service not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            new_start_dt = parse_datetime(new_start)
            new_end_dt = parse_datetime(new_end)
            
            if not new_start_dt or not new_end_dt:
                raise ValueError("Invalid datetime format")
            
            # Model's reschedule method handles everything
            child.reschedule(new_start_dt, new_end_dt, new_package)
        except ValidationError as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (ValueError, TypeError) as e:
            return Response(
                {"message": f"Invalid input: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = InvoiceBookingSerializer(child)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_venue(self, request):
        """Get all venue bookings with their services and invoices"""
        venue_bookings = self.get_queryset().filter(booking_entity='VENUE')
        serializer = InvoiceBookingSerializer(venue_bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def standalone_services(self, request):
        """Get all standalone service bookings (those without parent)"""
        service_bookings = self.get_queryset().filter(booking_entity='SERVICE')
        serializer = InvoiceBookingSerializer(service_bookings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def invoice_info(self, request, pk=None):
        """Get comprehensive invoice information for a booking"""
        booking = self.get_object()
        info = booking.get_booking_invoice_info()
        return Response(info)

class TotalInvoiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing invoices.
        
    Handles:
    - Manual invoice creation for specific periods
    - Retrieving invoice details and payments
    - Manual recalculation endpoints
    """
    # pagination_class = None
    queryset = TotalInvoice.objects.select_related(
        'booking', 'patient', 'user'
    ).prefetch_related('payments')
    serializer_class = TotalInvoiceSerializer
    search_fields = ['invoice_number', 'patient__first_name', 'patient__last_name', 'status']
    filterset_fields = {
        'patient': ['exact'],
        'booking__booking_type': ['exact'],
        'status': ['exact'],
    }

    ordering_fields = [
        'user', 'patient', 'created_at', 'period_start', 'period_end',
        'issued_date', 'status', 'total_amount'
    ]
    ordering = ['-created_at']
    
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Filter by customer
        if user.is_customer:
            queryset = queryset.filter(user=user)

        months_param = self.request.query_params.get('filter_months', None)

        if months_param:
            try:
                months = int(months_param)

                now = timezone.localtime()  # aware
                today = now.date()

                start_date = today - relativedelta(months=months)

                # Start of that day (00:00:00)
                start_datetime = timezone.make_aware(
                    datetime.combine(start_date, time.min),
                    timezone.get_current_timezone()
                )

                # End of that day (00:00:00)
                end_datetime = timezone.make_aware(
                    datetime.combine(today, time.max),
                    timezone.get_current_timezone()
                )

                queryset = queryset.filter(
                    period_start__gte=start_datetime,
                    # period_end__lte=end_datetime
                    
                )

            except (ValueError, TypeError):
                pass
    
        return queryset
    
    def list(self, request, *args, **kwargs):
        """
        Override list() to return grouped response by user and patient.
        """
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.order_by('user_id', 'patient_id')

        page = self.paginate_queryset(queryset)
        queryset_to_process = page if page is not None else queryset
        
        grouped_data = []

        for (user_id, patient_id), invoices_group in groupby(
            queryset_to_process,
            key=lambda x: (x.user_id, x.patient_id)
        ):
            invoices_list = list(invoices_group)
            
            if not invoices_list:
                continue
            
            first_invoice = invoices_list[0]
            user = first_invoice.user
            patient = first_invoice.patient
            
            total_invoice_amount = sum(inv.total_amount for inv in invoices_list)
            total_paid = sum(inv.paid_amount for inv in invoices_list)
            total_balance = total_invoice_amount - total_paid
            
            invoices_array = []
            for invoice in invoices_list:
                payments = invoice.payments.all()
                
                payment_details = [
                    {
                        'id': str(p.id),
                        'payment_date': str(p.created_at),
                        'amount': str(p.amount),
                        'paid_date': str(p.paid_date),
                        'method': p.method, 
                        'is_verified': p.is_verified,
                        'reference': p.reference or '-'
                    }
                    for p in payments
                ]
                
                invoices_array.append({
                    'id': str(invoice.id),
                    'invoice_date': str(invoice.issued_date),
                    'invoice_number': invoice.invoice_number,
                    'invoice_amount': str(invoice.total_amount),
                    'period_start': str(invoice.period_start),
                    'period_end': str(invoice.period_end),
                    'paid': str(invoice.paid_amount),
                    'balance': str(invoice.remaining_amount),
                    'status': invoice.get_status_display(),
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
        Create an invoice for a booking period.
        
        Payload:
        {
            "booking_id": 123,
            "period_start": "2026-02-01T00:00:00Z",
            "period_end": "2026-02-28T23:59:59Z"
        }
        """
        booking_id = request.data.get('booking_id')
        period_start_str = request.data.get('period_start')
        period_end_str = request.data.get('period_end')

        if not all([booking_id, period_start_str, period_end_str]):
            return Response(
                {'error': 'booking_id, period_start, and period_end are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse and validate datetime strings
        try:
            period_start = parse_datetime(period_start_str)
            period_end = parse_datetime(period_end_str)
            
            if not period_start or not period_end:
                raise ValueError("Invalid datetime format. Use ISO 8601 format.")
            
            if period_start >= period_end:
                raise ValueError("period_start must be before period_end")
        except (ValueError, TypeError) as e:
            return Response(
                {'error': f"Invalid date format: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            booking = InvoiceBooking.objects.select_related(
                'patient', 'user', 'parent'
            ).get(
                id=booking_id,
                user=request.user
            )
        except InvoiceBooking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate invoice period is within booking dates
        if period_start < booking.start_datetime or period_end > booking.end_datetime:
            return Response(
                {'error': 'Invoice period must be within booking dates'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Determine which booking should own the invoice
        invoice_booking = booking.parent if booking.parent else booking

        # Get or create invoice
        invoice, created = TotalInvoice.objects.get_or_create(
            booking=invoice_booking,
            period_start=period_start,
            period_end=period_end,
            defaults={
                "patient": invoice_booking.patient,
                "user": invoice_booking.user,
            }
        )

        # Always recalculate totals
        invoice.recalculate_totals()

        serializer = TotalInvoiceSerializer(invoice)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=status_code)

    @action(detail=True, methods=['get'])
    def recalculate(self, request, pk=None):
        """
        Manually recalculate invoice totals based on current bookings and payments.
        """
        invoice = self.get_object()
        invoice.recalculate_totals()
        
        serializer = TotalInvoiceSerializer(invoice)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_payment(self, request, pk=None):
        """
        Add a payment to an invoice.
        Invoice status is automatically recalculated.
        """
        invoice = self.get_object()
        
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        payment = Payment.objects.create(
            invoice=invoice,
            patient=invoice.patient,
            **serializer.validated_data
        )
        
        # Payment.save() automatically calls invoice.recalculate_payments()
        
        payment_serializer = PaymentSerializer(payment)
        return Response(payment_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get invoice summary statistics for the current user."""
        queryset = self.filter_queryset(self.get_queryset())
        total_stats = queryset.aggregate(
            total_invoices=Count('id'),
            total_amount=Sum('total_amount'),
            paid_amount=Sum('paid_amount'),
            remaining_amount=Sum('remaining_amount'),
            unpaid_count=Count('id', filter=Q(status=InvoiceStatus.UNPAID)),
            partially_paid_count=Count('id', filter=Q(status=InvoiceStatus.PARTIALLY_PAID)),
            paid_count=Count('id', filter=Q(status=InvoiceStatus.PAID))
        )
        
        serializer = InvoiceSummarySerializer(total_stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get all overdue invoices (due_date passed and status not PAID)."""
        today = timezone.now().date()
        overdue_invoices = self.get_queryset().filter(
            due_date__lt=today,
            status__in=['UNPAID', 'PARTIALLY_PAID']
        )
        
        serializer = self.serializer_class(overdue_invoices, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def payments(self, request, pk=None):
        """Get all payments for a specific invoice."""
        invoice = self.get_object()
        info = invoice.get_payments_info()
        return Response(info)

class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payments.
        
    Handles:
    - Recording payments
    - Verifying/unverifying payments
    - Tracking payment methods
    """
    filterset_fields = ['invoice_id', 'is_verified', 'method']  
    ordering_fields = ['created_at', 'amount', 'paid_date']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get payments for invoices belonging to current user"""
        queryset = Payment.objects.select_related('invoice', 'patient')
        user = self.request.user
        if user.is_customer:
            queryset = queryset.filter(invoice__user=user)
    
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return PaymentCreateSerializer
        return PaymentSerializer
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new payment.
        Invoice status is automatically recalculated.
        """
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
                
        output_serializer = PaymentSerializer(payment)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Mark a payment as verified.
        Invoice status is automatically recalculated.
        """
        payment = self.get_object()
        
        if not payment.invoice:
            return Response(
                {'error': 'Payment has no associated invoice'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Model's verify method handles everything
        success = payment.verify()
        
        if not success:
            return Response(
                {'message': 'Payment is already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = PaymentSerializer(payment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def unverify(self, request, pk=None):
        """
        Mark a payment as unverified.
        Invoice status is automatically recalculated.
        """
        payment = self.get_object()
        
        if not payment.invoice:
            return Response(
                {'error': 'Payment has no associated invoice'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Model's unverify method handles everything
        success = payment.unverify()
        
        if not success:
            return Response(
                {'message': 'Payment is not verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = PaymentSerializer(payment)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_verification(self, request):
        """Get all payments pending verification."""
        pending_payments = self.get_queryset().filter(is_verified=False)
        serializer = PaymentSerializer(pending_payments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def verified(self, request):
        """Get all verified payments."""
        verified_payments = self.get_queryset().filter(is_verified=True)
        serializer = PaymentSerializer(verified_payments, many=True)
        return Response(serializer.data)