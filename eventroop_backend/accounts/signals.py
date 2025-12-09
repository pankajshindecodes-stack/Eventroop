from django.db.models.signals import post_save, post_migrate
from django.core.management import call_command
from django.contrib.auth.models import Group
from django.dispatch import receiver
from django.utils import timezone
from .models import CustomUser,UserHierarchy
from django.db import transaction


# ---------------------------
# Assign Group on User Save
# ---------------------------
@receiver(post_save, sender=CustomUser)
def assign_group_to_user(sender, instance, created, **kwargs):
    """Automatically assign the correct group based on user_type."""
    if not instance.user_type:
        return

    try:
        group = Group.objects.get(name=instance.user_type)
    except Group.DoesNotExist:
        return

    # Remove user from other groups and add to correct one
    instance.groups.clear()
    instance.groups.add(group)


# ---------------------------
# Auto-create Groups after Migration
# ---------------------------
# @receiver(post_migrate)
# def create_default_groups_after_migration(sender, **kwargs):
#     """Automatically run group creation after migrations."""
#     if sender.name != "accounts":
#         return
#     print("Running post_migrate: creating default groups and permissions...")
#     call_command("create_default_groups")


# ---------------------------
# Auto generate Employee Id 
# ---------------------------
@receiver(post_save, sender=CustomUser)
def generate_employee_id(sender, instance, created, **kwargs):
    """
    Generate a unique employee ID in format:
    PREFIX-YYYY-OWNER_ID-UNIQUE_SEQUENCE
    Example: VSRE-M-2025-001-0001
    """
    if created and not instance.employee_id:
        # Map each user type to a short prefix
        prefix_map = {
            "VSRE_MANAGER": "VSRE-M",
            "LINE_MANAGER": "VSRE-LM",
            "VSRE_STAFF": "VSRE-S",
        }

        prefix = prefix_map.get(instance.user_type, None)
        
        # Return early if user type not in map
        if not prefix:
            return

        year = timezone.now().year
        owner_id = instance.created_by.id if instance.created_by else 999
        
        # Use transaction to ensure atomicity and prevent race conditions
        with transaction.atomic():
            # Get the highest sequence number for this specific combination
            # (prefix + year + owner + user_type)
            latest_user = (
                CustomUser.objects
                .filter(
                    created_by=instance.created_by,
                    user_type=instance.user_type,
                )
                .exclude(employee_id__isnull=True)
                .order_by("id")
                .last()
            )

            # Extract sequence number from latest employee_id and increment
            if latest_user and latest_user.employee_id:
                try:
                    # Parse: PREFIX-YYYY-OWNER_ID-SEQUENCE
                    parts = latest_user.employee_id.split("-")
                    last_sequence = int(parts[-1])
                    next_sequence = last_sequence + 1
                except (ValueError, IndexError):
                    next_sequence = 1
            else:
                next_sequence = 1

            # Create ID format: PREFIX-YYYY-OWNER_ID-SEQUENCE (4 digits)
            instance.employee_id = (
                f"{prefix}-{year}-{owner_id:03d}-{next_sequence:04d}"
            )

            # Save again without triggering another signal loop
            instance.save(update_fields=["employee_id"])
