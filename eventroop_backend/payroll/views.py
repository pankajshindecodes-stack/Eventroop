from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
from .models import SalaryStructure, CustomUser, SalaryTransaction
from .serializers import SalaryStructureSerializer
from rest_framework import viewsets, status

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
            print(queryset)
        return queryset.select_related("user").order_by("-effective_from")

class SalaryTransactionView(APIView):
    """
    GET: Get salary payment history with filtering
    POST: Create salary transactions (single or bulk)
    """
    permission_classes = [IsAuthenticated]
    
    def _check_user_access(self, target_user_id):
        """Helper method to check if user has access to target user's data"""
        if self.request.user.is_superuser:
            return True
        if self.request.user.is_owner:
            try:
                target_user = CustomUser.objects.get(pk=target_user_id)
                return hasattr(target_user, 'hierarchy') and target_user.hierarchy.owner == self.request.user
            except CustomUser.DoesNotExist:
                return False
        return str(self.request.user.id) == str(target_user_id)
    
    def get(self, request):
        """Retrieve salary payment history with flexible filtering"""
        employee_id = request.query_params.get('employee_id')
        status_filter = request.query_params.get('status')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        pending_only = request.query_params.get('pending_only', 'false').lower() == 'true'
        
        if employee_id:
            if not self._check_user_access(employee_id):
                return Response(
                    {"status": "error", "message": "Permission denied"},
                    status=status.HTTP_403_FORBIDDEN
                )
            transactions = SalaryTransaction.objects.filter(receiver_id=employee_id)
        elif pending_only:
            # Only owners can view all pending salaries
            if not request.user.is_owner:
                return Response(
                    {"status": "error", "message": "Only employers can view pending salaries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            transactions = SalaryTransaction.objects.filter(payer=request.user, status='PENDING')
        else:
            transactions = SalaryTransaction.objects.filter(receiver_id=request.user.id)
        
        if start_date:
            transactions = transactions.filter(payment_period_start__gte=start_date)
        if end_date:
            transactions = transactions.filter(payment_period_end__lte=end_date)
        if status_filter:
            transactions = transactions.filter(status=status_filter)
        
        transactions = transactions.select_related('receiver', 'payer').order_by('-payment_period_start')
        
        data = [
            {
                "transaction_id": str(t.transaction_id),
                "employee": t.receiver.get_full_name(),
                "employer": t.payer.get_full_name() if t.payer else None,
                "amount": float(t.amount),
                "payment_type": t.payment_type,
                "status": t.status,
                "payment_method": t.payment_method,
                "payment_period": f"{t.payment_period_start} to {t.payment_period_end}",
                "created_at": t.created_at.isoformat(),
                "processed_at": t.processed_at.isoformat() if t.processed_at else None,
                "payment_reference": t.payment_reference,
                "note": t.note
            } for t in transactions
        ]
        
        return Response(
            {
                "status": "success",
                "count": len(data),
                "results": data
            },
            status=status.HTTP_200_OK
        )
    
    def post(self, request):
        """Create single or bulk salary transactions"""
        if not request.user.is_owner:
            return Response(
                {"status": "error", "message": "Only employers can create salary transactions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Check if bulk operation
            payments_data = request.data.get('payments')
            
            if payments_data:
                # Bulk operation
                transactions = self._process_bulk_payments(payments_data)
                return Response(
                    {
                        "status": "success",
                        "message": f"{len(transactions)} salary transactions created",
                        "data": [
                            {
                                "transaction_id": str(t.transaction_id),
                                "employee": t.receiver.get_full_name(),
                                "amount": float(t.amount),
                                "status": t.status,
                                "period": f"{t.payment_period_start} to {t.payment_period_end}"
                            } for t in transactions
                        ]
                    },
                    status=status.HTTP_201_CREATED
                )
            else:
                # Single transaction
                transaction = self._create_single_payment(request.data)
                return Response(
                    {
                        "status": "success",
                        "message": "Salary transaction created successfully",
                        "data": {
                            "transaction_id": str(transaction.transaction_id),
                            "employee": transaction.receiver.get_full_name(),
                            "amount": float(transaction.amount),
                            "status": transaction.status,
                            "payment_period": f"{transaction.payment_period_start} to {transaction.payment_period_end}",
                            "created_at": transaction.created_at.isoformat()
                        }
                    },
                    status=status.HTTP_201_CREATED
                )
        
        except ValueError as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _create_single_payment(self, data):
        """Helper to create a single salary transaction"""
        required_fields = ['receiver_id', 'amount', 'payment_type', 'payment_period_start', 'payment_period_end']
        if not all(field in data for field in required_fields):
            raise ValueError("Missing required fields")
        
        try:
            receiver = CustomUser.objects.get(id=data['receiver_id'])
        except CustomUser.DoesNotExist:
            raise ValueError("Employee not found")
        
        if not hasattr(receiver, 'hierarchy') or receiver.hierarchy.owner != self.request.user:
            raise ValueError("Employee does not belong to your organization")
        
        return SalaryTransaction.objects.create(
            receiver=receiver,
            payer=self.request.user,
            amount=Decimal(str(data['amount'])),
            payment_type=data['payment_type'],
            payment_period_start=data['payment_period_start'],
            payment_period_end=data['payment_period_end'],
            payment_method=data.get('payment_method', 'BANK_TRANSFER'),
            note=data.get('note'),
            status='PENDING'
        )
    
    def _process_bulk_payments(self, payments_data):
        """Helper to process bulk salary payments"""
        if not payments_data:
            raise ValueError("No payment data provided")
        
        transactions = []
        for item in payments_data:
            try:
                receiver = CustomUser.objects.get(id=item['receiver_id'])
            except CustomUser.DoesNotExist:
                raise ValueError(f"Employee with ID {item['receiver_id']} not found")
            
            if not hasattr(receiver, 'hierarchy') or receiver.hierarchy.owner != self.request.user:
                raise ValueError(f"Employee {receiver.get_full_name()} does not belong to your organization")
            
            txn = SalaryTransaction.objects.create(
                receiver=receiver,
                payer=self.request.user,
                amount=Decimal(str(item['amount'])),
                payment_type=item['payment_type'],
                payment_period_start=item['payment_period_start'],
                payment_period_end=item['payment_period_end'],
                payment_method=item.get('payment_method', 'BANK_TRANSFER'),
                note=item.get('note'),
                status='PENDING'
            )
            transactions.append(txn)
        
        return transactions


class MarkSalaryAsPaidView(APIView):
    """
    PUT: Mark a salary transaction as paid
    """
    permission_classes = [IsAuthenticated]
    
    def put(self, request, transaction_id):
        """Mark a salary transaction as paid"""
        try:
            salary_txn = SalaryTransaction.objects.get(transaction_id=transaction_id)
            
            if not request.user.is_superuser and salary_txn.payer != request.user:
                return Response(
                    {"status": "error", "message": "Permission denied"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if salary_txn.status != 'PENDING':
                return Response(
                    {"status": "error", "message": f"Transaction is {salary_txn.status}, cannot mark as paid"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            payment_reference = request.data.get('payment_reference', '')
            salary_txn.status = 'PAID'
            salary_txn.payment_reference = payment_reference
            salary_txn.processed_at = timezone.now()
            salary_txn.save()
            
            return Response(
                {
                    "status": "success",
                    "message": "Salary marked as paid",
                    "data": {
                        "transaction_id": str(salary_txn.transaction_id),
                        "employee": salary_txn.receiver.get_full_name(),
                        "amount": float(salary_txn.amount),
                        "status": salary_txn.status,
                        "processed_at": salary_txn.processed_at.isoformat(),
                        "payment_reference": salary_txn.payment_reference
                    }
                },
                status=status.HTTP_200_OK
            )
        
        except SalaryTransaction.DoesNotExist:
            return Response(
                {"status": "error", "message": "Transaction not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )