from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import *
from .serializers import *
from rest_framework import viewsets, status
from datetime import datetime, timedelta
from rest_framework.views import APIView
from dateutil.relativedelta import relativedelta
from django.db import transaction as db_transaction
from eventroop_backend.pagination import 

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

        # ----- User filter -----
        user_id = params.get("user_id")
        if user_id:
            try:
                user_id = int(user_id)
                queryset = queryset.filter(user_id=user_id)
            except ValueError:
                return queryset.none()

        # Initialize default date range (6 months to end of current month)
        today = datetime.now().date()
        end_date = (today.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)  # Last day of current month
        start_date = (end_date - relativedelta(months=6)).replace(day=1)  # First day, 6 months back

        # ----- Year filter (highest priority) -----
        year = params.get("year")
        if year:
            try:
                year = int(year)
                start_date = datetime(year, 1, 1).date()
                end_date = datetime(year, 12, 31).date()
                return queryset.filter(start_date__gte=start_date, start_date__lte=end_date)
            except ValueError:
                return queryset.none()

        # ----- Custom date override -----
        custom_start = params.get("start_date")
        custom_end = params.get("end_date")

        if custom_start or custom_end:
            try:
                if custom_start:
                    start_date = datetime.strptime(custom_start, "%Y-%m-%d").date()
                if custom_end:
                    end_date = datetime.strptime(custom_end, "%Y-%m-%d").date()
            except ValueError:
                return queryset.none()

        # ----- Apply date filters -----
        return queryset.filter(
            start_date__gte=start_date,
            start_date__lte=end_date,
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

class SalaryTransactionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    def list(self, request):
        """
        GET /api/salary-transactions/
        List all salary transactions
        """
        transactions = SalaryTransaction.objects.all().order_by('created_at')
        
        # Optional filters
        status_filter = request.query_params.get('status')
        if status_filter:
            transactions = transactions.filter(status=status_filter)
        
        user_filter = request.query_params.get('user_id')
        if user_filter:
            transactions = transactions.filter(salary_report__user_id=user_filter)
        
        serializer = SalaryTransactionSerializer(transactions, many=True)
        
        return Response(serializer.data)

    @db_transaction.atomic
    def create(self, request):
        """
        POST /api/salary-transactions/
        Create or update salary transaction based on existing transaction status
        
        Rules:
        - If PENDING/PROCESSING: Update existing transaction to SUCCESS
        - If FAILED/CANCELLED: Create new transaction
        - If SUCCESS: Return error (already paid)
        """
        serializer = SalaryTransactionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        salary_report_id = serializer.validated_data['salary_report_id']
        salary_report = SalaryReport.objects.get(id=salary_report_id)
        amount_paid = serializer.validated_data['amount_paid']
        
        # Check if transaction exists
        existing_transaction = SalaryTransaction.objects.filter(
            salary_report_id=salary_report_id
        ).first()

        if existing_transaction:
            # Transaction exists - check its status
            if existing_transaction.status in ['PENDING', 'PROCESSING']:
                # Update existing transaction to SUCCESS
                existing_transaction.status = 'SUCCESS'
                existing_transaction.amount_paid = amount_paid
                existing_transaction.payment_method = serializer.validated_data['payment_method']
                existing_transaction.payment_reference = serializer.validated_data.get('payment_reference', '')
                existing_transaction.note = serializer.validated_data.get('note', '')
                existing_transaction.processed_at = timezone.now()
                existing_transaction.save()
            
            elif existing_transaction.status in ['FAILED', 'CANCELLED']:
                # Create new transaction
                SalaryTransaction.objects.create(
                    salary_report=salary_report,
                    amount_paid=amount_paid,
                    payment_method=serializer.validated_data['payment_method'],
                    payment_reference=serializer.validated_data.get('payment_reference', ''),
                    note=serializer.validated_data.get('note', ''),
                    processed_at=timezone.now(),
                    status='SUCCESS',
                )
        else:
            # No existing transaction - create new one
            SalaryTransaction.objects.create(
                salary_report=salary_report,
                amount_paid=amount_paid,
                payment_method=serializer.validated_data['payment_method'],
                payment_reference=serializer.validated_data.get('payment_reference', ''),
                note=serializer.validated_data.get('note', ''),
                processed_at=timezone.now(),
                status='SUCCESS',
            )
        # Update salary report when transaction is SUCCESS
        salary_report.paid_amount = SalaryTransaction.objects.filter(
            salary_report_id=salary_report_id,
            status='SUCCESS'
        ).aggregate(total=models.Sum('amount_paid'))['total'] or 0
        
        salary_report.remaining_payment = (
            salary_report.total_payable_amount - salary_report.paid_amount
        )
        salary_report.advance_amount = abs(
            salary_report.total_payable_amount - salary_report.paid_amount
        )
        salary_report.save(update_fields=['paid_amount', 'remaining_payment', 'updated_at'])

        return Response(
            {'detail': 'Payment processed successfully.'},
            status=status.HTTP_200_OK
        )