from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import SalaryStructure, SalaryTransaction
from .serializers import SalaryStructureSerializer,SalaryTransactionSerializer
from rest_framework import viewsets, status
from rest_framework.decorators import action
 
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


class SalaryTransactionViewSet(viewsets.ModelViewSet):
    """
    Payroll SalaryTransaction API
    """
    serializer_class = SalaryTransactionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'user_id']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'payment_reference']
    ordering_fields = ['created_at', 'status', 'amount', 'user__first_name']
    ordering = ['-created_at']
    def get_queryset(self):
        user = self.request.user

        # Owner can see all, others only their salary
        if user.is_superuser:
            return SalaryTransaction.objects.all()

        if user.is_owner:
            return SalaryTransaction.objects.filter(user__hierarchy__owner=user)
        if user.is_manager or user.is_vsre_staff:
            return SalaryTransaction.objects.filter(user=user)

    def perform_update(self, serializer):
        instance = self.get_object()

        # Prevent update after payment success
        if instance.status == "SUCCESS":
            raise ValueError("Paid salary cannot be modified")

        serializer.save()

    # -------------------------------
    # Custom Actions
    # -------------------------------

    @action(detail=True, methods=["post"])
    def mark_processing(self, request, pk=None):
        txn = self.get_object()
        txn.mark_as_processing()
        return Response({"status": "PROCESSING"})

    @action(detail=True, methods=["post"])
    def mark_paid(self, request, pk=None):
        txn = self.get_object()

        paid_amount = request.data.get("paid_amount")
        payment_reference = request.data.get("payment_reference")

        txn.mark_as_paid(
            paid_amount=paid_amount,
            payment_reference=payment_reference
        )

        return Response(
            SalaryTransactionSerializer(txn).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def mark_failed(self, request, pk=None):
        txn = self.get_object()
        reason = request.data.get("reason")

        txn.mark_as_failed(reason=reason)
        return Response({"status": "FAILED"})
