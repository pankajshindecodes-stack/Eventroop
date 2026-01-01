import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Count, Sum, Q
from .models import Attendance
from payroll.models import SalaryStructure
from attendance.models import AttendanceStatus

class PayrollCalculator:
    """
    Single source of truth for:
    - Attendance period calculation
    - Attendance aggregation
    - Salary structure selection
    - Salary calculation
    
    Now correctly handles mid-period salary changes.
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
    # Salary Structure
    # --------------------------------------------------
    def _get_salary_structure(self, effective_date=None):
        """Get salary structure effective on a given date."""
        check_date = effective_date or self.base_date
        return (
            SalaryStructure.objects
            .filter(
                user=self.user,
                effective_from__lte=check_date,
            )
            .order_by("-effective_from")
            .first()
        )

    # --------------------------------------------------
    # Period calculation (BASED ON SALARY TYPE)
    # --------------------------------------------------
    def _get_period_by_salary_type(self, base_date, salary_type):
        """Calculate period boundaries based on salary type and base date."""
        if salary_type in ("HOURLY", "DAILY"):
            return base_date, base_date

        if salary_type == "WEEKLY":
            start = base_date - timedelta(days=base_date.weekday())
            return start, start + timedelta(days=6)

        if salary_type == "FORTNIGHTLY":
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
        qs = AttendanceStatus.objects.filter(owner__is_superuser=True, is_active=True)

        return {
            "present": qs.filter(code__icontains="PRESENT").first(),
            "absent": qs.filter(code__icontains="ABSENT").first(),
            "paid_leave": qs.filter(code__icontains="PAID-LEAVE").first(),
            "half_day": qs.filter(code__icontains="HALF-DAY").first(),
            "weekly_off": qs.filter(code__icontains="WEEKLY-OFF").first(),
            "unpaid_leave": qs.filter(code__icontains="UNPAID-LEAVE").first(),
        }

    def _calculate_attendance(self, start_date, end_date):
        """Calculate attendance for a specific date range."""
        records = self._get_records(start_date, end_date)

        agg = records.aggregate(
            present_days=Count("id", filter=Q(status=self.status_codes["present"])),
            absent_days=Count("id", filter=Q(status=self.status_codes["absent"])),
            paid_leave_days=Count("id", filter=Q(status=self.status_codes["paid_leave"])),
            half_day_count=Count("id", filter=Q(status=self.status_codes["half_day"])),
            weekly_Offs=Count("id", filter=Q(status=self.status_codes["weekly_off"])),
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
    # Salary
    # --------------------------------------------------
    def _daily_rate(self, salary_obj, salary_type):
        """Calculate daily rate based on salary structure and type."""
        if not salary_obj:
            return Decimal("0")

        salary = Decimal(salary_obj.final_salary)

        if salary_type == "HOURLY":
            return salary * self.HOURS_PER_DAY
        if salary_type == "DAILY":
            return salary
        if salary_type == "WEEKLY":
            return salary / self.DAYS_PER_WEEK
        if salary_type == "FORTNIGHTLY":
            return salary / self.DAYS_PER_FORTNIGHT

        return salary / self.DAYS_PER_MONTH  # MONTHLY

    def _calculate_salary(self, salary_obj, salary_type, payable_days, start_date, end_date):
        """Calculate salary for a period with a specific salary structure."""
        daily_rate = self._daily_rate(salary_obj, salary_type).quantize(Decimal("0.01"))
        current_payment = (daily_rate * payable_days).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        total_days = (end_date - start_date).days + 1
        remaining_days = max(Decimal("0"), Decimal(total_days) - payable_days)
        remaining_payment = (remaining_days * daily_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return {
            "salary_type": salary_type,
            "final_salary": salary_obj.final_salary if salary_obj else 0,
            "daily_rate": daily_rate,
            "current_payment": current_payment,
            "remaining_payable_days": remaining_days,
            "remaining_payment": remaining_payment,
        }

    # --------------------------------------------------
    # Handle Mid-Period Salary Changes
    # --------------------------------------------------
    def _handle_salary_change_in_period(self, start_date, end_date):
        """
        If salary changes mid-period, split calculation into parts.
        Returns list of tuples: (salary_obj, salary_type, period_start, period_end)
        """
        # Get all salary changes that are effective on or before the period end
        all_changes = list(
            SalaryStructure.objects
            .filter(
                user=self.user,
                effective_from__lte=end_date
            )
            .order_by("-effective_from")
        )

        if not all_changes:
            return [(None, "MONTHLY", start_date, end_date)]

        # Find salary changes that occur within this period
        changes_in_period = [c for c in all_changes if start_date <= c.effective_from <= end_date]

        if not changes_in_period:
            # No changes during period, use the latest salary effective before period start
            salary = self._get_salary_structure(start_date)
            return [(salary, salary.salary_type if salary else "MONTHLY", start_date, end_date)]

        # Sort changes chronologically (earliest first)
        changes_in_period.sort(key=lambda x: x.effective_from)

        # Split period by salary changes
        periods = []
        current_start = start_date

        for change in changes_in_period:
            if current_start < change.effective_from:
                # Add period before this change using the previous salary
                prev_salary = self._get_salary_structure(current_start)
                prev_salary_type = prev_salary.salary_type if prev_salary else "MONTHLY"
                periods.append((prev_salary, prev_salary_type, current_start, change.effective_from - timedelta(days=1)))

            current_start = change.effective_from

        # Add remaining period after last change
        final_salary = self._get_salary_structure(current_start)
        final_salary_type = final_salary.salary_type if final_salary else "MONTHLY"
        periods.append((final_salary, final_salary_type, current_start, end_date))

        return periods

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------
    def calculate(self, base_date=None):
        """Calculate payroll for a single period."""
        base_date = base_date or self.base_date
        
        salary = self._get_salary_structure(base_date)
        salary_type = salary.salary_type if salary else "MONTHLY"
        
        start_date, end_date = self._get_period_by_salary_type(base_date, salary_type)
        
        # Check for mid-period salary changes
        salary_periods = self._handle_salary_change_in_period(start_date, end_date)
        
        if len(salary_periods) == 1:
            # No salary changes during period
            salary, salary_type, period_start, period_end = salary_periods[0]
            attendance = self._calculate_attendance(period_start, period_end)
            salary_calc = self._calculate_salary(salary, salary_type, attendance["total_payable_days"], period_start, period_end)

            return {
                "start_date": period_start,
                "end_date": period_end,
                "present_days": attendance["present_days"],
                "absent_days": attendance["absent_days"],
                "half_day_count": attendance["half_day_count"],
                "paid_leave_days": attendance["paid_leave_days"],
                "weekly_Offs": attendance["weekly_Offs"],
                "unpaid_leaves": attendance["unpaid_leaves"],
                "total_payable_days": float(attendance["total_payable_days"]),
                "total_payable_hours": float(attendance["total_payable_hours"]),
                **salary_calc,
            }
        else:
            # Salary changed mid-period, calculate combined result
            total_present_days = 0
            total_absent_days = 0
            total_half_days = 0
            total_paid_leaves = 0
            total_weekly_offs = 0
            total_unpaid_leaves = 0
            total_payable_days = Decimal("0")
            total_payable_hours = Decimal("0")
            total_current_payment = Decimal("0")

            for salary, salary_type, period_start, period_end in salary_periods:
                attendance = self._calculate_attendance(period_start, period_end)
                salary_calc = self._calculate_salary(salary, salary_type, attendance["total_payable_days"], period_start, period_end)

                total_present_days += attendance["present_days"]
                total_absent_days += attendance["absent_days"]
                total_half_days += attendance["half_day_count"]
                total_paid_leaves += attendance["paid_leave_days"]
                total_weekly_offs += attendance["weekly_Offs"]
                total_unpaid_leaves += attendance["unpaid_leaves"]
                total_payable_days += attendance["total_payable_days"]
                total_payable_hours += Decimal(str(attendance["total_payable_hours"]))
                total_current_payment += salary_calc["current_payment"]

            return {
                "start_date": start_date,
                "end_date": end_date,
                "present_days": total_present_days,
                "absent_days": total_absent_days,
                "half_day_count": total_half_days,
                "paid_leave_days": total_paid_leaves,
                "weekly_Offs": total_weekly_offs,
                "unpaid_leaves": total_unpaid_leaves,
                "total_payable_days": float(total_payable_days),
                "total_payable_hours": float(total_payable_hours),
                "salary_type": salary_type,
                "final_salary": (salary.final_salary if salary else 0),
                "current_payment": float(total_current_payment),
                "remaining_payable_days": 0,
                "remaining_payment": 0.0,
                "daily_rate": 0,
            }

    def calculate_all_periods_auto(self, start_date=None, end_date=None):
        """
        Returns all payroll reports from start_date (or user's first attendance) 
        to end_date (or today) based on user's salary type.
        """
        # Determine date range
        first_attendance = Attendance.objects.filter(user=self.user).order_by("date").first()
        start_date = start_date or (first_attendance.date if first_attendance else date.today())
        end_date = end_date or date.today()

        reports = []
        current_date = start_date

        while current_date <= end_date:
            # Calculate report for this period
            report = self.calculate(current_date)
            reports.append(report)

            # Get salary structure for current date to determine next period
            salary = self._get_salary_structure(current_date)
            salary_type = salary.salary_type if salary else "MONTHLY"
            _, period_end = self._get_period_by_salary_type(current_date, salary_type)

            # Move to next period
            if salary_type in ("HOURLY", "DAILY", "WEEKLY", "FORTNIGHTLY"):
                current_date = period_end + timedelta(days=1)
            else:  # MONTHLY
                next_month = period_end.replace(day=28) + timedelta(days=4)
                current_date = next_month.replace(day=1)

        return reports