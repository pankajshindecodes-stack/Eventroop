import calendar
from datetime import date, timedelta
from django.db.models import Sum
from decimal import Decimal

class AttendanceCalculator:
    """Calculate attendance metrics for a user over a period."""

    def __init__(self, user, start_date=None, end_date=None):
        self.user = user
        self.start_date = start_date
        self.end_date = end_date
        self.records = self._get_records()
        self.status_codes = self._load_status_codes()

    def _get_records(self):
        """Get attendance records for the period."""
        from .models import Attendance
        
        query = Attendance.objects.filter(user=self.user)
        
        if self.start_date and self.end_date:
            query = query.filter(
                date__gte=self.start_date,
                date__lte=self.end_date
            )
        
        return query

    def _load_status_codes(self):
        """Load attendance status codes."""
        from .models import AttendanceStatus
        status_query = AttendanceStatus.objects.filter(owner__is_superuser=True)

        return {
            'absent': status_query.filter(code__icontains="ABSENT",is_active=True).first(),
            'present': status_query.filter(code__icontains="PRESENT",is_active=True).first(),
            'paid_leave': status_query.filter(code__icontains="PAID-LEAVE",is_active=True).first(),
            'half_day': status_query.filter(code__icontains="HALF-DAY",is_active=True).first(),
            'weekly_Off': status_query.filter(code__icontains="WEEKLY-OFF",is_active=True).first(),
            'unpaid_leave': status_query.filter(code__icontains="UNPAID-LEAVE",is_active=True).first(),
        }

    def _count_status(self, status_obj):
        """Count records for a specific status."""
        if not status_obj:
            return 0
        return self.records.filter(status=status_obj).count()

    def _calculate_total_hours(self):
        """Calculate total hours worked."""
        duration_sum = self.records.aggregate(total=Sum("duration"))["total"]
        
        if not duration_sum:
            return Decimal("0")
        
        total_seconds = duration_sum.total_seconds()
        return Decimal(total_seconds) / Decimal(3600)

    def calculate(self):
        """Calculate all attendance metrics."""        
        absent = self._count_status(self.status_codes['absent'])
        present = self._count_status(self.status_codes['present'])
        paid_leave = self._count_status(self.status_codes['paid_leave'])
        half_day = self._count_status(self.status_codes['half_day'])
        weekly_Off = self._count_status(self.status_codes['weekly_Off'])
        unpaid_leave = self._count_status(self.status_codes['unpaid_leave'])
        total_hours = self._calculate_total_hours()

        payable_days = present + paid_leave + (Decimal("0.5") * half_day)

        return {
            "present_days": present,
            "absent_days": absent,
            "half_day_count": half_day,
            "paid_leave_days": paid_leave,
            "weekly_Offs": weekly_Off,
            "unpaid_leaves": unpaid_leave,
            "total_payable_days": float(payable_days),
            "total_payable_hours": float(total_hours),
        }


class SalaryCalculator:
    """Calculate salary based on attendance and salary structure."""

    HOURS_PER_DAY = 8
    DAYS_PER_WEEK = 7
    DAYS_PER_FORTNIGHT = 15
    DAYS_PER_MONTH = 30

    def __init__(self, user, salary_structure):
        self.user = user
        self.salary = salary_structure

    def _salary_type(self):
        return self.salary.salary_type if self.salary else "MONTHLY"

    def get_period(self):
        today = date.today()
        stype = self._salary_type()

        if stype == "DAILY":
            return today, today

        if stype == "WEEKLY":
            start = today - timedelta(days=today.weekday())
            return start, start + timedelta(days=6)

        if stype == "FORTNIGHTLY":
            start = today - timedelta(days=today.weekday())
            return start, start + timedelta(days=14)

        if stype == "MONTHLY":
            year, month = today.year, today.month
            first = date(year, month, 1)
            last = date(year, month, calendar.monthrange(year, month)[1])
            return first, last

        return today, today

    def _daily_rate(self):
        if not self.salary:
            return Decimal("0")

        final_salary = Decimal(self.salary.final_salary)
        stype = self._salary_type()

        rate_map = {
            "HOURLY": final_salary * self.HOURS_PER_DAY,
            "DAILY": final_salary,
            "WEEKLY": final_salary / self.DAYS_PER_WEEK,
            "FORTNIGHTLY": final_salary / self.DAYS_PER_FORTNIGHT,
            "MONTHLY": final_salary / self.DAYS_PER_MONTH,
        }

        return round(rate_map.get(stype, final_salary / self.DAYS_PER_MONTH),2)

    def calculate_salary(self, payable_days):
        daily_rate = self._daily_rate()
        return round(Decimal(payable_days) * daily_rate, 2)

    def calculate_remaining_days(self, payable_days):
        start, end = self.get_period()
        total_days = (end - start).days + 1
        return max(0, total_days - int(payable_days))

    def calculate_remaining_salary(self, payable_days):
        remaining_days = self.calculate_remaining_days(payable_days)
        return round(Decimal(remaining_days) * self._daily_rate(), 2)
