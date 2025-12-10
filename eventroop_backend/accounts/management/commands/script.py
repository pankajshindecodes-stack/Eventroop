from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from accounts.models import CustomUser  # change to your correct path


class Command(BaseCommand):
    help = "Generate employee IDs for all users whose owner (created_by) is 38"

    def handle(self, *args, **kwargs):
        prefix_map = {
            "VSRE_MANAGER": "VSRE-M",
            "LINE_MANAGER": "VSRE-LM",
            "VSRE_STAFF": "VSRE-S",
        }

        year = timezone.now().year
        owner_id = 2
        updated_count = 0

        # Only target users for owner 38 with no employee ID
        users = CustomUser.objects.filter(
            created_by_id=owner_id,
            user_type__in=["VSRE_MANAGER", "LINE_MANAGER", "VSRE_STAFF"],
        ).order_by("id")

        self.stdout.write(f"Found {users.count()} users to update...\n")
        for user in users:
            user.employee_id = None
            user.save()
            self.stdout.write(
                self.style.NOTICE(
                    f"Employee ID: {user.employee_id}"
                )
            )
            
        
        for user in users:
            prefix = prefix_map.get(user.user_type)
            if not prefix:
                continue

            with transaction.atomic():
                # Fetch latest sequence for same owner + user type
                latest_user = (
                    CustomUser.objects.filter(
                        created_by_id=owner_id,
                        user_type=user.user_type
                    )
                    .exclude(employee_id__isnull=True)
                    .order_by("id")
                    .last()
                )

                # Determine next sequence
                if latest_user and latest_user.employee_id:
                    try:
                        parts = latest_user.employee_id.split("-")
                        last_seq = int(parts[-1])
                    except Exception:
                        last_seq = 0
                    next_seq = last_seq + 1
                else:
                    next_seq = 1

                # Build employee_id
                employee_id = (
                    f"{prefix}-{year}-{owner_id:03d}-{next_seq:04d}"
                )

                # Update user
                user.employee_id = employee_id
                user.save(update_fields=["employee_id"])
                updated_count += 1

                self.stdout.write(
                    f"Updated User {user.id} → {employee_id}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully updated {updated_count} users for owner {owner_id}."
            )
        )
