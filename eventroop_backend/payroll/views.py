from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import SalaryStructure, SalaryReport
from .serializers import SalaryStructureSerializer,SalaryReportSerializer
from rest_framework import viewsets, status
from datetime import datetime, timedelta
from rest_framework.views import APIView
 
class SalaryStructureViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing salary structures
    """

    serializer_class = SalaryStructureSerializer
    permission_classes = [IsAuthenticated]

    filterset_fields = [
        "user_id",
        "salary_type",
        "change_type",
        "effective_from",
    ]

    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "user__mobile_number",
    ]

    def get_queryset(self):
        """
        Get queryset based on user hierarchy
        """
        user = self.request.user

        # Admin → see everything
        if user.is_superuser:
            queryset = SalaryStructure.objects.all()

        # Owner → see salary structures of their staff + managers
        elif getattr(user, "is_owner", False):
            queryset = SalaryStructure.objects.filter(user__hierarchy__owner=user)

        # Staff or Manager → see only their own salary structure
        else:
            queryset = SalaryStructure.objects.filter(user=user)
        return queryset.select_related("user").order_by("-effective_from")

class SalaryReportAPIView(APIView):
    """
    READ-ONLY Salary Report API

    GET /api/salary-reports/
    GET /api/salary-reports/<id>/

    Filters:
    - Default: last 6 months
    - ?year=YYYY
    - ?start_date=YYYY-MM-DD
    - ?end_date=YYYY-MM-DD
    """

    permission_classes = [IsAuthenticated]

    # -------------------- Base queryset --------------------
    def get_base_queryset(self, request):
        user = request.user

        if user.is_superuser:
            return SalaryReport.objects.all()

        if user.is_owner:
            return SalaryReport.objects.filter(user__hierarchy__owner=user)

        if user.is_manager or user.is_vsre_staff:
            return SalaryReport.objects.filter(user=user)

        return SalaryReport.objects.none()

    # -------------------- Date filters --------------------
    def apply_date_filters(self, request, queryset):
        params = request.query_params

        # ----- Year filter (highest priority) -----
        year = params.get("year")
        if year:
            try:
                year = int(year)
                return queryset.filter(start_date__year=year)
            except ValueError:
                return queryset.none()

        # ----- Default: last 6 months -----
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=180)

        # ----- Custom override -----
        custom_start = params.get("start_date")
        custom_end = params.get("end_date")

        if custom_start:
            try:
                start_date = datetime.strptime(custom_start, "%Y-%m-%d").date()
            except ValueError:
                return queryset.none()

        if custom_end:
            try:
                end_date = datetime.strptime(custom_end, "%Y-%m-%d").date()
            except ValueError:
                return queryset.none()

        return queryset.filter(
            start_date__gte=start_date,
            end_date__lte=end_date,
        )

    # -------------------- GET --------------------
    def get(self, request, pk=None):
        queryset = self.get_base_queryset(request)
        queryset = self.apply_date_filters(request, queryset)

        # ----- Retrieve single report -----
        if pk:
            try:
                report = queryset.get(pk=pk)
            except SalaryReport.DoesNotExist:
                return Response(
                    {"detail": "Salary report not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = SalaryReportSerializer(report)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # ----- List reports -----
        serializer = SalaryReportSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
