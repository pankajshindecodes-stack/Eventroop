import calendar
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Count, Sum, Q
from .models import Attendance, AttendanceStatus


class AttendanceCalculator:
    """
    Single source of truth for:
    - Attendance period calculation
    - Attendance aggregation
    - Attendance reporting
    """

    HOURS_PER_DAY = Decimal("8")
    DAYS_PER_WEEK = Decimal("7")
    DAYS_PER_FORTNIGHT = Decimal("14")
    DAYS_PER_MONTH = Decimal("30")

    def __init__(self, user, base_date=None):
        self.user = user
        self.base_date = base_date or date.today()
        self.status_codes = self._load_status_codes()

    # --------------------------------------------------
    # Period calculation (BASED ON PERIOD TYPE)
    # --------------------------------------------------
    def _get_period_by_type(self, base_date, period_type):
        """Calculate period boundaries based on period type and base date."""
        if period_type in ("HOURLY", "DAILY"):
            return base_date, base_date

        if period_type == "WEEKLY":
            start = base_date - timedelta(days=base_date.weekday())
            return start, start + timedelta(days=6)

        if period_type == "FORTNIGHTLY":
            if base_date.day <= 15:
                return base_date.replace(day=1), base_date.replace(day=15)

            last = calendar.monthrange(base_date.year, base_date.month)[1]
            return base_date.replace(day=16), base_date.replace(day=last)

        # MONTHLY
        first = base_date.replace(day=1)
        last = base_date.replace(
            day=calendar.monthrange(base_date.year, base_date.month)[1]
        )
        return first, last

    # --------------------------------------------------
    # Attendance
    # --------------------------------------------------
    def _get_records(self, start_date, end_date):
        """Get attendance records for a date range."""
        return Attendance.objects.filter(
            user=self.user,
            date__range=(start_date, end_date)
        )

    def _load_status_codes(self):
        """Load active attendance status codes."""
        qs = AttendanceStatus.objects.filter(owner__is_superuser=True, is_active=True)

        return {
            "present": qs.filter(code__icontains="PRESENT").first(),
            "absent": qs.filter(code__icontains="ABSENT").first(),
            "paid_leave": qs.filter(code__icontains="PAID_LEAVE").first(),
            "half_day": qs.filter(code__icontains="HALF_DAY").first(),
            "weekly_off": qs.filter(code__icontains="WEEKLY_OFF").first(),
            "unpaid_leave": qs.filter(code__icontains="UNPAID_LEAVE").first(),
        }

    def _calculate_attendance(self, start_date, end_date):
        """Calculate attendance metrics for a specific date range."""
        records = self._get_records(start_date, end_date)

        agg = records.aggregate(
            present_days=Count("id", filter=Q(status=self.status_codes["present"])),
            absent_days=Count("id", filter=Q(status=self.status_codes["absent"])),
            paid_leave_days=Count("id", filter=Q(status=self.status_codes["paid_leave"])),
            half_day_count=Count("id", filter=Q(status=self.status_codes["half_day"])),
            weekly_offs=Count("id", filter=Q(status=self.status_codes["weekly_off"])),
            unpaid_leaves=Count("id", filter=Q(status=self.status_codes["unpaid_leave"])),
            total_duration=Sum("duration"),
        )

        total_hours = (
            Decimal(agg["total_duration"].total_seconds()) / Decimal(3600)
            if agg["total_duration"]
            else Decimal("0")
        )

        payable_days = (
            agg["present_days"]
            + agg["paid_leave_days"]
            + (Decimal("0.5") * agg["half_day_count"])
        )

        return {
            **agg,
            "total_payable_days": payable_days,
            "total_payable_hours": total_hours,
        }

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------
    def get_attendance_report(self, base_date=None, period_type="MONTHLY"):
        """
        Generate attendance report for a single period.
        
        Args:
            base_date: Reference date for period calculation (defaults to today)
            period_type: Type of period - HOURLY, DAILY, WEEKLY, FORTNIGHTLY, MONTHLY
            
        Returns:
            dict with attendance metrics and period boundaries
        """
        base_date = base_date or self.base_date
        period_start, period_end = self._get_period_by_type(base_date, period_type)
        
        attendance = self._calculate_attendance(period_start, period_end)

        print(attendance)
        return {
            "start_date": period_start,
            "end_date": period_end,
            "period_type": period_type,
            "present_days": attendance["present_days"],
            "absent_days": attendance["absent_days"],
            "half_day_count": attendance["half_day_count"],
            "paid_leave_days": attendance["paid_leave_days"],
            "weekly_offs": attendance["weekly_offs"],
            "unpaid_leaves": attendance["unpaid_leaves"],
            "total_payable_days": float(attendance["total_payable_days"]),
            "total_payable_hours": float(attendance["total_payable_hours"]),
        }

    def get_all_periods_attendance(self, start_date=None, end_date=None, period_type="MONTHLY"):
        """
        Returns attendance reports for all periods in a date range.
        
        Args:
            start_date: Start of range (defaults to user's first attendance)
            end_date: End of range (defaults to today)
            period_type: Type of period - HOURLY, DAILY, WEEKLY, FORTNIGHTLY, MONTHLY
            
        Returns:
            list of attendance report dicts
        """
        # Determine date range
        first_attendance = Attendance.objects.filter(user=self.user).order_by("date").first()
        start_date = start_date or (first_attendance.date if first_attendance else date.today())
        end_date = end_date or date.today()

        reports = []
        current_date = start_date

        while current_date <= end_date:
            # Generate report for this period
            report = self.get_attendance_report(current_date, period_type)
            reports.append(report)

            # Move to next period
            _, period_end = self._get_period_by_type(current_date, period_type)

            if period_type in ("HOURLY", "DAILY", "WEEKLY", "FORTNIGHTLY"):
                current_date = period_end + timedelta(days=1)
            else:  # MONTHLY
                next_month = period_end.replace(day=28) + timedelta(days=4)
                current_date = next_month.replace(day=1)

        return reports

    def get_attendance_for_date_range(self, start_date, end_date):
        """
        Get attendance metrics for a custom date range (not aligned to periods).
        
        Args:
            start_date: Start of custom range
            end_date: End of custom range
            
        Returns:
            dict with attendance metrics
        """
        attendance = self._calculate_attendance(start_date, end_date)

        return {
            "start_date": start_date,
            "end_date": end_date,
            "present_days": attendance["present_days"],
            "absent_days": attendance["absent_days"],
            "half_day_count": attendance["half_day_count"],
            "paid_leave_days": attendance["paid_leave_days"],
            "weekly_offs": attendance["weekly_offs"],
            "unpaid_leaves": attendance["unpaid_leaves"],
            "total_payable_days": float(attendance["total_payable_days"]),
            "total_payable_hours": float(attendance["total_payable_hours"]),
        }

