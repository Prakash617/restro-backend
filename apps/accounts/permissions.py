from rest_framework import permissions


class IsSuperAdmin(permissions.BasePermission):
    message = "Platform SuperAdmin privileges are required for this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return bool(
            user.is_superuser
            or getattr(user, "role", None) in ("SUPERADMIN", "SUPER_ADMIN")
        )


class IsRestaurantStaff(permissions.BasePermission):
    message = "Active restaurant staff credentials are required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_active)
