# # booking/signals.py
# from decimal import Decimal
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.db import transaction
# from .models import Booking, InvoiceTransaction


# @receiver(post_save, sender=Booking)
# def create_invoice_on_booking(sender, instance, created, **kwargs):
#     """
#     Create invoice(s) automatically when booking is created:
#     - If booking has venue: create single invoice with all services
#     - If booking has only services: create separate invoices per service
#     """
#     if not created:
#         return

#     booking = instance
#     invoices = []

#     with transaction.atomic():
#         if booking.venue:
#             # Create single invoice for venue with all services
#             venue_amount = booking.venue_amount  # from booking calculation
#             all_services = booking.booking_services.all()

#             services_amount = sum(
#                 bs.total_price for bs in all_services
#             ) or Decimal("0.00")

#             invoice = InvoiceTransaction.objects.create(
#                 booking=booking,
#                 invoice_for=InvoiceTransaction.InvoiceFor.VENUE,
#                 subtotal=venue_amount + services_amount,
#                 discount=booking.discount or Decimal("0.00"),
#                 tax=booking.tax or Decimal("0.00"),
#                 total_amount=0,  # calculated in save()
#                 created_by=booking.created_by
#             )
#             invoice.service_bookings.set(all_services)
#             invoices.append(invoice)

#         else:
#             # Create separate invoice for each service booking
#             service_bookings = booking.booking_services.all()

#             for service_booking in service_bookings:
#                 invoice = InvoiceTransaction.objects.create(
#                     booking=booking,
#                     invoice_for=InvoiceTransaction.InvoiceFor.SERVICE,
#                     subtotal=service_booking.total_price,
#                     discount=service_booking.discount or Decimal("0.00"),
#                     tax=service_booking.tax or Decimal("0.00"),
#                     total_amount=0,  # calculated in save()
#                     created_by=booking.created_by
#                 )
#                 invoice.service_bookings.add(service_booking)
#                 invoices.append(invoice)

