from django.db.models.signals import post_save, post_migrate
from django.core.management import call_command
from django.contrib.auth.models import Group
from django.dispatch import receiver
from django.utils import timezone
from .models import CustomUser,UserHierarchy


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
    if created and not instance.employee_id:
        # Map each user type to a short prefix
        prefix_map = {
            "VSRE_MANAGER": "VSRE-M",
            "LINE_MANAGER": "VSRE-LM",
            "VSRE_STAFF": "VSRE-S",
        }

        prefix = prefix_map.get(instance.user_type,None)
        year = timezone.now().year
        
        if not prefix:
            return
        
        # Count how many existing users have this type (for sequential numbering)        
        count = (
            CustomUser.objects.filter(
                created_by=instance.created_by, # filter only same owner
                user_type=instance.user_type    # filter same user_type
            )
            .exclude(employee_id__isnull=True)
            .count()
            + 1
        )

        # Create ID format: PREFIX-YEAR-XXX

        instance.employee_id = f"{prefix}-{year}-{instance.created_by.id:03d}-{count:03d}"

        # Save again without triggering another signal loop
        instance.save(update_fields=["employee_id"])
