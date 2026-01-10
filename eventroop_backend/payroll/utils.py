from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from payroll.models import SalaryStructure
from attendance.utils import AttendanceCalculator


class SalaryCalculator:
    """
    Single source of truth for salary calculations.
    Depends on AttendanceCalculator for attendance metrics.
    
    Handles:
    - Salary structure selection
    - Salary calculations
    - Mid-period salary changes
    """

    HOURS_PER_DAY = Decimal("8")
    DAYS_PER_WEEK = Decimal("7")
    DAYS_PER_FORTNIGHT = Decimal("14")
    DAYS_PER_MONTH = Decimal("30")

    def __init__(self, user, base_date=None):
        self.user = user
        self.base_date = base_date or date.today()
        self.attendance_calc = AttendanceCalculator(user, base_date)

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
                change_type__in=["BASE_SALARY","INCREMENT"]
            )
            .order_by("-effective_from")
            .first()
        )

    # --------------------------------------------------
    # Salary Calculations
    # --------------------------------------------------
    def _daily_rate(self, salary_obj, salary_type):
        """
        Calculate daily rate based on salary structure and salary type.
        """
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

        # MONTHLY → dynamic calendar days
        
        return salary / self.DAYS_PER_MONTH


    def _calculate_salary(self, salary_obj, salary_type, payable_days):
        """Calculate salary for a period with a specific salary structure."""
        daily_rate = self._daily_rate(salary_obj, salary_type).quantize(Decimal("0.01"))
        current_payment = (daily_rate * Decimal(str(payable_days))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return {
            "salary_type": salary_type,
            "final_salary": float(salary_obj.final_salary) if salary_obj else 0.0,
            "daily_rate": float(daily_rate),
            "current_payment": float(current_payment),
        }

    # --------------------------------------------------
    # Handle Mid-Period Salary Changes
    # --------------------------------------------------
    def _get_salary_periods(self, start_date, end_date):
        """
        Split period by salary changes if they occur mid-period.
        Returns list of tuples: (salary_obj, salary_type, period_start, period_end)
        """
        all_changes = list(
            SalaryStructure.objects
            .filter(
                user=self.user,
                effective_from__lte=end_date,
                change_type__in=["BASE_SALARY","INCREMENT"]
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
    def calculate_payroll(self, base_date=None, period_type="MONTHLY"):
        """
        Calculate payroll (attendance + salary) for a single period.
        
        Args:
            base_date: Reference date for period calculation (defaults to today)
            period_type: Type of period - HOURLY, DAILY, WEEKLY, FORTNIGHTLY, MONTHLY
            
        Returns:
            dict with attendance metrics and salary calculation
        """
        base_date = base_date or self.base_date
        
        # Get attendance report
        attendance_report = self.attendance_calc.get_attendance_report(base_date, period_type)
        period_start = attendance_report["start_date"]
        period_end = attendance_report["end_date"]
        
        # Check for mid-period salary changes
        salary_periods = self._get_salary_periods(period_start, period_end)
        
        if len(salary_periods) == 1:
            # No salary changes during period
            salary, salary_type, _, _ = salary_periods[0]
            salary_calc = self._calculate_salary(
                salary, 
                salary_type, 
                attendance_report["total_payable_days"],
            )

            return {
                **attendance_report,
                **salary_calc,
            }
        else:
            # Salary changed mid-period, calculate combined result
            total_current_payment = Decimal("0")
            final_daily_rate = Decimal("0")
            salary_type = period_type

            for salary, sal_type, sal_start, sal_end in salary_periods:
                # Get attendance for this salary period
                period_attendance = self.attendance_calc.get_attendance_for_date_range(sal_start, sal_end)
                salary_calc = self._calculate_salary(
                    salary,
                    sal_type,
                    period_attendance["total_payable_days"],
                )

                final_daily_rate = Decimal(str(salary_calc["daily_rate"]))
                total_current_payment += Decimal(str(salary_calc["current_payment"]))

            return {
                **attendance_report,
                "salary_type": salary_type,
                "final_salary": (salary.final_salary if salary else 0.0),
                "daily_rate": float(final_daily_rate),
                "current_payment": float(total_current_payment),
            }

    def calculate_all_payroll_periods(self, start_date=None, end_date=None, period_type="MONTHLY"):
        """
        Returns payroll reports for all periods in a date range.
        
        Args:
            start_date: Start of range (defaults to user's first attendance)
            end_date: End of range (defaults to today)
            period_type: Type of period - HOURLY, DAILY, WEEKLY, FORTNIGHTLY, MONTHLY
            
        Returns:
            list of payroll report dicts
        """
        # Use attendance calculator to get all periods
        attendance_reports = self.attendance_calc.get_all_periods_attendance(
            start_date, end_date, period_type
        )

        payroll_reports = []
        for report in attendance_reports:
            period_start = report["start_date"]
            period_end = report["end_date"]
            
            # Check for salary changes in this period
            salary_periods = self._get_salary_periods(period_start, period_end)
            
            if len(salary_periods) == 1:
                salary, salary_type, _, _ = salary_periods[0]
                salary_calc = self._calculate_salary(salary, salary_type, report["total_payable_days"])
            else:
                total_current_payment = Decimal("0")
                final_daily_rate = Decimal("0")
                
                for salary, sal_type, sal_start, sal_end in salary_periods:
                    period_attendance = self.attendance_calc.get_attendance_for_date_range(sal_start, sal_end)
                    salary_calc = self._calculate_salary(
                        salary,
                        sal_type,
                        period_attendance["total_payable_days"]
                    )
                    final_daily_rate = Decimal(str(salary_calc["daily_rate"]))
                    total_current_payment += Decimal(str(salary_calc["current_payment"]))
                
                salary_calc = {
                    "salary_type": period_type,
                    "final_salary": (salary.final_salary if salary else 0.0),
                    "daily_rate": float(final_daily_rate),
                    "current_payment": float(total_current_payment),
                }

            payroll_reports.append({**report, **salary_calc})

        return payroll_reports