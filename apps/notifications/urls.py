from django.urls import path

from .push_views import (
    PushStatusView,
    PushSubscribeView,
    PushTestView,
    PushUnsubscribeView,
    PushVapidPublicKeyView,
)
from .views import (
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
)

urlpatterns = [
    path(
        "notifications/",
        NotificationListView.as_view(),
        name="notification-list",
    ),
    path(
        "notifications/<int:pk>/read/",
        NotificationMarkReadView.as_view(),
        name="notification-mark-read",
    ),
    path(
        "notifications/mark-all-read/",
        NotificationMarkAllReadView.as_view(),
        name="notification-mark-all-read",
    ),
    path(
        "push/vapid-public-key/",
        PushVapidPublicKeyView.as_view(),
        name="push-vapid-public-key",
    ),
    path("push/subscribe/", PushSubscribeView.as_view(), name="push-subscribe"),
    path("push/unsubscribe/", PushUnsubscribeView.as_view(), name="push-unsubscribe"),
    path("push/status/", PushStatusView.as_view(), name="push-status"),
    path("push/test/", PushTestView.as_view(), name="push-test"),
]
