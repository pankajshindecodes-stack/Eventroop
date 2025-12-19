from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from attendance.models import Attendance, AttendanceStatus
from accounts.models import CustomUser


class Command(BaseCommand):
    help = "Mark attendance for all staff as Present from start_date to today"

    def handle(self, *args, **kwargs):
        # Get the "Present" status with code "P"
        try:
            present_status = AttendanceStatus.objects.get(code='PRESENT')
        except AttendanceStatus.DoesNotExist:
            self.stdout.write(
                self.style.ERROR("AttendanceStatus with code 'P' (Present) not found.")
            )
            return

        current_date = date.today()  # Today's date
        
        users = CustomUser.objects.get_staff_under_owner(owner=38)
        users_list = list(users.values_list('id', flat=True))

        if not users_list:
            self.stdout.write(self.style.WARNING("No staff found for this owner."))
            return

        # Get existing attendance records to avoid duplicates
        existing = set(
            Attendance.objects.filter(
                user_id__in=users_list,
                date=current_date
            ).values_list('user_id', 'date')
        )

        # Prepare bulk create data with "Present" status
        attendance_records = []
        for user_id in users_list:
            if (user_id, current_date) not in existing:
                attendance_records.append(
                    Attendance(
                        user_id=user_id,
                        date=current_date,
                        status=present_status,
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
                    f"Created {len(created)} attendance records marked as Present."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING("No new attendance records to create.")
            )