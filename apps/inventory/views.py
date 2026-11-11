from decimal import Decimal
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.accounts.permissions import IsRestaurantStaff
from .models import (
    InventoryItem,
    PurchaseOrder,
    RecipeIngredient,
    StockMovement,
    Supplier,
)
from .serializers import (
    InventoryItemSerializer,
    PurchaseOrderSerializer,
    RecipeIngredientSerializer,
    StockMovementSerializer,
    SupplierSerializer,
)


class SupplierListCreateView(generics.ListCreateAPIView):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.AllowAny]


class SupplierDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.AllowAny]


class InventoryItemListCreateView(generics.ListCreateAPIView):
    serializer_class = InventoryItemSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = InventoryItem.objects.select_related("supplier", "branch").all()
        category = self.request.query_params.get("category")
        branch = self.request.query_params.get("branch")
        low_stock = self.request.query_params.get("low_stock")
        if category:
            qs = qs.filter(category=category)
        if branch:
            qs = qs.filter(branch_id=branch)
        if low_stock and low_stock.lower() in ("true", "1"):
            from django.db.models import F

            qs = qs.filter(current_stock__lte=F("reorder_level"))
        return qs


class InventoryItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = InventoryItem.objects.select_related("supplier", "branch").all()
    serializer_class = InventoryItemSerializer
    permission_classes = [permissions.AllowAny]


class InventoryItemAdjustStockView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        item = generics.get_object_or_404(InventoryItem, pk=pk)
        movement_type = (
            request.data.get("movement_type") or StockMovement.MovementType.RESTOCK
        ).upper()
        quantity = Decimal(str(request.data.get("quantity") or "0"))
        reason = request.data.get("reason") or f"{movement_type} adjustment"
        reference = request.data.get("reference") or ""

        if quantity == 0:
            return Response(
                {"detail": "Non-zero quantity is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if movement_type in (
            StockMovement.MovementType.CONSUMPTION,
            StockMovement.MovementType.WASTAGE,
        ):
            delta = -abs(quantity)
        elif movement_type in (
            StockMovement.MovementType.RESTOCK,
            StockMovement.MovementType.PO_RECEIPT,
        ):
            delta = abs(quantity)
            item.last_restocked_at = timezone.now()
        else:
            delta = quantity

        item.current_stock = max(Decimal("0.000"), item.current_stock + delta)
        item.save(update_fields=["current_stock", "last_restocked_at"])

        StockMovement.objects.create(
            item=item,
            branch=item.branch,
            movement_type=movement_type,
            quantity=delta,
            reason=reason,
            reference=reference,
            performed_by=request.user if request.user.is_authenticated else None,
        )

        if movement_type == StockMovement.MovementType.WASTAGE:
            AuditLog.objects.create(
                actor=request.user if request.user.is_authenticated else None,
                actor_name=getattr(request.user, "full_name", "Staff"),
                branch=item.branch,
                action=AuditLog.Action.STOCK_WASTAGE,
                target_model="InventoryItem",
                target_id=str(item.id),
                description=f"Recorded wastage of {abs(quantity)} {item.unit} for '{item.name}' ({reason}).",
                metadata_json={"quantity": str(delta), "reason": reason},
            )

        return Response(InventoryItemSerializer(item).data, status=status.HTTP_200_OK)


class RecipeIngredientListCreateView(generics.ListCreateAPIView):
    serializer_class = RecipeIngredientSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = RecipeIngredient.objects.select_related(
            "menu_item", "inventory_item"
        ).all()
        menu_item = self.request.query_params.get("menu_item")
        if menu_item:
            qs = qs.filter(menu_item_id=menu_item)
        return qs


class RecipeIngredientDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = RecipeIngredient.objects.select_related(
        "menu_item", "inventory_item"
    ).all()
    serializer_class = RecipeIngredientSerializer
    permission_classes = [permissions.AllowAny]


class PurchaseOrderListCreateView(generics.ListCreateAPIView):
    queryset = (
        PurchaseOrder.objects.select_related("supplier", "branch")
        .prefetch_related("items__inventory_item")
        .all()
    )
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.AllowAny]


class PurchaseOrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = (
        PurchaseOrder.objects.select_related("supplier", "branch")
        .prefetch_related("items__inventory_item")
        .all()
    )
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.AllowAny]


class PurchaseOrderReceiveView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        po = generics.get_object_or_404(
            PurchaseOrder.objects.prefetch_related("items__inventory_item"), pk=pk
        )
        if po.status == PurchaseOrder.Status.RECEIVED:
            return Response(
                {"detail": f"Purchase order {po.po_number} has already been received."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        for po_item in po.items.all():
            qty = po_item.quantity_ordered - po_item.quantity_received
            if qty <= 0:
                qty = po_item.quantity_ordered
            po_item.quantity_received = po_item.quantity_ordered
            po_item.save(update_fields=["quantity_received"])

            inv_item = po_item.inventory_item
            inv_item.current_stock += qty
            inv_item.last_restocked_at = now
            if po_item.unit_cost and po_item.unit_cost > 0:
                inv_item.cost_per_unit = po_item.unit_cost
            inv_item.save(
                update_fields=["current_stock", "last_restocked_at", "cost_per_unit"]
            )

            StockMovement.objects.create(
                item=inv_item,
                branch=po.branch or inv_item.branch,
                movement_type=StockMovement.MovementType.PO_RECEIPT,
                quantity=qty,
                reason=f"Received via Purchase Order {po.po_number}",
                reference=po.po_number,
                performed_by=request.user if request.user.is_authenticated else None,
            )

        po.status = PurchaseOrder.Status.RECEIVED
        po.received_at = now
        po.save(update_fields=["status", "received_at"])

        return Response(PurchaseOrderSerializer(po).data, status=status.HTTP_200_OK)


class StockMovementListView(generics.ListAPIView):
    serializer_class = StockMovementSerializer
    permission_classes = [IsRestaurantStaff]

    def get_queryset(self):
        qs = StockMovement.objects.select_related(
            "item", "branch", "performed_by"
        ).all()
        item = self.request.query_params.get("item")
        movement_type = self.request.query_params.get("movement_type")
        if item:
            qs = qs.filter(item_id=item)
        if movement_type:
            qs = qs.filter(movement_type=movement_type)
        return qs[:200]
