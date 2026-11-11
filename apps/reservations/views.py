from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsRestaurantStaff
from apps.tables.models import DiningTable
from .models import TableReservation
from .serializers import TableReservationSerializer


class TableReservationListCreateView(generics.ListCreateAPIView):
    serializer_class = TableReservationSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = TableReservation.objects.select_related(
            "table", "branch", "customer"
        ).all()
        status_param = self.request.query_params.get("status")
        date_param = self.request.query_params.get("reservation_date")
        branch = self.request.query_params.get("branch")
        if status_param:
            qs = qs.filter(status=status_param)
        if date_param:
            qs = qs.filter(reservation_date=date_param)
        if branch:
            qs = qs.filter(branch_id=branch)
        return qs

    def perform_create(self, serializer):
        reservation = serializer.save()
        if (
            reservation.table
            and reservation.status == TableReservation.Status.CONFIRMED
            and reservation.table.status == DiningTable.Status.AVAILABLE
        ):
            reservation.table.status = DiningTable.Status.RESERVED
            reservation.table.save(update_fields=["status"])


class TableReservationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TableReservation.objects.select_related(
        "table", "branch", "customer"
    ).all()
    serializer_class = TableReservationSerializer
    permission_classes = [permissions.AllowAny]


class TableReservationSeatView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        reservation = generics.get_object_or_404(TableReservation, pk=pk)
        table_id = request.data.get("table_id") or request.data.get("table")
        if table_id:
            table = generics.get_object_or_404(DiningTable, pk=table_id)
            reservation.table = table

        reservation.status = TableReservation.Status.SEATED
        reservation.save(update_fields=["status", "table"])

        if reservation.table:
            reservation.table.status = DiningTable.Status.OCCUPIED
            reservation.table.current_guest_count = reservation.party_size
            reservation.table.save(update_fields=["status", "current_guest_count"])

        return Response(
            TableReservationSerializer(reservation).data,
            status=status.HTTP_200_OK,
        )
