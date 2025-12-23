from datetime import date, timedelta
from django.db.models import Sum
from decimal import Decimal

class AttendanceCalculator:
    """Calculate attendance metrics for a user over a period."""

    SALARY_TYPE_DAILY = "DAILY"
    SALARY_TYPE_WEEKLY = "WEEKLY"
    SALARY_TYPE_FORTNIGHTLY = "FORTNIGHTLY"
    SALARY_TYPE_MONTHLY = "MONTHLY"
    SALARY_TYPE_HOURLY = "HOURLY"

    STATUS_PRESENT = "P"
    STATUS_ABSENT = "A"
    STATUS_HALF_DAY = "HD"
    STATUS_PAID_LEAVE = "PL"

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
        
        return {
            'present': AttendanceStatus.objects.filter(code__iexact=self.STATUS_PRESENT).first(),
            'absent': AttendanceStatus.objects.filter(code__iexact=self.STATUS_ABSENT).first(),
            'half_day': AttendanceStatus.objects.filter(code__iexact=self.STATUS_HALF_DAY).first(),
            'paid_leave': AttendanceStatus.objects.filter(code__iexact=self.STATUS_PAID_LEAVE).first(),
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
        present = self._count_status(self.status_codes['present'])
        absent = self._count_status(self.status_codes['absent'])
        half_day = self._count_status(self.status_codes['half_day'])
        paid_leave = self._count_status(self.status_codes['paid_leave'])
        total_hours = self._calculate_total_hours()

        payable_days = present + paid_leave + (Decimal("0.5") * half_day)

        return {
            "present_days": present,
            "absent_days": absent,
            "half_day_count": half_day,
            "paid_leave_days": paid_leave,
            "total_payable_days": float(payable_days),
            "total_payable_hours": float(total_hours),
        }


class SalaryCalculator:
    """Calculate salary and remaining payable days."""

    HOURS_PER_DAY = 8
    WORKING_DAYS_PER_WEEK = 6
    WORKING_DAYS_PER_FORTNIGHT = 12
    DAYS_PER_MONTH = 30

    def __init__(self, user, salary_structure):
        self.user = user
        self.salary_structure = salary_structure

    def _get_salary_type(self):
        """Get salary type with fallback."""
        return self.salary_structure.salary_type if self.salary_structure else "MONTHLY"

    def get_period(self):
        """Get period start and end dates based on salary type."""
        today = date.today()
        salary_type = self._get_salary_type()

        if salary_type == "DAILY":
            return today, today + timedelta(days=1)

        if salary_type == "WEEKLY":
            start = today - timedelta(days=today.weekday())
            return start, start + timedelta(days=7)

        if salary_type == "FORTNIGHTLY":
            start = today - timedelta(days=today.weekday())
            return start, start + timedelta(days=14)

        # MONTHLY
        start = date(today.year, today.month, 1)
        return start, start + timedelta(days=30)

    def _get_daily_rate(self):
        """Calculate daily rate based on salary type."""
        if not self.salary_structure or not self.salary_structure.rate:
            return 0

        rate = float(self.salary_structure.rate)
        salary_type = self._get_salary_type()

        rate_map = {
            "HOURLY": rate * self.HOURS_PER_DAY,
            "DAILY": rate,
            "WEEKLY": rate / self.WORKING_DAYS_PER_WEEK,
            "FORTNIGHTLY": rate / self.WORKING_DAYS_PER_FORTNIGHT,
            "MONTHLY": rate / self.DAYS_PER_MONTH,
        }

        return rate_map.get(salary_type, rate / self.DAYS_PER_MONTH)

    def _get_period_total_days(self, start_date, end_date):
        """Calculate total days in a period."""
        return (end_date - start_date).days + 1

    def calculate_salary(self, payable_days):
        """Calculate current salary based on payable days."""
        if not self.salary_structure:
            return 0

        daily_rate = self._get_daily_rate()
        return round(float(payable_days) * daily_rate, 2)

    def calculate_remaining_days(self, payable_days):
        """Calculate remaining payable days in the period."""
        if not self.salary_structure:
            return 0

        start_date, end_date = self.get_period()
        total_days = self._get_period_total_days(start_date, end_date)
        return max(0, total_days - payable_days)

    def calculate_remaining_salary(self, payable_days):
        """Calculate remaining salary potential for remaining days."""
        if not self.salary_structure:
            return 0

        remaining_days = self.calculate_remaining_days(payable_days)
        daily_rate = self._get_daily_rate()
        return round(remaining_days * daily_rate, 2)

    """Calculate salary and remaining payable days."""

    HOURS_PER_DAY = 8
    WORKING_DAYS_PER_WEEK = 6
    WORKING_DAYS_PER_FORTNIGHT = 12
    DAYS_PER_MONTH = 30

    def __init__(self, user, salary_structure):
        self.user = user
        self.salary_structure = salary_structure

    def _get_salary_type(self):
        """Get salary type with fallback."""
        return self.salary_structure.salary_type if self.salary_structure else "MONTHLY"

    def get_period(self):
        """Get period start and end dates based on salary type."""
        today = date.today()
        salary_type = self._get_salary_type()

        if salary_type == "DAILY":
            return today, today + timedelta(days=1)

        if salary_type == "WEEKLY":
            start = today - timedelta(days=today.weekday())
            return start, start + timedelta(days=7)

        if salary_type == "FORTNIGHTLY":
            start = today - timedelta(days=today.weekday())
            return start, start + timedelta(days=14)

        # MONTHLY
        start = date(today.year, today.month, 1)
        return start, start + timedelta(days=30)

    def _get_daily_rate(self):
        """Calculate daily rate based on salary type."""
        if not self.salary_structure or not self.salary_structure.rate:
            return 0

        rate = float(self.salary_structure.rate)
        salary_type = self._get_salary_type()

        rate_map = {
            "HOURLY": rate * self.HOURS_PER_DAY,
            "DAILY": rate,
            "WEEKLY": rate / self.WORKING_DAYS_PER_WEEK,
            "FORTNIGHTLY": rate / self.WORKING_DAYS_PER_FORTNIGHT,
            "MONTHLY": rate / self.DAYS_PER_MONTH,
        }

        return rate_map.get(salary_type, rate / self.DAYS_PER_MONTH)

    def _get_period_total_days(self, start_date, end_date):
        """Calculate total days in a period."""
        return (end_date - start_date).days + 1

    def calculate_salary(self, payable_days):
        """Calculate current salary based on payable days."""
        if not self.salary_structure:
            return 0

        daily_rate = self._get_daily_rate()
        return round(float(payable_days) * daily_rate, 2)

    def calculate_remaining_days(self, payable_days):
        """Calculate remaining payable days in the period."""
        if not self.salary_structure:
            return 0

        start_date, end_date = self.get_period()
        total_days = self._get_period_total_days(start_date, end_date)
        return max(0, total_days - payable_days)

    def calculate_remaining_salary(self, payable_days):
        """Calculate remaining salary potential for remaining days."""
        if not self.salary_structure:
            return 0

        remaining_days = self.calculate_remaining_days(payable_days)
        daily_rate = self._get_daily_rate()
        return round(remaining_days * daily_rate, 2)