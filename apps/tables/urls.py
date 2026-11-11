from django.urls import path
from .views import (
    DiningTableDetailView,
    DiningTableListCreateView,
    DiningTableMergeView,
    DiningTableSetStatusView,
    DiningTableTransferView,
    DiningZoneDetailView,
    DiningZoneListCreateView,
)

urlpatterns = [
    path(
        "tables/zones/",
        DiningZoneListCreateView.as_view(),
        name="dining-zone-list-create",
    ),
    path(
        "tables/zones/<int:pk>/",
        DiningZoneDetailView.as_view(),
        name="dining-zone-detail",
    ),
    path("tables/", DiningTableListCreateView.as_view(), name="dining-table-list-create"),
    path("tables/<int:pk>/", DiningTableDetailView.as_view(), name="dining-table-detail"),
    path(
        "tables/<int:pk>/set-status/",
        DiningTableSetStatusView.as_view(),
        name="dining-table-set-status",
    ),
    path("tables/merge/", DiningTableMergeView.as_view(), name="dining-table-merge"),
    path(
        "tables/transfer/",
        DiningTableTransferView.as_view(),
        name="dining-table-transfer",
    ),
]
