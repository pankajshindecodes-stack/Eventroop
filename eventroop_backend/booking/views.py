from venue_manager.models import Venue, Service
from venue_manager.serializers import VenueSerializer, ServiceSerializer
from rest_framework import viewsets, permissions, status
from .serializers import *
from .models import *
from .filters import EntityFilter
from django.db.models import Q, Sum, Count
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime
from decimal import Decimal

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

    @action(detail=False, methods=['get'])
    def by_belongs_to(self, request):
        """
        Example:
        /booking/packages/by_belongs_to/?content_type=venue&object_id=3
        """
        from django.contrib.contenttypes.models import ContentType
        
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

class InvoiceBookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing invoice bookings and services
    Provides endpoints for:
    - Listing all bookings for a patient/user
    - Creating new bookings
    - Booking services
    """
    
    queryset = InvoiceBooking.objects.select_related(
        'user', 'patient', 'venue', 'venue_package'
    )
    serializer_class = InvoiceBookingSerializer

    def get_queryset(self):
        """Filter bookings based on user and optional filters"""
        queryset = InvoiceBooking.objects.select_related(
            'user', 'patient', 'venue', 'venue_package'
        ).prefetch_related('services')

        # Filter by current user
        user = self.request.user
        if user.is_customer:
            queryset = queryset.filter(user=user)

        # Optional filters
        patient_id = self.request.query_params.get('patient_id')
        status_filter = self.request.query_params.get('status')
        venue_id = self.request.query_params.get('venue_id')

        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if venue_id:
            queryset = queryset.filter(venue_id=venue_id)
        return queryset

    def create(self, request, *args, **kwargs):
        """Create a new venue booking"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            patient = Patient.objects.get(id=request.data.get('patient_id'))
            
            InvoiceBooking.objects.create(
                user=request.user,
                patient=patient,
                venue_id=request.data.get('venue_id'),
                venue_package_id=request.data.get('venue_package_id'),
                start_datetime=request.data.get('start_datetime'),
                end_datetime=request.data.get('end_datetime'),
                booking_type=request.data.get('booking_type'),
                status=InvoiceBookingStatus.BOOKED
            )

            return Response(
                {"message": "Venue Booked successfully."},
                status=status.HTTP_201_CREATED
            )
        except Patient.DoesNotExist:
            return Response(
                {'error': 'Patient not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
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

