from django.urls import path
from .views import (
    DashboardStatsView,
    KDSOrderItemBumpView,
    KDSOrderListView,
    OrderAddItemsView,
    OrderAdvanceStatusView,
    OrderCheckoutView,
    OrderDetailView,
    OrderListCreateView,
    OrderRefundView,
)

urlpatterns = [
    path("orders/", OrderListCreateView.as_view(), name="order-list-create"),
    path("orders/kds/", KDSOrderListView.as_view(), name="order-kds-list"),
    path(
        "orders/dashboard-stats/",
        DashboardStatsView.as_view(),
        name="order-dashboard-stats",
    ),
    path(
        "orders/items/<int:item_id>/bump/",
        KDSOrderItemBumpView.as_view(),
        name="order-item-bump",
    ),
    path(
        "orders/<int:pk>/bump-item/",
        KDSOrderItemBumpView.as_view(),
        name="order-bump-item-alt",
    ),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path(
        "orders/<int:pk>/add-items/",
        OrderAddItemsView.as_view(),
        name="order-add-items",
    ),
    path(
        "orders/<int:pk>/advance-status/",
        OrderAdvanceStatusView.as_view(),
        name="order-advance-status",
    ),
    path(
        "orders/<int:pk>/status/",
        OrderAdvanceStatusView.as_view(),
        name="order-status-alt",
    ),
    path(
        "orders/<int:pk>/checkout/",
        OrderCheckoutView.as_view(),
        name="order-checkout",
    ),
    path(
        "orders/<int:pk>/refund/",
        OrderRefundView.as_view(),
        name="order-refund",
    ),
]
