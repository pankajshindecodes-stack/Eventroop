from django.db import transaction
from decimal import Decimal
from .models import SalaryTransaction

class SalaryPaymentService:
    """Service class to handle salary transaction creation and tracking."""
    
    @staticmethod
    def create_salary_transaction(
        receiver,
        payer,
        amount,
        payment_type,
        payment_period_start,
        payment_period_end,
        payment_method="CASH",
        payment_reference=None,
        note=None,
        attachment=None
    ):
        """
        Create a salary transaction.
        
        Args:
            receiver: CustomUser (employee receiving salary)
            payer: CustomUser (employer/owner paying salary)
            amount: Decimal (salary amount)
            payment_type: Payment frequency (MONTHLY, FORTNIGHTLY, WEEKLY, DAILY, HOURLY)
            payment_period_start: Start date of salary period
            payment_period_end: End date of salary period
            payment_method: Payment method (BANK_TRANSFER, CHECK, CASH, UPI, OTHER)
            payment_reference: Bank transaction ID, check number, UTR, etc.
            note: Additional notes
            attachment: Payment receipt/proof file
            
        Returns:
            SalaryTransaction instance
        """
        
        if amount <= 0:
            raise ValueError("Salary amount must be greater than 0")
        
        if payment_period_end < payment_period_start:
            raise ValueError("Payment period end date must be >= start date")
        
        with transaction.atomic():
            salary_txn = SalaryTransaction.objects.create(
                receiver=receiver,
                payer=payer,
                amount=amount,
                payment_type=payment_type,
                payment_period_start=payment_period_start,
                payment_period_end=payment_period_end,
                payment_method=payment_method,
                payment_reference=payment_reference,
                note=note or f"Salary for {receiver.get_full_name()} ({payment_period_start} to {payment_period_end})",
                attachment=attachment,
                status="PENDING"
            )
            
            return salary_txn
    
    @staticmethod
    def mark_as_processing(salary_txn):
        """Mark salary transaction as processing."""
        salary_txn.mark_as_processing()
        return salary_txn
    
    @staticmethod
    def mark_as_paid(salary_txn, payment_reference=None):
        """
        Mark salary transaction as successfully paid.
        
        Args:
            salary_txn: SalaryTransaction instance
            payment_reference: Bank transaction ID, UTR, check number, etc.
        """
        salary_txn.mark_as_paid(payment_reference=payment_reference)
        return salary_txn
    
    @staticmethod
    def mark_as_failed(salary_txn, reason=""):
        """
        Mark salary transaction as failed.
        
        Args:
            salary_txn: SalaryTransaction instance
            reason: Reason for failure
        """
        salary_txn.mark_as_failed(reason=reason)
        return salary_txn
    
    @staticmethod
    def cancel_salary_transaction(salary_txn, reason=""):
        """Cancel a salary transaction."""
        if salary_txn.status != "PENDING":
            raise ValueError("Only pending transactions can be cancelled")
        
        salary_txn.status = "CANCELLED"
        if reason:
            salary_txn.note = f"Cancelled: {reason}"
        salary_txn.save()
        return salary_txn
    
    @staticmethod
    def process_bulk_salary_payments(payments_data, payer):
        """
        Process multiple salary payments at once.
        
        Args:
            payments_data: List of dicts with payment information
            payer: CustomUser (employer paying)
            
        Returns:
            List of created SalaryTransaction instances
        """
        transactions = []
        
        with transaction.atomic():
            for data in payments_data:
                salary_txn = SalaryPaymentService.create_salary_transaction(
                    receiver=data['receiver'],
                    payer=payer,
                    amount=Decimal(str(data['amount'])),
                    payment_type=data['payment_type'],
                    payment_period_start=data['payment_period_start'],
                    payment_period_end=data['payment_period_end'],
                    payment_method=data.get('payment_method', 'BANK_TRANSFER'),
                    note=data.get('note'),
                )
                transactions.append(salary_txn)
        
        return transactions
    
    @staticmethod
    def get_pending_salaries(employee=None, employer=None):
        """Get all pending salary transactions."""
        query = SalaryTransaction.objects.filter(status="PENDING")
        
        if employee:
            query = query.filter(receiver=employee)
        if employer:
            query = query.filter(payer=employer)
        
        return query.order_by("payment_period_start")
    
    @staticmethod
    def get_salary_history(employee, start_date=None, end_date=None):
        """Get salary payment history for an employee."""
        query = SalaryTransaction.objects.filter(receiver=employee)
        
        if start_date:
            query = query.filter(payment_period_start__gte=start_date)
        if end_date:
            query = query.filter(payment_period_end__lte=end_date)
        
        return query.order_by("-payment_period_start")
