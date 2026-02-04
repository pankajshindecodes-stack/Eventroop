from decimal import Decimal
from django.utils import timezone
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def calculate_package_cost(package, start_datetime, end_datetime):
    """
    Calculate the cost of a package for a given period.
    
    This function should be implemented based on your package pricing logic.
    Examples:
    - Fixed monthly cost
    - Daily rate calculation
    - Tiered pricing based on duration
    """
    # Example implementation - adjust based on your Package model
    if hasattr(package, 'monthly_cost'):
        # Calculate number of months
        days = (end_datetime.date() - start_datetime.date()).days
        # Simple calculation: proportion of monthly cost
        cost = package.monthly_cost * Decimal(days) / Decimal(30)
        return cost
    
    # Fallback to base price
    return package.price if hasattr(package, 'price') else Decimal("0.00")


def get_month_boundaries(date):
    """
    Get the first and last day of the month for a given date.
    
    Returns:
        tuple: (month_start, month_end)
    """
    month_start = date.replace(day=1)
    month_end = month_start + relativedelta(months=1) - timedelta(days=1)
    return month_start, month_end


def generate_invoice_for_period(booking, period_start, period_end, discount=Decimal("0.00"), tax_percentage=Decimal("0.00")):
    """
    Generate or update an invoice for a specific period.
    
    Args:
        booking: InvoiceBooking instance
        period_start: datetime
        period_end: datetime
        discount: Decimal discount amount
        tax_percentage: Decimal tax percentage
        
    Returns:
        TotalInvoice instance
    """
    from .models import TotalInvoice
    
    # Calculate costs
    subtotal = calculate_package_cost(booking.package, period_start, period_end)
    tax_amount = (subtotal * tax_percentage) / Decimal("100")
    total_amount = subtotal + tax_amount - discount
    
    # Check if invoice already exists for this period
    invoice, created = TotalInvoice.objects.get_or_create(
        booking=booking,
        period_start=period_start,
        period_end=period_end,
        defaults={
            'patient': booking.patient,
            'user': booking.user,
            'total_amount': total_amount,
            'remaining_amount': total_amount,
            'discount_amount': discount,
            'tax_amount': tax_amount,
            'due_date': timezone.now().date() + timedelta(days=30)
        }
    )
    
    if not created:
        # Update existing invoice
        invoice.total_amount = total_amount
        invoice.remaining_amount = total_amount - invoice.paid_amount
        invoice.discount_amount = discount
        invoice.tax_amount = tax_amount
        invoice.save()
    
    return invoice


def bulk_create_invoices_for_booking(booking, number_of_months, discount=Decimal("0.00"), tax_percentage=Decimal("0.00")):
    """
    Create invoices for a booking spanning multiple months.
    
    Args:
        booking: InvoiceBooking instance (should be parent booking)
        number_of_months: int
        discount: Decimal
        tax_percentage: Decimal
        
    Returns:
        list: Created TotalInvoice instances
    """
    from .models import TotalInvoice
    from django.db import transaction
    
    invoices = []
    start_date = booking.start_datetime.date()
    
    with transaction.atomic():
        for month_offset in range(number_of_months):
            # Calculate period for this month
            period_start = start_date + relativedelta(months=month_offset)
            period_start = period_start.replace(day=1)
            
            period_end = period_start + relativedelta(months=1) - timedelta(days=1)
            
            # Convert to datetime
            period_start_dt = timezone.make_aware(datetime.combine(period_start, datetime.min.time()))
            period_end_dt = timezone.make_aware(datetime.combine(period_end, datetime.max.time()))
            
            # Generate invoice
            invoice = generate_invoice_for_period(
                booking,
                period_start_dt,
                period_end_dt,
                discount,
                tax_percentage
            )
            invoices.append(invoice)
    
    return invoices


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


def auto_generate_monthly_invoices():
    """
    Periodic task to auto-generate invoices for ongoing bookings.
    Can be scheduled using Celery or other task scheduler.
    """
    from .models import InvoiceBooking, BookingStatus
    from django.db.models import Q
    
    # Get all active parent bookings
    active_bookings = InvoiceBooking.objects.filter(
        parent__isnull=True,  # Parent bookings
        status=BookingStatus.CONFIRMED
    )
    
    for booking in active_bookings:
        # Check if invoice exists for current month
        today = timezone.now().date()
        month_start = today.replace(day=1)
        month_end = month_start + relativedelta(months=1) - timedelta(days=1)
        
        from .models import TotalInvoice
        invoice_exists = TotalInvoice.objects.filter(
            booking=booking,
            period_start__date=month_start,
            period_end__date=month_end
        ).exists()
        
        if not invoice_exists:
            # Generate invoice for current month
            generate_invoice_for_period(
                booking,
                timezone.make_aware(datetime.combine(month_start, datetime.min.time())),
                timezone.make_aware(datetime.combine(month_end, datetime.max.time()))
            )