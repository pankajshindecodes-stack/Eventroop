from venue_manager.models import Venue, Service, Resource
from venue_manager.serializers import VenueSerializer, ServiceSerializer
from rest_framework import viewsets, permissions, status
from .serializers import *
from .models import *
from .filters import EntityFilter,InvoiceBookingFilter
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

    serializer_class = InvoiceBookingSerializer
    filterset_class = InvoiceBookingFilter

    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = InvoiceBooking.objects.select_related(
            "user",
            "patient",
            "venue",
            "venue_package",
            "invoice",
        ).prefetch_related(
            "services",
            "services__service",
            "services__service_package",
        )

        user = self.request.user
        if user.is_customer:
            queryset = queryset.filter(user=user)

        return queryset

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        patient = serializer.validated_data["patient"]

        if not (
            patient.registered_by == request.user
            or getattr(request.user, "is_owner", False)
        ):
            return Response({"error": "Unauthorized patient"}, status=403)

        booking = serializer.save(user=request.user, status=InvoiceBookingStatus.BOOKED)

        # Ensure invoice exists
        invoice, _ = TotalInvoice.objects.get_or_create(
            booking=booking,
            defaults={
                "patient": booking.patient,
                "user": booking.user,
            },
        )

        invoice.recalculate_totals()

        return Response(
            InvoiceBookingSerializer(booking, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def book_service(self, request, pk=None):

        booking = self.get_object()

        if booking.status == InvoiceBookingStatus.CANCELLED:
            return Response({"detail": "Booking cancelled"}, status=400)

        serializer = BookServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_object_or_404(Service, id=serializer.validated_data["service_id"])
        package = get_object_or_404(
            Package, id=serializer.validated_data["service_package_id"]
        )

        service_booking = InvoiceBookingService.objects.create(
            booking=booking,
            user=request.user,
            patient=booking.patient,
            service=service,
            service_package=package,
            start_datetime=serializer.validated_data["start_datetime"],
            end_datetime=serializer.validated_data["end_datetime"],
            status=InvoiceBookingStatus.BOOKED,
        )

        invoice, _ = TotalInvoice.objects.get_or_create(
            booking=booking,
            defaults={"patient": booking.patient, "user": booking.user},
        )

        invoice.service_bookings.add(service_booking)
        invoice.recalculate_totals()

        return Response({"message": "Service booked."}, status=201)
    
    @action(detail=True, methods=["post"])
    def cancel_booking(self, request, pk=None):

        booking = self.get_object()

        try:
            booking.cancel()
            booking.invoice.recalculate_totals()
        except ValidationError as e:
            return Response({"detail": str(e)}, status=400)

        return Response({"message": "Booking cancelled."})

    @action(detail=True, methods=["post"])
    def cancel_service(self, request, pk=None):

        booking = self.get_object()
        service_id = request.data.get("service_booking_id")

        if not service_id:
            return Response({"detail": "service_id required"}, status=400)

        service = booking.services.filter(id=service_id).first()

        if not service:
            return Response({"detail": "Service not found"}, status=404)

        try:
            service.cancel()
            booking.invoice.service_bookings.remove(service)
            booking.invoice.recalculate_totals()
        except ValidationError as e:
            return Response({"detail": str(e)}, status=400)

        return Response({"message": "Service cancelled."})

class TotalInvoiceViewSet(viewsets.ReadOnlyModelViewSet):

    filterset_fields = [
        "status",
        "patient",
        "user",
        "booking",
    ]

    search_fields = [
        "patient__first_name",
        "patient__last_name",
        "user__first_name",
        "user__last_name",
        "booking__id",
    ]

    ordering_fields = [
        "user",
        "patient",
        "created_at",
        "updated_at",
        "total_amount",
        "paid_amount",
        "status",
    ]

    ordering = ["-created_at"]  # default ordering

    serializer_class = TotalInvoiceListSerializer
    
    def get_queryset(self):

        queryset = TotalInvoice.objects.select_related(
            "patient", "user", "booking"
        ).prefetch_related(
            Prefetch("payments", queryset=Payment.objects.order_by("-created_at"))
        )

        user = self.request.user
        if user.is_customer:
            queryset = queryset.filter(user=user)

        return queryset.order_by("-created_at")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """
        Example:
        /total-invoices/summary/
        /total-invoices/summary/?status=PAID
        """

        # IMPORTANT: use filtered queryset (so filters/search apply)
        queryset = self.filter_queryset(self.get_queryset())

        today = timezone.now().date()

        data = {
            "total_invoices": queryset.count(),

            "total_amount_sum": queryset.aggregate(
                total=Sum("total_amount")
            )["total"] or 0,

            "paid_amount_sum": queryset.aggregate(
                paid=Sum("paid_amount")
            )["paid"] or 0,

            # Status based counts (adjust status values to your model)
            "paid_count": queryset.filter(status="PAID").count(),

            "unpaid_count": queryset.filter(status="UNPAID").count(),

            "partial_paid_count": queryset.filter(status="PARTIAL").count(),

            "pending_count": queryset.filter(status="PENDING").count(),

            # Overdue (due_date < today AND not paid)
            "overdue_count": queryset.filter(
                Q(due_date__lt=today) & ~Q(status="PAID")
            ).count(),
        }

        return Response(data)


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    queryset = Payment.objects.select_related(
        "invoice",
        "patient"
    ).order_by("-created_at")

    # Exact filtering
    filterset_fields = [
        "invoice",
        "patient",
        "method",
        "is_verified",
    ]

    # Search (partial match)
    search_fields = [
        "reference",
        "invoice__invoice_number",
        "patient__first_name",
        "patient__last_name",
    ]

    # Ordering
    ordering_fields = [
        "created_at",
        "amount",
        "method",
        "is_verified",
    ]

    ordering = ["-created_at"]
    def get_queryset(self):
        queryset = self.queryset

        user = self.request.user
        if user.is_customer:
            queryset = queryset.filter(invoice__user=user)

        return queryset

 
    @transaction.atomic
    def perform_create(self, serializer):
        """
        Atomic create so invoice + payment always stay in sync
        """
        serializer.save()

    # ---------------- Custom Actions ---------------- #

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """
        Mark payment as verified
        POST /payments/{id}/verify/
        """
        payment = self.get_object()
        payment.is_verified = True
        payment.save(update_fields=["is_verified", "updated_at"])

        return Response({"status": "payment verified"})

    @action(detail=False, methods=["get"])
    def unverified(self, request):
        """
        /payments/unverified/
        """
        qs = Payment.get_unverified_payments()
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
