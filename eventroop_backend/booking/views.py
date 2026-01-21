from venue_manager.models import Venue,Service
from venue_manager.serializers import VenueSerializer,ServiceSerializer
from rest_framework import viewsets, permissions,status
from .serializers import *
from .models import Patient,Package
from .filters import EntityFilter
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response


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
        # "category": ["iexact", "icontains"],
        # "sub_category": ["iexact", "icontains"],
        "city": ["iexact", "icontains"],
        # "tags": ["iexact", "icontains"],
        # "starting_price": ["gte", "lte"],
        # "rating": ["gte", "lte", "exact"],

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

        # Owner → return all patient data
        if user.is_owner:
            return Patient.objects.filter(
                Q(registered_by__hierarchy__owner=user) |
                Q(registered_by=user)
            )


        # Manager/Staff → only their own patients
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
        "user__mobile_number"
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

        return qs.order_by("-id")  # or any default ordering you prefer
    
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
        if user.is_vsre_staff:
            return Package.objects.filter(owner=user.hierarchy.owner)
        return Package.objects.filter(owner=user)

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

    @action(detail=False, methods=['get'])
    def by_belongs_to(self, request):
        """
        Example:
        /booking/packages/by_belongs_to/?content_type=venue&object_id=3
        """
        content_type_name = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')

        if not content_type_name or not object_id:
            return Response(
                {'error': 'content_type and object_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Resolve model name → ContentType row
            content_type = ContentType.objects.get(model=content_type_name.lower())
        except ContentType.DoesNotExist:
            return Response(
                {'error': f'Invalid content_type: {content_type_name}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        packages = self.get_queryset().filter(
            content_type=content_type,
            object_id=object_id
        )

        serializer = self.get_serializer(packages, many=True)
        return Response(serializer.data)

class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing venue bookings.
    
    Supports filtering by: status, user, patient, venue
    Search fields: patient__name, invoice__invoice_number
    Ordering: start_datetime, created_at, final_amount
    """
    filterset_fields = ['status', 'user', 'patient', 'venue']
    search_fields = ['patient__name', 'invoice__invoice_number']
    ordering_fields = ['start_datetime', 'created_at', 'final_amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter bookings based on user role"""
        user = self.request.user
        queryset = Booking.objects.select_related(
            'user', 'patient', 'venue', 'venue_package'
        ).prefetch_related('booking_services')
        
        if user.is_customer:
            queryset = queryset.filter(user=user)
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return BookingCreateUpdateSerializer
        elif self.action in ['update', 'partial_update']:
            return BookingCreateUpdateSerializer
        return BookingListSerializer
    
    def perform_create(self, serializer):
        """Set user to current request user and initial status"""
        try:
            serializer.save(
                user=self.request.user,
                status=BookingStatus.DRAFT
            )
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict)
    
    def perform_update(self, serializer):
        """Handle booking updates"""
        try:
            serializer.save()
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict)
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update booking status"""
        booking = self.get_object()
        new_status = request.data.get('status')
        
        # Validate status
        valid_statuses = dict(BookingStatus.choices)
        if new_status not in valid_statuses:
            return Response(
                {'error': f'Invalid status. Valid options: {list(valid_statuses.keys())}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = new_status
        try:
            booking.save()
            serializer = self.get_serializer(booking)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an existing booking"""
        booking = self.get_object()
        
        # Prevent cancellation of completed/already cancelled bookings
        if booking.status in [BookingStatus.FULFILLED, BookingStatus.CANCELLED]:
            return Response(
                {'error': f'Cannot cancel booking with status: {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = BookingStatus.CANCELLED
        try:
            booking.save()
            return Response(
                {
                    'message': 'Booking cancelled successfully',
                    'booking': self.get_serializer(booking).data
                },
                status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming bookings for current user"""
        upcoming_bookings = self.get_queryset().filter(
            status=BookingStatus.BOOKED,
            start_datetime__gt=timezone.now()
        )
        serializer = self.get_serializer(upcoming_bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def ongoing(self, request):
        """Get currently ongoing bookings"""
        ongoing_bookings = self.get_queryset().filter(
            status=BookingStatus.IN_PROGRESS
        )
        serializer = self.get_serializer(ongoing_bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def recalculate_costs(self, request, pk=None):
        """Manually recalculate booking costs"""
        booking = self.get_object()
        try:
            booking.recalculate_totals()
            booking.save()
            serializer = self.get_serializer(booking)
            return Response(
                {
                    'message': 'Costs recalculated successfully',
                    'booking': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
class BookingServiceViewSet(viewsets.ModelViewSet):
    serializer_class = BookingServiceSerializer
    filterset_fields = ['booking', 'service', 'status', 'patient']
    search_fields = ['service__name', 'patient__name']
    ordering_fields = ['start_datetime', 'created_at', 'service_total_price']
    ordering = ['start_datetime']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_customer:
            return BookingService.objects.filter(user=user).select_related('booking', 'service', 'service_package')
        return BookingService.objects.all().select_related('booking', 'service', 'service_package')
    
        
    @action(detail=False, methods=['get'])
    def by_booking(self, request):
        """
        Get all services for a specific booking.
        
        Query parameters:
        - booking_id: The booking ID (required)
        """
        booking_id = request.query_params.get('booking_id')

        if not booking_id:
            return Response(
                {'error': 'booking_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify booking belongs to user
        booking_intance = get_object_or_404(Booking, id=booking_id)

        services = self.get_queryset().filter(booking=booking_intance)
        serializer = self.get_serializer(services, many=True)
        return Response(
            {
                'booking_id': booking_id,
                'booking_patient': booking_intance.patient.get_full_name(),
                'services_count': services.count(),
                'total_services_cost': str(booking_intance.services_cost),
                'services': serializer.data
            },
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def by_service(self, request):
        """
        Get all bookings/instances for a specific service.
        
        Query parameters:
        - service_id: The service ID (required)
        """
        service_id = request.query_params.get('service_id')

        if not service_id:
            return Response(
                {'error': 'service_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        services = self.get_queryset().filter(service_id=service_id)

        if not services.exists():
            return Response(
                {'error': 'No services found for the given service_id'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(services, many=True)

        return Response(
            {
                'service_id': service_id,
                'bookings_count': services.count(),
                'total_revenue': str(sum(s.service_total_price for s in services)),
                'services': serializer.data
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):

        """
        Change the status of a BookingService.
        
        Request body:
        {
            "status": "IN_PROGRESS"
        }
        """
        booking_service = self.get_object()
        new_status = request.data.get('status')

        if not new_status:
            return Response(
                {'error': 'status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        booking_service.status = new_status
        booking_service.save(update_fields=['status'])

        return Response(
            self.get_serializer(booking_service).data,
            status=status.HTTP_200_OK
        )


# class InvoiceViewSet(viewsets.ModelViewSet):
#     """
#     ViewSet for InvoiceTransaction management
    
#     Endpoints:
#     - GET /invoices/ - List all invoices
#     - POST /invoices/ - Create new invoice
#     - GET /invoices/{id}/ - Get invoice details
#     - PUT/PATCH /invoices/{id}/ - Update invoice
#     - DELETE /invoices/{id}/ - Delete invoice
#     - POST /invoices/{id}/record_payment/ - Record payment
#     - POST /invoices/{id}/send/ - Mark invoice as sent
#     - GET /invoices/stats/summary/ - Get payment statistics
#     """
    
#     queryset = InvoiceTransaction.objects.select_related('booking', 'booking_service')
#     filterset_fields = ['invoice_type', 'payment_status', 'payment_method']
#     search_fields = ['invoice_number', 'notes']
#     ordering_fields = ['invoice_date', 'due_date', 'total_amount']
#     ordering = ['-invoice_date']
    
#     def get_serializer_class(self):
#         if self.action == 'create':
#             return InvoiceCreateSerializer
#         elif self.action == 'retrieve':
#             return InvoiceDetailSerializer
#         elif self.action == 'record_payment':
#             return InvoicePaymentSerializer
#         elif self.action in ['update', 'partial_update']:
#             return InvoiceUpdateSerializer
#         return InvoiceSerializer
    
#     def create(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         self.perform_create(serializer)
        
#         # Return full details after creation
#         invoice = serializer.instance
#         return Response(
#             InvoiceDetailSerializer(invoice).data,
#             status=status.HTTP_201_CREATED
#         )
    
#     @action(detail=True, methods=['post'])
#     def record_payment(self, request, pk=None):
#         """Record a payment for the invoice"""
#         invoice = self.get_object()
#         serializer = InvoicePaymentSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
        
#         try:
#             invoice.record_payment(
#                 amount=serializer.validated_data['amount'],
#                 method=serializer.validated_data.get('payment_method'),
#                 transaction_id=serializer.validated_data.get('transaction_id', '')
#             )
#             return Response(
#                 {
#                     'success': True,
#                     'message': f"Payment of {serializer.validated_data['amount']} recorded",
#                     'invoice': InvoiceDetailSerializer(invoice).data
#                 },
#                 status=status.HTTP_200_OK
#             )
#         except Exception as e:
#             return Response(
#                 {'error': str(e)},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
    
#     @action(detail=True, methods=['post'])
#     def send(self, request, pk=None):
#         """Mark invoice as sent"""
#         invoice = self.get_object()
#         from django.utils import timezone
        
#         invoice.is_sent = True
#         invoice.sent_date = timezone.now()
#         invoice.save()
        
#         return Response(
#             {
#                 'success': True,
#                 'message': 'InvoiceTransaction marked as sent',
#                 'invoice': InvoiceDetailSerializer(invoice).data
#             },
#             status=status.HTTP_200_OK
#         )
    
#     @action(detail=False, methods=['get'])
#     def stats_summary(self, request):
#         """Get payment statistics"""
#         from django.db.models import Sum, Count, Q
        
#         stats = {
#             'total_invoices': InvoiceTransaction.objects.count(),
#             'pending': InvoiceTransaction.objects.filter(
#                 payment_status=InvoiceTransaction.PaymentStatus.PENDING
#             ).count(),
#             'partially_paid': InvoiceTransaction.objects.filter(
#                 payment_status=InvoiceTransaction.PaymentStatus.PARTIALLY_PAID
#             ).count(),
#             'paid': InvoiceTransaction.objects.filter(
#                 payment_status=InvoiceTransaction.PaymentStatus.PAID
#             ).count(),
#             'cancelled': InvoiceTransaction.objects.filter(
#                 payment_status=InvoiceTransaction.PaymentStatus.CANCELLED
#             ).count(),
#             'total_amount_due': str(
#                 InvoiceTransaction.objects.aggregate(
#                     total=Sum('amount_due')
#                 )['total'] or Decimal('0.00')
#             ),
#             'total_amount_paid': str(
#                 InvoiceTransaction.objects.aggregate(
#                     total=Sum('amount_paid')
#                 )['total'] or Decimal('0.00')
#             ),
#             'total_invoice_value': str(
#                 InvoiceTransaction.objects.aggregate(
#                     total=Sum('total_amount')
#                 )['total'] or Decimal('0.00')
#             )
#         }
#         return Response(stats, status=status.HTTP_200_OK)
    
#     @action(detail=False, methods=['get'])
#     def by_status(self, request):
#         """Get invoices grouped by payment status"""
#         status_param = request.query_params.get('status')
        
#         if not status_param:
#             return Response(
#                 {'error': 'status parameter required'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         invoices = InvoiceTransaction.objects.filter(payment_status=status_param)
#         serializer = self.get_serializer(invoices, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)

