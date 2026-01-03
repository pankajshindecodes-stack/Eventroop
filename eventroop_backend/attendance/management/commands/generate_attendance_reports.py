
# Alternative: Use a management command for batch report generation
# management/commands/generate_attendance_reports.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from attendance.models import CustomUser, AttendanceReport
from attendance.utils import AttendanceCalculator
from decimal import Decimal

class Command(BaseCommand):
    help = 'Generate attendance reports for all users'

    def handle(self, *args, **options):
        users = CustomUser.objects.filter(user_type__in=("VSRE_MANAGER","LINE_MANAGER","VSRE_STAFF"))
        
        for user in users:
            payroll = AttendanceCalculator(user)
            reports = payroll.get_all_periods_attendance()
            
            for report in reports:
                AttendanceReport.objects.update_or_create(
                    user=user,
                    start_date=report["start_date"],
                    end_date=report["end_date"],
                    period_type=report["period_type"],
                    defaults={
                        "present_days": Decimal(str(report.get("present_days", 0))),
                        "absent_days": Decimal(str(report.get("absent_days", 0))),
                        "half_day_count": Decimal(str(report.get("half_day_count", 0))),
                        "paid_leave_days": Decimal(str(report.get("paid_leave_days", 0))),
                        "weekly_Offs": Decimal(str(report.get("weekly_offs", 0))),
                        "unpaid_leaves": Decimal(str(report.get("unpaid_leaves", 0))),
                        "total_payable_days": Decimal(str(report.get("total_payable_days", 0))),
                        "total_payable_hours": Decimal(str(report.get("total_payable_hours", 0))),
                    }
                )
            
            self.stdout.write(
                self.style.SUCCESS(f'Generated reports for {user.get_full_name()}')
            )