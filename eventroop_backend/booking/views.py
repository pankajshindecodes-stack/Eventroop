from venue_manager.models import Venue, Service,Resource
from venue_manager.serializers import VenueSerializer, ServiceSerializer
from rest_framework import viewsets, permissions, status
from .serializers import *
from .models import *
from .filters import EntityFilter,InvoiceBookingFilter
from django.db.models import Q, Sum, Count
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
    ViewSet for managing invoice bookings with proper authorization and validation
    """
    queryset = InvoiceBooking.objects.select_related(
        'user', 'patient', 'venue', 'venue_package'
    )
    serializer_class = InvoiceBookingSerializer
    filterset_class = InvoiceBookingFilter

    search_fields = [
        "patient__first_name",
        "patient__last_name",
        "patient__email",
        "venue__name",
    ]

    ordering_fields = [
        "start_datetime",
        "end_datetime",
        "created_at",
    ]

    ordering = ["-created_at"]
    def get_queryset(self):
        """Filter bookings with proper authorization and optimization"""
        queryset = InvoiceBooking.objects.select_related(
            'user', 'patient', 'venue', 'venue_package'
        ).prefetch_related(
            'services',
            'services__service',
            'services__service_package'
        )

        # Authorization: customers can only see their own bookings
        user = self.request.user
        if user.is_customer:
            queryset = queryset.filter(user=user)

        return queryset

    def _validate_datetime_range(self, start_str, end_str):
        """Helper: Validate and parse datetime range"""
        try:
            start = parser.parse(start_str)
            end = parser.parse(end_str)
        except (ValueError, TypeError):
            raise ValueError('Invalid datetime format. Use ISO 8601.')
        
        if end <= start:
            raise ValueError('end_datetime must be after start_datetime')
        
        if start < timezone.now():
            raise ValueError('Cannot create bookings for past dates')
        
        return start, end

    def create(self, request, *args, **kwargs):
        """Create booking with full validation"""
        patient_id = request.data.get('patient_id')
        venue_id = request.data.get('venue_id')
        venue_package_id = request.data.get('venue_package_id')

        # Verify patient ownership
        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            return Response(
                {'error': 'Patient not found or unauthorized'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verify venue exists
        try:
            venue = Venue.objects.get(id=venue_id)
        except Venue.DoesNotExist:
            return Response(
                {'error': 'Venue not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verify package exists and belongs to venue
        try:
            package = Package.objects.get(
                id=venue_package_id,
                content_type__model='venue'
            )
        except Package.DoesNotExist:
            return Response(
                {'error': 'Invalid package for this venue'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate datetime range
        try:
            start, end = self._validate_datetime_range(
                request.data.get('start_datetime'),
                request.data.get('end_datetime')
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate booking type
        booking_type = request.data.get('booking_type', BookingTypeChoices.IN_HOUSE)
        valid_types = [choice[0] for choice in BookingTypeChoices.choices]
        if booking_type not in valid_types:
            return Response(
                {'error': f'Invalid booking_type'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create booking
        booking = InvoiceBooking.objects.create(
            user=request.user,
            patient=patient,
            venue=venue,
            venue_package=package,
            start_datetime=start,
            end_datetime=end,
            booking_type=booking_type,
            status=InvoiceBookingStatus.BOOKED
        )
        # invoice = booking.invoice
        # invoice.recalculate_totals()
        
        return Response(
            {"message": "Venue booked successfully.", "id": booking.id},
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def book_service(self, request, pk=None):
        """
        Book a service for an existing venue booking
        POST payload:
        {
            "service_id": 1,
            "service_package_id": 2,
            "start_datetime": "2024-02-15T10:00:00Z",
            "end_datetime": "2024-02-15T12:00:00Z"
        }
        """
        booking = self.get_object()
        serializer = BookServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Verify service exists
            from venue_manager.models import Service
            service = Service.objects.get(id=serializer.validated_data['service_id'])

            # Verify package exists
            package = get_object_or_404(
                Package,
                id=serializer.validated_data['service_package_id']
            )

            # Create service booking
            service_booking = InvoiceBookingService.objects.create(
                booking=booking,
                user=request.user,
                patient=booking.patient,
                service=service,
                service_package=package,
                start_datetime=serializer.validated_data['start_datetime'],
                end_datetime=serializer.validated_data['end_datetime'],
                status=InvoiceBookingStatus.BOOKED
            )
            invoice = booking.invoice
            invoice.service_bookings.add(service_booking)
            invoice.recalculate_totals()


            return Response(
                {"message": "Service Booked successfully."},
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"])
    def cancel_booking(self, request, pk=None):
        """
        POST /invoice-bookings/{id}/cancel/

        Cancels booking and all related services.
        """

        booking = self.get_object()
        try:
            booking.cancel()
            invoice = booking.invoice
            invoice.recalculate_totals()
        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"message": "Booking cancelled successfully."},            
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=["post"])
    def cancel_service(self, request, pk=None):
        """
        POST /invoice-booking-services/{id}/cancel/
        """

        booking = self.get_object()

        service_id = request.data.get("service_id")

        if not service_id:
            return Response(
                {"detail": "service_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        service = booking.services.filter(id=service_id).first()
        invoice = booking.invoice
        invoice.service_bookings.remove(service)
        invoice.recalculate_totals()
        if not service:
            return Response(
                {"detail": "Service not found in this booking"},
                status=status.HTTP_404_NOT_FOUND
            )


        try:
            service.cancel()
        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"message": "Service cancelled successfully."},
            status=status.HTTP_200_OK
        )

class TotalInvoiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing total invoices
    Provides endpoints for:
    - Listing invoices for a user
    - Retrieving invoice details
    - Getting overdue and pending invoices
    """
    
    queryset = TotalInvoice.objects.select_related(
        'booking', 'patient', 'user'
    ).prefetch_related('service_bookings', 'payments')
    serializer_class = TotalInvoiceSerializer

    def get_queryset(self):
        """Filter invoices based on user"""
        queryset = TotalInvoice.objects.filter(
            user=self.request.user
        ).select_related('booking', 'patient', 'user').prefetch_related(
            'service_bookings', 'payments'
        )

        # Optional filters
        patient_id = self.request.query_params.get('patient_id')
        status_filter = self.request.query_params.get('status')

        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    @action(detail=False, methods=['get'])
    def overdue_invoices(self, request):
        """Get all overdue invoices for the current user"""
        overdue = TotalInvoice.get_overdue_invoices().filter(user=request.user)
        serializer = self.get_serializer(overdue, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_invoices(self, request):
        """
        Get all pending invoices
        Query params:
        - patient_id: Filter by patient (optional)
        """
        patient_id = request.query_params.get('patient_id')
        pending = TotalInvoice.get_pending_invoices(
            patient=Patient.objects.get(id=patient_id) if patient_id else None
        ).filter(user=request.user)
        
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

