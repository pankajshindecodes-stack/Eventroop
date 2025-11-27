from accounts.models import CustomUser

def validate_owner_permissions(user, managers, staff_members):
    for m in managers:
        if m.hierarchy.owner != user:
            raise PermissionError(f"Manager {m.id} does not belong to you")

    for s in staff_members:
        if s.hierarchy.owner != user:
            raise PermissionError(f"Staff {s.id} does not belong to you")


def validate_manager_permissions(user, entity, manager_ids, staff_members):
    if not entity.managers.filter(id=user.id).exists():
        raise PermissionError("You are not assigned as manager for this item")

    if manager_ids:
        raise PermissionError("Managers cannot assign other managers")

    for s in staff_members:
        if s.hierarchy.parent_id != user.id:
            raise PermissionError(f"Staff {s.id} does not report to you")


def auto_assign_staff(manager_ids):
    return CustomUser.objects.filter(
        hierarchy__parent_id__in=manager_ids,
        user_type="VSRE_STAFF"
    )
