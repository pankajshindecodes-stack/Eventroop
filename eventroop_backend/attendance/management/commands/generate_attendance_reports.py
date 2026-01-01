
# Alternative: Use a management command for batch report generation
# management/commands/generate_attendance_reports.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from attendance.models import CustomUser, AttendanceReport
from attendance.utils import PayrollCalculator


class Command(BaseCommand):
    help = 'Generate attendance reports for all users'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, help='Generate report for specific user')
        parser.add_argument('--date', type=str, help='Generate reports for specific date (YYYY-MM-DD)')

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        date_str = options.get('date')
        
        if user_id:
            users = CustomUser.objects.filter(id=user_id)
        else:
            users = CustomUser.objects.all()
        
        for user in users:
            payroll = PayrollCalculator(user)
            reports = payroll.calculate_all_periods_auto()
            
            for report in reports:
                AttendanceReport.objects.update_or_create(
                    user=user,
                    start_date=report["start_date"],
                    end_date=report["end_date"],
                    defaults={
                        "present_days": report.get("present_days", 0),
                        "absent_days": report.get("absent_days", 0),
                        "half_day_count": report.get("half_day_count", 0),
                        "paid_leave_days": report.get("paid_leave_days", 0),
                        "weekly_Offs": report.get("weekly_Offs", 0),
                        "unpaid_leaves": report.get("unpaid_leaves", 0),
                        "total_payable_days": report.get("total_payable_days", 0),
                        "total_payable_hours": report.get("total_payable_hours", 0),
                        "salary_type": report.get("salary_type"),
                        "final_salary": report.get("final_salary", 0),
                        "daily_rate": report.get("daily_rate", 0),
                        "current_payment": report.get("current_payment", 0),
                    }
                )
            
            self.stdout.write(
                self.style.SUCCESS(f'Generated reports for {user.get_full_name()}')
            )