from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from .models import TotalInvoice, InvoiceBooking, InvoiceBookingService

@receiver(post_save, sender=InvoiceBooking)
def update_invoice_from_booking(sender, instance, **kwargs):
    try:
        invoice = instance.invoice
    except TotalInvoice.DoesNotExist:
        return

    invoice.recalculate_totals()

@receiver(m2m_changed, sender=TotalInvoice.service_bookings.through)
def update_invoice_from_services(sender, instance, action, **kwargs):
    if action in ("post_add", "post_remove", "post_clear"):
        instance.recalculate_totals()

@receiver(post_save, sender=InvoiceBookingService)
def update_invoice_from_service_change(sender, instance, **kwargs):
    for invoice in instance.invoices.all():
        invoice.recalculate_totals()
