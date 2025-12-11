from django.core.management.base import BaseCommand
from datetime import date, timedelta
from attendance.models import Attendance, AttendanceStatus
from accounts.models import CustomUser


class Command(BaseCommand):
    help = "Generate attendance for all users from their start_date to today"

    def handle(self, *args, **kwargs):
        default_status = AttendanceStatus.objects.filter(code="P").first()
        if not default_status:
            self.stdout.write(self.style.ERROR("ABSENT status not found."))
            return

        today = date.today()

        users = CustomUser.objects.get_staff_under_owner(owner=38)

        for user in users:
            start_date = date(2025,10,1)
            current = start_date
            created_count = 0

            while current <= today:
                _, created = Attendance.objects.get_or_create(
                    user=user,
                    date=current,
                    defaults={
                        "status": default_status,
                        "duration": None,
                    },
                )
                if created:
                    created_count += 1

                current += timedelta(days=1)

            self.stdout.write(
                self.style.SUCCESS(
                    f"{user.get_full_name()} → {created_count} attendance records created."
                )
            )
