from django.core.management.base import BaseCommand
from datetime import date, timedelta
from attendance.models import Attendance, AttendanceStatus
from accounts.models import CustomUser
import random


class Command(BaseCommand):
    help = "Generate attendance for all users from their start_date to today"

    def handle(self, *args, **kwargs):
        statuses = list(AttendanceStatus.objects.all())
        if not statuses:
            self.stdout.write(self.style.ERROR("No attendance statuses found."))
            return

        start_date = date(2025, 12, 11,)
        end_date = date(2025, 12, 13,)
        
        users = CustomUser.objects.get_staff_under_owner(owner=2)
        users_list = list(users.values_list('id', flat=True))

        # Generate all dates once
        current = start_date
        all_dates = []
        while current <= end_date:
            all_dates.append(current)
            current += timedelta(days=1)

        # Get existing attendance records to avoid duplicates
        existing = set(
            Attendance.objects.filter(
                user_id__in=users_list,
                date__range=[start_date, end_date]
            ).values_list('user_id', 'date')
        )

        # Prepare bulk create data with random status
        attendance_records = []
        for user_id in users_list:
            for d in all_dates:
                if (user_id, d) not in existing:
                    attendance_records.append(
                        Attendance(
                            user_id=user_id,
                            date=d,
                            status=random.choice(statuses),
                            duration=None,
                        )
                    )

        # Bulk create all at once
        if attendance_records:
            created = Attendance.objects.bulk_create(
                attendance_records,
                batch_size=5000,
                ignore_conflicts=False
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {len(created)} attendance records."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING("No new attendance records to create.")
            )