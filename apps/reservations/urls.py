from django.urls import path
from .views import (
    TableReservationDetailView,
    TableReservationListCreateView,
    TableReservationSeatView,
)

urlpatterns = [
    path(
        "reservations/",
        TableReservationListCreateView.as_view(),
        name="reservation-list-create",
    ),
    path(
        "reservations/<int:pk>/",
        TableReservationDetailView.as_view(),
        name="reservation-detail",
    ),
    path(
        "reservations/<int:pk>/seat/",
        TableReservationSeatView.as_view(),
        name="reservation-seat",
    ),
]
