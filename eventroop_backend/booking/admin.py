
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib.admin.decorators import display
from .models import *


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('building_name', 'city', 'location_type', 'postal_code')
    list_filter = ('location_type', 'city', 'state')
    search_fields = ('building_name', 'city', 'address_line1')
    readonly_fields = ('full_address',)
    
    fieldsets = (
        ('Location Details', {
            'fields': ('location_type', 'user')
        }),
        ('Address', {
            'fields': ('building_name', 'address_line1', 'address_line2', 'locality', 'city', 'state', 'postal_code', 'full_address')
        }),
    )

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'package_type', 'period', 'price', 'is_active')
    list_filter = ('package_type', 'period', 'is_active', 'created_at')
    search_fields = ('name', 'owner__email')
    readonly_fields = ('belongs_to','created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'owner')
        }),
        ('Package Details', {
            'fields': ('package_type', 'period', 'price', 'is_active')
        }),
        ('Polymorphic Relation', {
            'fields': ('content_type', 'object_id','belongs_to'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return self.readonly_fields + ('content_type', 'object_id')
        return self.readonly_fields

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'email', 'phone', 'gender', 'blood_group', 'registration_date')
    list_filter = ('gender', 'blood_group', 'registration_date', 'id_proof')
    search_fields = ('first_name', 'last_name', 'email', 'phone')
    readonly_fields = ('registration_date', 'updated_at', 'get_total_payment')
    date_hierarchy = 'registration_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('first_name', 'last_name', 'email', 'registered_by')
        }),
        ('Contact Information', {
            'fields': ('phone', 'address', 'age')
        }),
        ('Emergency Contacts', {
            'fields': ('emergency_contact', 'emergency_phone', 'emergency_contact_2', 'emergency_phone_2')
        }),
        ('Medical Information', {
            'fields': ('gender', 'blood_group', 'medical_conditions', 'allergies', 'present_health_condition', 'preferred_language')
        }),
        ('Identification', {
            'fields': ('id_proof', 'id_proof_number', 'patient_documents')
        }),
        ('Professional Background', {
            'fields': ('education_qualifications', 'earlier_occupation', 'year_of_retirement'),
            'classes': ('collapse',)
        }),
        ('Payment Information', {
            'fields': ('registration_fee', 'advance_payment', 'payment_mode', 'get_total_payment')
        }),
        ('Metadata', {
            'fields': ('registration_date', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Full Name'

# ========================= CUSTOM FILTERS =========================
class StatusFilter(admin.SimpleListFilter):
    """Custom filter for invoice status with counts"""
    title = 'Invoice Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        statuses = [
            (InvoiceStatus.UNPAID, 'Unpaid'),
            (InvoiceStatus.PARTIALLY_PAID, 'Partially Paid'),
            (InvoiceStatus.PAID, 'Paid'),
            (InvoiceStatus.OVERDUE, 'Overdue'),
            (InvoiceStatus.DRAFT, 'Draft'),
            (InvoiceStatus.CANCELLED, 'Cancelled'),
        ]
        return statuses

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class OverdueFilter(admin.SimpleListFilter):
    """Filter to show overdue invoices"""
    title = 'Payment Status'
    parameter_name = 'overdue'

    def lookups(self, request, model_admin):
        return [
            ('overdue', 'Overdue'),
            ('due_soon', 'Due Soon (7 days)'),
            ('on_time', 'On Time'),
        ]

    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == 'overdue':
            return queryset.filter(
                due_date__lt=today,
                status__in=[InvoiceStatus.UNPAID, InvoiceStatus.PARTIALLY_PAID]
            )
        elif self.value() == 'due_soon':
            from datetime import timedelta
            soon = today + timedelta(days=7)
            return queryset.filter(
                due_date__lte=soon,
                due_date__gte=today,
                status__in=[InvoiceStatus.UNPAID, InvoiceStatus.PARTIALLY_PAID]
            )
        elif self.value() == 'on_time':
            return queryset.filter(
                due_date__gte=today,
                status__in=[InvoiceStatus.UNPAID, InvoiceStatus.PARTIALLY_PAID]
            )
        return queryset


class PaymentMethodFilter(admin.SimpleListFilter):
    """Filter payments by method"""
    title = 'Payment Method'
    parameter_name = 'method'

    def lookups(self, request, model_admin):
        return PaymentMethod.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(method=self.value())
        return queryset


class DateRangeFilter(admin.SimpleListFilter):
    """Filter by date range"""
    title = 'Date Range'
    parameter_name = 'date_range'

    def lookups(self, request, model_admin):
        return [
            ('today', 'Today'),
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('quarter', 'This Quarter'),
        ]

    def queryset(self, request, queryset):
        from datetime import timedelta
        today = timezone.now().date()
        
        if self.value() == 'today':
            return queryset.filter(created_at__date=today)
        elif self.value() == 'week':
            week_start = today - timedelta(days=today.weekday())
            return queryset.filter(created_at__date__gte=week_start)
        elif self.value() == 'month':
            month_start = today.replace(day=1)
            return queryset.filter(created_at__date__gte=month_start)
        elif self.value() == 'quarter':
            quarter_start = today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
            return queryset.filter(created_at__date__gte=quarter_start)
        return queryset


# ========================= INLINE ADMINS =========================
class InvoiceBookingServiceInline(admin.TabularInline):
    """Inline admin for services within a booking"""
    model = InvoiceBookingService
    extra = 1
    fields = (
        'service',
        'service_package',
        'start_datetime',
        'end_datetime',
        'subtotal',
        'status'
    )
    readonly_fields = ('subtotal', 'invoice_number', 'created_at')
    can_delete = True

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('service', 'service_package')


class PaymentInline(admin.TabularInline):
    """Inline admin for payments within an invoice"""
    model = Payment
    extra = 1
    fields = ('patient', 'amount', 'method', 'reference', 'created_at')
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('patient')


# ========================= INVOICE BOOKING ADMIN =========================
@admin.register(InvoiceBooking)
class InvoiceBookingAdmin(admin.ModelAdmin):
    """Admin interface for Invoice Bookings"""
    
    # Display Configuration
    list_display = (
        'invoice_number',
        'patient',
        'venue',
        'start_datetime',
        'end_datetime',
        'subtotal',
        'status'
    )
    
    list_filter = (
        'status',
        'created_at',
        DateRangeFilter,
        'venue',
        'user'
    )
    
    search_fields = (
        'invoice_number',
        'patient__name',
        'patient__email',
        'venue__name',
        'user__email'
    )
    
    # Form Configuration
    fieldsets = (
        ('Booking Information', {
            'fields': (
                'invoice_number',
                'user',
                'patient',
                'venue',
                'venue_package'
            ),
            'description': 'Core booking details'
        }),
        ('Dates & Duration', {
            'fields': (
                'start_datetime',
                'end_datetime',
            ),
            'description': 'When is the booking scheduled?'
        }),
        ('Financial Details', {
            'fields': ('subtotal',),
            'description': 'Automatically calculated based on package and duration'
        }),
        ('Status & Tracking', {
            'fields': (
                'status',
                'created_at',
                'updated_at'
            ),
            'description': 'Current status and timestamps'
        }),
    )
    
    readonly_fields = (
        'invoice_number',
        'subtotal',
        'created_at',
        'updated_at'
    )
    
    inlines = [InvoiceBookingServiceInline]
    
    # Actions
    actions = [
        'mark_as_booked',
        'mark_as_in_progress',
        'mark_as_fulfilled',
        'mark_as_cancelled',
        'export_as_csv'
    ]
    
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        """Optimize queries"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'patient',
            'venue',
            'user',
            'venue_package'
        ).prefetch_related('services')
    

    
    # Actions
    @admin.action(description='Mark selected as Booked')
    def mark_as_booked(self, request, queryset):
        updated = queryset.update(status=InvoiceBookingStatus.BOOKED)
        self.message_user(request, f'{updated} bookings marked as booked.')
    
    @admin.action(description='Mark selected as In Progress')
    def mark_as_in_progress(self, request, queryset):
        updated = queryset.update(status=InvoiceBookingStatus.IN_PROGRESS)
        self.message_user(request, f'{updated} bookings marked as in progress.')
    
    @admin.action(description='Mark selected as Fulfilled')
    def mark_as_fulfilled(self, request, queryset):
        updated = queryset.update(status=InvoiceBookingStatus.FULFILLED)
        self.message_user(request, f'{updated} bookings marked as fulfilled.')
    
    @admin.action(description='Mark selected as Cancelled')
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status=InvoiceBookingStatus.CANCELLED)
        self.message_user(request, f'{updated} bookings marked as cancelled.')
    
    @admin.action(description='Export to CSV')
    def export_as_csv(self, request, queryset):
        """Export selected bookings to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="bookings.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Invoice Number',
            'Patient',
            'Venue',
            'Start DateTime',
            'End DateTime',
            'Subtotal',
            'Status'
        ])
        
        for booking in queryset:
            writer.writerow([
                booking.invoice_number,
                booking.patient.name if booking.patient else '-',
                booking.venue.name if booking.venue else '-',
                booking.start_datetime,
                booking.end_datetime,
                booking.subtotal,
                booking.get_status_display()
            ])
        
        return response


# ========================= INVOICE BOOKING SERVICE ADMIN =========================
@admin.register(InvoiceBookingService)
class InvoiceBookingServiceAdmin(admin.ModelAdmin):
    """Admin interface for Invoice Booking Services"""
    
    list_display = (
        'invoice_number',
        'service',
        'booking',
        'start_datetime',
        'end_datetime',
        'subtotal',
        'status'
    )
    
    list_filter = (
        'status',
        'created_at',
        DateRangeFilter,
        'service'
    )
    
    search_fields = (
        'invoice_number',
        'service__name',
        'booking__invoice_number'
    )
    
    fieldsets = (
        ('Patient & Booker', {
            'fields': (
                'patient',
                'user',
            )
        }),
        ('Service Information', {
            'fields': (
                'invoice_number',
                'booking',
                'service',
                'service_package'
            )
        }),
        ('Dates & Duration', {
            'fields': (
                'start_datetime',
                'end_datetime',
            )
        }),
        ('Financial Details', {
            'fields': ('subtotal',)
        }),
        ('Status', {
            'fields': ('status',)
        }),
    )
    
    readonly_fields = (
        'invoice_number',
        'subtotal',
        'created_at',
        'updated_at'
    )
    
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        """Optimize queries"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'booking',
            'service',
            'service_package'
        )
    



# ========================= TOTAL INVOICE ADMIN =========================
@admin.register(TotalInvoice)
class TotalInvoiceAdmin(admin.ModelAdmin):
    """Admin interface for Total Invoices with advanced features"""
    
    list_display = (
        'patient',
        'user',
        'total_amount',
        'paid_amount',
        'remaining_amount',
        'status',
        'due_date'
    )
    
    list_filter = (
        StatusFilter,
        OverdueFilter,
        DateRangeFilter,
        'created_at',
        'user'
    )
    
    search_fields = (
        'booking__invoice_number',
        'patient__name',
        'patient__email',
        'user__email'
    )
    
    fieldsets = (
        ('Invoice Information', {
            'fields': (
                'booking',
                'patient',
                'user',
            ),
            'description': 'Core invoice details'
        }),
        ('Financial Summary', {
            'fields': (
                'total_amount',
                'paid_amount',
                'remaining_amount',
            ),
            'description': 'Amounts are automatically calculated',
            'classes': ('wide',)
        }),
        ('Services', {
            'fields': ('service_bookings',),
            'description': 'Associated services'
        }),
        ('Status & Dates', {
            'fields': (
                'status',
                'due_date',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = (
        'total_amount',
        'paid_amount',
        'remaining_amount',
        'created_at',
        'updated_at'
    )
    
    filter_horizontal = ('service_bookings',)
    
    inlines = [PaymentInline]
    
    actions = [
        'mark_as_pending',
        'send_payment_reminder',
        'export_unpaid_invoices'
    ]
    
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        """Optimize queries with prefetch"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'booking',
            'patient',
            'user'
        ).prefetch_related(
            'service_bookings',
            'payments'
        )
    

    
    # Custom Actions
    @admin.action(description='Mark as Unpaid')
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status=InvoiceStatus.UNPAID)
        self.message_user(request, f'{updated} invoices marked as pending.')
    
    @admin.action(description='Send Payment Reminder')
    def send_payment_reminder(self, request, queryset):
        """Send payment reminders to selected invoices"""
        # Implement your email sending logic here
        count = queryset.count()
        self.message_user(request, f'Payment reminders sent for {count} invoices.')
    
    @admin.action(description='Export Unpaid Invoices')
    def export_unpaid_invoices(self, request, queryset):
        """Export unpaid invoices to CSV"""
        import csv
        from django.http import HttpResponse
        
        unpaid = queryset.exclude(status=InvoiceStatus.PAID)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="unpaid_invoices.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Invoice Number',
            'Patient',
            'Total Amount',
            'Paid Amount',
            'Remaining Amount',
            'Status',
            'Due Date'
        ])
        
        for invoice in unpaid:
            writer.writerow([
                invoice.booking.invoice_number,
                invoice.patient.name,
                invoice.total_amount,
                invoice.paid_amount,
                invoice.remaining_amount,
                invoice.get_status_display(),
                invoice.due_date
            ])
        
        return response


# ========================= PAYMENT ADMIN =========================
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin interface for Payments"""
    
    list_display = (
        'id',
        'invoice',
        'patient',
        'amount',
        'method',
        'reference',
        'created_at'
    )
    
    list_filter = (
        PaymentMethodFilter,
        DateRangeFilter,
        'created_at',
        'method'
    )
    
    search_fields = (
        'invoice__booking__invoice_number',
        'patient__name',
        'patient__email',
        'reference'
    )
    
    fieldsets = (
        ('Payment Details', {
            'fields': (
                'invoice',
                'patient',
                'amount',
                'method',
            )
        }),
        ('Reference', {
            'fields': ('reference',),
            'description': 'Transaction ID, check number, or reference number'
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = (
        'created_at',
        'updated_at'
    )
    
    actions = [
        'export_payments',
        'send_receipt'
    ]
    
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        """Optimize queries"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'invoice',
            'patient'
        )
    

    
    @admin.action(description='Export Payments')
    def export_payments(self, request, queryset):
        """Export payments to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Payment ID',
            'Invoice',
            'Patient',
            'Amount',
            'Method',
            'Reference',
            'Date'
        ])
        
        for payment in queryset:
            writer.writerow([
                payment.id,
                payment.invoice.booking.invoice_number,
                payment.patient.name,
                payment.amount,
                payment.get_method_display(),
                payment.reference,
                payment.created_at
            ])
        
        return response
    
    @admin.action(description='Send Receipt')
    def send_receipt(self, request, queryset):
        """Send payment receipts"""
        count = queryset.count()
        self.message_user(request, f'Receipts sent for {count} payments.')


# ========================= ADMIN SITE CUSTOMIZATION =========================
admin.site.site_header = "Invoice Management System"
admin.site.site_title = "IMS Admin"
admin.site.index_title = "Welcome to Invoice Management System"