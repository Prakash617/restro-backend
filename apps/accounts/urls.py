from django.urls import path
from .views import (
    AuditLogListView,
    LoginView,
    MeView,
    PinLoginView,
    StaffDetailView,
    StaffListCreateView,
    StaffShiftClockInView,
    StaffShiftClockOutView,
    StaffShiftDetailView,
    StaffShiftListCreateView,
    TokenRefreshView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/pin-login/", PinLoginView.as_view(), name="auth-pin-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("staff/", StaffListCreateView.as_view(), name="staff-list-create"),
    path("staff/<int:pk>/", StaffDetailView.as_view(), name="staff-detail"),
    path("shifts/", StaffShiftListCreateView.as_view(), name="shift-list-create"),
    path("shifts/<int:pk>/", StaffShiftDetailView.as_view(), name="shift-detail"),
    path(
        "shifts/<int:pk>/clock-in/",
        StaffShiftClockInView.as_view(),
        name="shift-clock-in",
    ),
    path(
        "shifts/<int:pk>/clock-out/",
        StaffShiftClockOutView.as_view(),
        name="shift-clock-out",
    ),
    path("audit-logs/", AuditLogListView.as_view(), name="audit-log-list"),
]
