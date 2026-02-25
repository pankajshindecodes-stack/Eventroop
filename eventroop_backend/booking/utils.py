from decimal import Decimal
from django.utils import timezone
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from .constants import BookingStatus

def get_month_boundaries(date):
    """
    Get the first and last day of the month for a given date.
    
    Returns:
        tuple: (month_start, month_end)
    """
    month_start = date.replace(day=1)
    month_end = month_start + relativedelta(months=1) - timedelta(days=1)
    return month_start, month_end

def calculate_outstanding_balance(user):
    """
    Calculate total outstanding balance for a user across all invoices.
    
    Args:
        user: CustomUser instance
        
    Returns:
        Decimal: Total outstanding amount
    """
    from .models import TotalInvoice
    
    total = TotalInvoice.objects.filter(
        user=user,
        status__in=['UNPAID', 'PARTIALLY_PAID']
    ).values_list('remaining_amount', flat=True)
    
    return sum(total, Decimal("0.00"))


def get_invoices_due_soon(days=7):
    """
    Get all invoices due within specified days.
    
    Args:
        days: int number of days
        
    Returns:
        QuerySet of TotalInvoice instances
    """
    from .models import TotalInvoice
    from django.db.models import Q
    
    today = timezone.now().date()
    due_date = today + timedelta(days=days)
    
    return TotalInvoice.objects.filter(
        Q(due_date__lte=due_date) & Q(due_date__gte=today),
        status__in=['UNPAID', 'PARTIALLY_PAID']
    )


def send_invoice_reminder(invoice):
    """
    Send invoice reminder to patient/user.
    
    Args:
        invoice: TotalInvoice instance
    """
    # Implement your email/notification logic here
    # Example: send_email(invoice.user.email, "Invoice Reminder", template_context)
    pass

def auto_update_status(start_datetime,end_datetime):
    now = timezone.now()
    status =  BookingStatus.DRAFT
    if now < start_datetime:
        status = BookingStatus.YET_TO_START
    elif start_datetime <= now <= end_datetime:
        status = BookingStatus.IN_PROGRESS
    elif now > end_datetime:
        status = BookingStatus.UNFULFILLED
    return status
   

def generate_order_id(instance):
    """
    Generates hierarchical order_id:
    
    PrimaryOrder   → 00001
    SecondaryOrder → 00001-00002
    TernaryOrder   → 00001-00002-00003
    """

    if not instance.id:
        raise ValueError("Instance must be saved before generating order_id")

    # TernaryOrder
    if hasattr(instance, "secondary_order") and instance.secondary_order:
        parent = instance.secondary_order
        return f"{parent.order_id}-{instance.id:05}"

    # SecondaryOrder
    if hasattr(instance, "primary_order") and instance.primary_order:
        parent = instance.primary_order
        return f"{parent.order_id}-{instance.id:05}"

    # PrimaryOrder
    return f"{instance.id:05}"