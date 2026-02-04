from django.db import models

class BookingType(models.TextChoices):
        IN_HOUSE = 'IN_HOUSE', 'In House'
        OPD = 'OPD', 'OPD'
        CLIENT_SIDE = 'CLIENT_SIDE', 'Client Side'
    
class PeriodChoices(models.TextChoices):
    HOURLY = "HOURLY", "Hourly"
    DAILY = "DAILY", "Daily"
    MONTHLY = "MONTHLY", "Monthly"

class BookingEntity(models.TextChoices):
    VENUE = "VENUE", "Venue"
    SERVICE = "SERVICE", "Service"
    RESOURCE = "RESOURCE", "Resource"

class BookingStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    BOOKED = 'BOOKED', 'Booked'
    DELAYED = 'DELAYED', 'Delayed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    FULFILLED = 'FULFILLED', 'Fulfilled'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    YET_TO_BE_STARTED = 'YET_TO_BE_STARTED', 'Yet To Be Started'
    PARTIALLY_FULFILLED = 'PARTIALLY_FULFILLED', 'Partially Fulfilled'

class InvoiceStatus(models.TextChoices):
    UNPAID = 'UNPAID', 'Unpaid'
    PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
    PAID = 'PAID', 'Paid'
    OVERDUE = 'OVERDUE', 'Overdue'
    CANCELLED = 'CANCELLED', 'Cancelled'
    REFUNDED = 'REFUNDED', 'Refunded'

class PaymentMethod(models.TextChoices):
    CASH = 'CASH', 'Cash'
    UPI = 'UPI', 'UPI'
    CARD = 'CARD', 'Card'
    BANK = 'BANK', 'Bank'
    CHEQUE = 'CHEQUE', 'Cheque'
