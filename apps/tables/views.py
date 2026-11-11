from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.accounts.permissions import IsRestaurantStaff
from .models import DiningTable, DiningZone
from .serializers import DiningTableSerializer, DiningZoneSerializer


class DiningZoneListCreateView(generics.ListCreateAPIView):
    serializer_class = DiningZoneSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = DiningZone.objects.select_related("branch").prefetch_related("tables").all()
        branch = self.request.query_params.get("branch")
        if branch:
            qs = qs.filter(branch_id=branch)
        return qs


class DiningZoneDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = DiningZone.objects.select_related("branch").prefetch_related("tables").all()
    serializer_class = DiningZoneSerializer
    permission_classes = [permissions.AllowAny]


class DiningTableListCreateView(generics.ListCreateAPIView):
    serializer_class = DiningTableSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = (
            DiningTable.objects.select_related("zone", "branch", "merged_into")
            .prefetch_related("merged_tables", "orders")
            .all()
        )
        zone = self.request.query_params.get("zone")
        branch = self.request.query_params.get("branch")
        status_param = self.request.query_params.get("status")
        if zone:
            qs = qs.filter(zone_id=zone)
        if branch:
            qs = qs.filter(branch_id=branch)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(tenant, "schema_name", "public") != "public" and getattr(tenant, "plan", None):
            max_tables = tenant.plan.max_tables
            current_tables = DiningTable.objects.count()
            if current_tables >= max_tables:
                return Response(
                    {
                        "code": "QUOTA_EXCEEDED",
                        "detail": (
                            f"Table quota reached ({current_tables}/{max_tables}) for the "
                            f"{tenant.plan.name} plan. Please upgrade your subscription plan."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().create(request, *args, **kwargs)


class DiningTableDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = (
        DiningTable.objects.select_related("zone", "branch", "merged_into")
        .prefetch_related("merged_tables", "orders")
        .all()
    )
    serializer_class = DiningTableSerializer
    permission_classes = [permissions.AllowAny]


class DiningTableSetStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        table = generics.get_object_or_404(DiningTable, pk=pk)
        new_status = (request.data.get("status") or "").strip().upper()
        valid_statuses = dict(DiningTable.Status.choices)
        if new_status not in valid_statuses:
            return Response(
                {"detail": f"Invalid status. Choose from {list(valid_statuses.keys())}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        table.status = new_status
        if new_status == DiningTable.Status.AVAILABLE:
            table.current_guest_count = 0
            table.merged_into = None
            table.merged_tables.update(
                merged_into=None,
                status=DiningTable.Status.AVAILABLE,
                current_guest_count=0,
            )
        elif "current_guest_count" in request.data:
            table.current_guest_count = int(request.data["current_guest_count"] or 0)
        table.save()
        return Response(DiningTableSerializer(table).data, status=status.HTTP_200_OK)


class DiningTableMergeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        primary_id = request.data.get("primary_table_id")
        secondary_ids = request.data.get("secondary_table_ids") or []
        unmerge = bool(request.data.get("unmerge", False))

        if not primary_id:
            return Response(
                {"detail": "primary_table_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        primary_table = generics.get_object_or_404(DiningTable, pk=primary_id)

        if unmerge or not secondary_ids:
            merged_numbers = list(
                primary_table.merged_tables.values_list("table_number", flat=True)
            )
            primary_table.merged_tables.update(
                merged_into=None,
                status=DiningTable.Status.AVAILABLE,
                current_guest_count=0,
            )
            primary_table.merged_into = None
            primary_table.save(update_fields=["merged_into"])
            AuditLog.objects.create(
                actor=request.user if request.user.is_authenticated else None,
                actor_name=getattr(request.user, "full_name", "Staff"),
                branch=primary_table.branch,
                action=AuditLog.Action.TABLE_MERGED,
                target_model="DiningTable",
                target_id=str(primary_table.id),
                description=f"Unmerged tables {merged_numbers} from Table {primary_table.table_number}.",
                metadata_json={"unmerged": merged_numbers},
            )
            return Response(
                DiningTableSerializer(primary_table).data,
                status=status.HTTP_200_OK,
            )

        secondary_tables = DiningTable.objects.filter(id__in=secondary_ids).exclude(
            id=primary_table.id
        )
        merged_nums = []
        for sec in secondary_tables:
            sec.merged_into = primary_table
            sec.status = primary_table.status if primary_table.status != DiningTable.Status.AVAILABLE else DiningTable.Status.OCCUPIED
            sec.save(update_fields=["merged_into", "status"])
            merged_nums.append(sec.table_number)

        if primary_table.status == DiningTable.Status.AVAILABLE:
            primary_table.status = DiningTable.Status.OCCUPIED
            primary_table.save(update_fields=["status"])

        AuditLog.objects.create(
            actor=request.user if request.user.is_authenticated else None,
            actor_name=getattr(request.user, "full_name", "Staff"),
            branch=primary_table.branch,
            action=AuditLog.Action.TABLE_MERGED,
            target_model="DiningTable",
            target_id=str(primary_table.id),
            description=f"Merged tables {merged_nums} into primary Table {primary_table.table_number}.",
            metadata_json={
                "primary_table": primary_table.table_number,
                "secondary_tables": merged_nums,
            },
        )
        return Response(
            DiningTableSerializer(primary_table).data,
            status=status.HTTP_200_OK,
        )


class DiningTableTransferView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from apps.orders.models import Order

        from_id = request.data.get("from_table_id")
        to_id = request.data.get("to_table_id")
        if not from_id or not to_id:
            return Response(
                {"detail": "Both from_table_id and to_table_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if str(from_id) == str(to_id):
            return Response(
                {"detail": "Source and destination tables must be different."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from_table = generics.get_object_or_404(DiningTable, pk=from_id)
        to_table = generics.get_object_or_404(DiningTable, pk=to_id)

        active_orders = Order.objects.filter(table=from_table).exclude(
            status__in=[Order.Status.COMPLETED, Order.Status.CANCELLED]
        )
        transferred_order_numbers = list(
            active_orders.values_list("order_number", flat=True)
        )
        active_orders.update(table=to_table)

        to_table.status = DiningTable.Status.OCCUPIED
        to_table.current_guest_count = from_table.current_guest_count or to_table.capacity
        to_table.save(update_fields=["status", "current_guest_count"])

        from_table.status = DiningTable.Status.AVAILABLE
        from_table.current_guest_count = 0
        from_table.merged_into = None
        from_table.save(update_fields=["status", "current_guest_count", "merged_into"])

        AuditLog.objects.create(
            actor=request.user if request.user.is_authenticated else None,
            actor_name=getattr(request.user, "full_name", "Staff"),
            branch=to_table.branch or from_table.branch,
            action=AuditLog.Action.TABLE_TRANSFERRED,
            target_model="DiningTable",
            target_id=str(to_table.id),
            description=(
                f"Transferred Table {from_table.table_number} to Table {to_table.table_number} "
                f"(orders: {transferred_order_numbers})."
            ),
            metadata_json={
                "from_table": from_table.table_number,
                "to_table": to_table.table_number,
                "orders": transferred_order_numbers,
            },
        )

        return Response(
            {
                "detail": f"Transferred active order(s) from Table {from_table.table_number} to Table {to_table.table_number}.",
                "from_table": DiningTableSerializer(from_table).data,
                "to_table": DiningTableSerializer(to_table).data,
                "transferred_orders": transferred_order_numbers,
            },
            status=status.HTTP_200_OK,
        )
