from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from .models import InvoiceBooking, TotalInvoice, Payment


# MAIN SIGNAL: Auto Create Monthly Invoices for Multi-Month Bookings
@receiver(post_save, sender=InvoiceBooking)
def auto_create_monthly_invoices(sender, instance, created, **kwargs):
    """
    Automatically create monthly invoices when booking spans multiple months.
    
    Logic:
    - VENUE/Standalone SERVICE bookings: Create monthly invoices
    - Child SERVICE bookings: Skip (handled by parent)
    - Single month bookings: Create one invoice
    - Multi-month bookings: Create one invoice per month (by end of month)
    
    Example:
    - Booking: Feb 1 - Apr 30 (3 months)
    → Creates 3 invoices:
        1. Feb 1 - Feb 29 (ends by end of month)
        2. Mar 1 - Mar 31 (ends by end of month)
        3. Apr 1 - Apr 30 (ends by end of month)
    """
    
    # Skip if this is a child booking (has parent)
    if instance.parent is not None:
        if created:
            # Trigger parent invoice recalculation
            update_parent_invoices(instance.parent)
        return
    
    # Only create invoices for VENUE or standalone SERVICE
    if instance.booking_entity not in ['VENUE', 'SERVICE']:
        return
    
    # Handle new bookings
    if created:
        try:
            with transaction.atomic():
                _create_monthly_invoices_for_booking(instance)
        except Exception as e:
            print(f"Error creating monthly invoices for booking {instance.id}: {str(e)}")
    
    # Handle updates to existing bookings
    else:
        # Recalculate all associated invoices
        invoices = TotalInvoice.objects.filter(booking=instance)
        for invoice in invoices:
            invoice.recalculate_totals()


@receiver(post_save, sender=Payment)
def update_invoice_on_payment(sender, instance, created, **kwargs):
    """
    When a payment is recorded, recalculate invoice totals and status.
    
    Automatically updates:
    - paid_amount
    - remaining_amount
    - invoice status (UNPAID → PARTIALLY_PAID → PAID)
    - paid_date (when fully paid)
    """
    if created or not instance.is_verified:
        invoice = instance.invoice
        invoice.recalculate_payments()


@receiver(post_save, sender=InvoiceBooking)
def cascade_cancellation_to_invoices(sender, instance, **kwargs):
    """
    When a booking is cancelled, automatically cancel/adjust related invoices.
    """
    if instance.status == 'CANCELLED':
        # Update all invoices for this booking
        invoices = TotalInvoice.objects.filter(booking=instance)
        for invoice in invoices:
            # Mark as cancelled if no payments yet
            if invoice.paid_amount == 0:
                invoice.status = 'CANCELLED'
                invoice.save(update_fields=['status'])
            else:
                # Recalculate with cancelled booking (0 subtotal)
                invoice.recalculate_totals()


# HELPER FUNCTIONS
def _create_monthly_invoices_for_booking(booking):
    """
    Create monthly invoices for a booking that spans multiple months.
    
    For a booking from Feb 1 - Apr 30:
    - Invoice 1: Feb 1 - Feb 29 (February)
    - Invoice 2: Mar 1 - Mar 31 (March)
    - Invoice 3: Apr 1 - Apr 30 (April)
    """
    start_date = booking.start_datetime
    end_date = booking.end_datetime
    
    # Generate list of month periods
    months_to_invoice = _get_month_periods(start_date, end_date)
    invoices_created = []
    
    for period_start, period_end in months_to_invoice:
        # Check if invoice already exists
        existing_invoice = TotalInvoice.objects.filter(
            booking=booking,
            period_start=period_start,
            period_end=period_end
        ).first()
        
        if existing_invoice:
            # Already exists, recalculate
            existing_invoice.recalculate_totals()
            invoices_created.append(existing_invoice)
            continue
        
        # Create new invoice
        invoice = TotalInvoice.objects.create(
            booking=booking,
            period_start=period_start,
            period_end=period_end,
            patient=booking.patient,
            user=booking.user
        )
        
        # Calculate totals
        invoice.recalculate_totals()
        invoices_created.append(invoice)
    
    return invoices_created


def _get_month_periods(start_datetime, end_datetime):
    """
    Split datetime range into monthly periods.
    """

    if start_datetime >= end_datetime:
        return []

    periods = []

    current = start_datetime

    while current < end_datetime:

        # First moment of next month (00:00:00)
        first_next_month = (
            current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            + relativedelta(months=1)
        )

        # End of current month = one second before next month
        month_end = first_next_month - timedelta(seconds=1)

        # Cap to booking end
        period_end = min(month_end, end_datetime)

        periods.append((current, period_end))

        # Next period starts immediately after
        current = period_end + timedelta(seconds=1)

    return periods


def _get_months_count(start_datetime, end_datetime):
    """
    Calculate number of months a booking spans.
    
    Args:
        start_datetime: Booking start datetime
        end_datetime: Booking end datetime
    
    Returns:
        int: Number of months (including partial months)
    
    Example:
        2026-02-15 to 2026-04-25 = 3 months
        2026-02-01 to 2026-02-28 = 1 month
        2026-01-15 to 2026-02-15 = 2 months
    """
    
    months = 0
    current = start_datetime
    
    while current < end_datetime:
        months += 1
        current = current + relativedelta(months=1)
    
    return months


def update_parent_invoices(parent_booking):
    """
    Helper function to update all invoices associated with a parent booking.
    Called when child services are added or modified.
    """
    invoices = TotalInvoice.objects.filter(booking=parent_booking)
    for invoice in invoices:
        invoice.recalculate_totals()


# SIGNAL: Auto Update Child Service Bookings
@receiver(post_save, sender=InvoiceBooking)
def update_invoices_on_child_service_change(sender, instance, created, **kwargs):
    """
    When a child service booking changes, update parent's invoices.
    """
    if instance.parent and not created:
        # This is a child service that was updated
        parent_invoices = TotalInvoice.objects.filter(booking=instance.parent)
        for invoice in parent_invoices:
            invoice.recalculate_totals()


# CONVENIENCE FUNCTIONS FOR MANUAL OPERATIONS
def trigger_invoice_recalculation(booking):
    """
    Manually trigger invoice recalculation for a booking.
    Useful for admin or bulk operations.
    """
    invoices = TotalInvoice.objects.filter(booking=booking)
    for invoice in invoices:
        invoice.recalculate_totals()


def trigger_invoice_recalculation_for_patient(patient):
    """
    Recalculate all invoices for a patient.
    """
    invoices = TotalInvoice.objects.filter(patient=patient)
    for invoice in invoices:
        invoice.recalculate_totals()


def get_booking_invoice_info(booking):
    """
    Get comprehensive invoice information for a booking.
    
    Returns:
        dict: {
            'booking_id': int,
            'months_count': int,
            'month_periods': list,
            'invoices_count': int,
            'invoices': list,
            'total_invoice_amount': Decimal,
            'total_paid': Decimal,
            'total_remaining': Decimal,
        }
    """
    
    months_count = _get_months_count(booking.start_datetime, booking.end_datetime)
    month_periods = _get_month_periods(booking.start_datetime, booking.end_datetime)
    invoices = TotalInvoice.objects.filter(booking=booking)
    
    total_amount = sum(inv.total_amount for inv in invoices)
    total_paid = sum(inv.paid_amount for inv in invoices)
    total_remaining = sum(inv.remaining_amount for inv in invoices)
    
    return {
        'booking_id': booking.id,
        'booking_entity': booking.get_booking_entity_display(),
        'months_count': months_count,
        'month_periods': [
            {
                'period_start': start.isoformat(),
                'period_end': end.isoformat(),
            }
            for start, end in month_periods
        ],
        'invoices_count': invoices.count(),
        'invoices': [
            {
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'period': f"{inv.period_start.date()} - {inv.period_end.date()}",
                'total_amount': str(inv.total_amount),
                'paid_amount': str(inv.paid_amount),
                'remaining_amount': str(inv.remaining_amount),
                'status': inv.get_status_display(),
                'due_date': inv.due_date,
            }
            for inv in invoices.order_by('period_start')
        ],
        'total_invoice_amount': str(total_amount),
        'total_paid': str(total_paid),
        'total_remaining': str(total_remaining),
    }


def regenerate_monthly_invoices(booking, force=False):
    """
    Regenerate all monthly invoices for a booking.
    
    Args:
        booking: InvoiceBooking instance
        force: If True, deletes existing invoices and recreates them
    
    Returns:
        list: Recreated invoices
    """
    
    if force:
        # Delete existing invoices (cascade to payments)
        TotalInvoice.objects.filter(booking=booking).delete()
    
    # Create fresh invoices
    return _create_monthly_invoices_for_booking(booking)


# TODO: ASYNC TASK FOR FUTURE INVOICE GENERATION (Optional Celery)
def create_future_monthly_invoices(booking):
    """
    Can be used as a Celery task to create invoices asynchronously.
    
    Usage with Celery:
    @shared_task
    def async_create_future_invoices(booking_id):
        booking = InvoiceBooking.objects.get(id=booking_id)
        create_future_monthly_invoices(booking)
    
    # Call: async_create_future_invoices.delay(booking.id)
    """
    
    invoices = _create_monthly_invoices_for_booking(booking)
    return invoices


# SIGNAL: Handle Invoice Period Updates
@receiver(pre_save, sender=InvoiceBooking)
def handle_booking_period_change(sender, instance, **kwargs):
    """
    Detect when booking period (start/end datetime) changes.
    This will trigger invoice regeneration.
    """
    
    try:
        old_instance = InvoiceBooking.objects.get(pk=instance.pk)
        
        # Check if period changed
        if (old_instance.start_datetime != instance.start_datetime or 
            old_instance.end_datetime != instance.end_datetime):
            
            # Store flag to handle in post_save
            instance._period_changed = True
    except InvoiceBooking.DoesNotExist:
        pass

@receiver(post_save, sender=InvoiceBooking)
def handle_booking_period_change_post_save(sender, instance, **kwargs):
    """
    Regenerate invoices if booking period was changed.
    """
    
    if hasattr(instance, '_period_changed') and instance._period_changed:
        # Only regenerate if no payments made yet
        invoices = TotalInvoice.objects.filter(booking=instance)
        unpaid_invoices = invoices.filter(paid_amount=0)
        
        if unpaid_invoices.count() == invoices.count():
            # Safe to regenerate
            regenerate_monthly_invoices(instance, force=True)
        else:
            # Has paid invoices, just update unpaid
            for invoice in unpaid_invoices:
                invoice.recalculate_totals()
        
        # Clean up flag
        delattr(instance, '_period_changed')


# SIGNAL: Auto-create Invoices for Future Months (Optional)
def schedule_future_invoice_creation():
    """
    Optional: Schedule invoice creation for upcoming months.
    Use with Django Celery Beat or APScheduler.
    
    This can be called daily to create invoices for the next month
    for active bookings that will span multiple months.
    
    Example Celery Beat task:
    
    # celery.py
    from celery.schedules import crontab
    
    app.conf.beat_schedule = {
        'create-future-invoices': {
            'task': 'invoices.tasks.schedule_future_invoice_creation',
            'schedule': crontab(hour=0, minute=0, day_of_month=28),  # Run on 28th
        },
    }
    """
    
    from django.utils import timezone
    
    today = timezone.now()
    next_month_start = (today.replace(day=1) + relativedelta(months=1)).replace(hour=0, minute=0, second=0)
    next_month_end = (next_month_start + relativedelta(months=1) - timedelta(seconds=1))
    
    # Find bookings that span into next month
    future_bookings = InvoiceBooking.objects.filter(
        end_datetime__gte=next_month_start,
        status__in=['CONFIRMED', 'COMPLETED'],
        parent__isnull=True
    )
    
    invoices_created = 0
    
    for booking in future_bookings:
        # Check if invoice already exists for next month
        existing = TotalInvoice.objects.filter(
            booking=booking,
            period_start__gte=next_month_start,
            period_end__lte=next_month_end
        ).exists()
        
        if not existing:
            # Create invoices for next month
            _create_monthly_invoices_for_booking(booking)
            invoices_created += 1
    
    return {
        'bookings_processed': future_bookings.count(),
        'invoices_created': invoices_created,
        'month': next_month_start.strftime('%B %Y')
    }