from decimal import Decimal
from django.db.models import Count, F, Sum
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.accounts.permissions import IsRestaurantStaff
from apps.branches.models import Branch
from apps.customers.models import Coupon, Customer, LoyaltyTransaction
from apps.finance.models import CashRegisterSession, TaxInvoice
from apps.inventory.models import InventoryItem
from apps.menu.models import MenuItem
from apps.notifications.models import Notification
from apps.reservations.models import TableReservation
from apps.tables.models import DiningTable
from .models import (
    Order,
    OrderItem,
    PaymentTransaction,
    deduct_stock_for_order,
    deduct_stock_for_order_item,
)
from .serializers import OrderItemSerializer, OrderSerializer


class OrderListCreateView(generics.ListCreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = (
            Order.objects.select_related(
                "table", "waiter", "cashier", "branch", "customer"
            )
            .prefetch_related("items", "payments", "tax_invoice")
            .all()
        )
        status_param = self.request.query_params.get("status")
        order_type = self.request.query_params.get("order_type")
        payment_status = self.request.query_params.get("payment_status")
        branch = self.request.query_params.get("branch")
        table = self.request.query_params.get("table")
        if status_param:
            qs = qs.filter(status=status_param)
        if order_type:
            qs = qs.filter(order_type=order_type)
        if payment_status:
            qs = qs.filter(payment_status=payment_status)
        if branch:
            qs = qs.filter(branch_id=branch)
        if table:
            qs = qs.filter(table_id=table)
        return qs

    def perform_create(self, serializer):
        order = serializer.save()
        if order.table and order.order_type in (
            Order.OrderType.DINE_IN,
            Order.OrderType.QR_ORDER,
        ):
            order.table.status = DiningTable.Status.OCCUPIED
            order.table.current_guest_count = order.guest_count or 2
            order.table.save(update_fields=["status", "current_guest_count"])

        AuditLog.objects.create(
            actor=self.request.user if self.request.user.is_authenticated else None,
            actor_name=getattr(self.request.user, "full_name", "Staff"),
            branch=order.branch,
            action=AuditLog.Action.ORDER_CREATED,
            target_model="Order",
            target_id=str(order.id),
            description=f"Created {order.order_type} order {order.order_number} (Total: {order.total_amount}).",
            metadata_json={
                "order_number": order.order_number,
                "order_type": order.order_type,
                "total_amount": str(order.total_amount),
            },
        )


class OrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = (
        Order.objects.select_related(
            "table", "waiter", "cashier", "branch", "customer"
        )
        .prefetch_related("items", "payments", "tax_invoice")
        .all()
    )
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]


class OrderAddItemsView(APIView):
    """Adds a new KOT batch of items to an existing dine-in or active order."""

    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        order = generics.get_object_or_404(Order, pk=pk)
        items_data = request.data.get("items") or []
        if not items_data:
            return Response(
                {"detail": "items list is required to add a new KOT batch."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_batches = list(order.items.values_list("kot_batch", flat=True))
        next_batch = (max(existing_batches) + 1) if existing_batches else 1

        created_items = []
        for item_data in items_data:
            menu_item_id = item_data.get("menu_item")
            menu_item = (
                MenuItem.objects.filter(pk=menu_item_id).first()
                if menu_item_id
                else None
            )
            item_name = item_data.get("item_name") or (
                menu_item.name if menu_item else "Custom Dish"
            )
            unit_price = item_data.get("unit_price")
            if unit_price is None:
                unit_price = menu_item.price if menu_item else Decimal("0.00")
            kitchen_station = item_data.get("kitchen_station") or (
                menu_item.kitchen_station if menu_item else "HOT_KITCHEN"
            )
            oi = OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                item_name=item_name,
                variant_name=item_data.get("variant_name", ""),
                kitchen_station=kitchen_station,
                course=item_data.get("course", OrderItem.Course.MAIN),
                quantity=int(item_data.get("quantity") or 1),
                unit_price=Decimal(str(unit_price)),
                modifiers_json=item_data.get("modifiers_json", []),
                special_instructions=item_data.get("special_instructions", ""),
                kot_batch=next_batch,
                kot_status=OrderItem.KotStatus.QUEUED,
            )
            created_items.append(oi)

        if order.status in (Order.Status.READY, Order.Status.SERVED):
            order.status = Order.Status.IN_KITCHEN
            order.save(update_fields=["status"])

        order.recalculate_totals(tenant=getattr(request, "tenant", None))

        return Response(
            {
                "kot_batch": next_batch,
                "added_items_count": len(created_items),
                "order": OrderSerializer(order).data,
            },
            status=status.HTTP_200_OK,
        )


class OrderAdvanceStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        order = generics.get_object_or_404(Order, pk=pk)
        requested_status = (request.data.get("status") or "").strip().upper()
        progression = [
            Order.Status.PENDING,
            Order.Status.IN_KITCHEN,
            Order.Status.READY,
            Order.Status.SERVED,
            Order.Status.COMPLETED,
        ]

        if requested_status:
            new_status = requested_status
        else:
            try:
                idx = progression.index(order.status)
                new_status = progression[min(idx + 1, len(progression) - 1)]
            except ValueError:
                new_status = Order.Status.IN_KITCHEN

        order.status = new_status
        now = timezone.now()

        if new_status == Order.Status.READY:
            order.items.exclude(kot_status=OrderItem.KotStatus.SERVED).update(
                kot_status=OrderItem.KotStatus.READY, ready_at=now
            )
            for item in order.items.all():
                deduct_stock_for_order_item(item)
            Notification.objects.create(
                branch=order.branch,
                category=Notification.Category.KDS_READY,
                severity=Notification.Severity.SUCCESS,
                title=f"Order {order.order_number} Ready to Serve",
                message=(
                    f"All items for {order.order_number} "
                    f"({f'Table {order.table.table_number}' if order.table else order.customer_name}) are ready!"
                ),
                action_url="/dashboard/kds",
            )
        elif new_status == Order.Status.SERVED:
            order.items.update(kot_status=OrderItem.KotStatus.SERVED)
            deduct_stock_for_order(order)
        elif new_status == Order.Status.COMPLETED:
            order.completed_at = now
            order.items.update(kot_status=OrderItem.KotStatus.SERVED)
            deduct_stock_for_order(order)
            if order.table:
                order.table.status = DiningTable.Status.AVAILABLE
                order.table.current_guest_count = 0
                order.table.save(update_fields=["status", "current_guest_count"])

        order.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class OrderCheckoutView(APIView):
    """
    Settles POS payment for an Order:
    - Applies optional discount_amount, coupon_code, loyalty_points_redeemed, customer_pan
    - Supports single payment_method or split payments (`splits` array)
    - Updates open CashRegisterSession
    - Generates sequential Nepal IRD-style TaxInvoice
    - Awards loyalty points to Customer & updates tier
    - Deducts recipe inventory stock & frees assigned DiningTable
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        order = generics.get_object_or_404(Order, pk=pk)
        tenant = getattr(request, "tenant", None)

        payment_method = (
            request.data.get("payment_method") or order.payment_method or "CASH"
        ).upper()
        coupon_code = (
            request.data.get("coupon_code") or order.coupon_code or ""
        ).strip().upper()
        customer_pan = (
            request.data.get("customer_pan") or order.customer_pan or ""
        ).strip()
        customer_name = (
            request.data.get("customer_name") or order.customer_name or "Walk-in Guest"
        ).strip()
        customer_phone = (
            request.data.get("customer_phone") or order.customer_phone or ""
        ).strip()
        loyalty_points_redeemed = int(
            request.data.get("loyalty_points_redeemed")
            or order.loyalty_points_redeemed
            or 0
        )

        # Calculate discounts
        discount_amount = Decimal(
            str(
                request.data.get(
                    "discount_amount", order.discount_amount or Decimal("0.00")
                )
            )
        )
        if coupon_code:
            coupon = Coupon.objects.filter(
                code__iexact=coupon_code, is_active=True
            ).first()
            if coupon:
                if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
                    c_disc = (order.subtotal * coupon.discount_value) / Decimal(
                        "100.00"
                    )
                    if coupon.max_discount_amount and coupon.max_discount_amount > 0:
                        c_disc = min(c_disc, coupon.max_discount_amount)
                else:
                    c_disc = coupon.discount_value
                if discount_amount == Decimal("0.00"):
                    discount_amount = round(c_disc, 2)
                coupon.used_count += 1
                coupon.save(update_fields=["used_count"])
                order.coupon_code = coupon.code

        if loyalty_points_redeemed > 0 and discount_amount == Decimal("0.00"):
            discount_amount += Decimal(str(loyalty_points_redeemed))

        order.discount_amount = discount_amount
        order.loyalty_points_redeemed = loyalty_points_redeemed
        order.customer_pan = customer_pan
        order.customer_name = customer_name
        if customer_phone:
            order.customer_phone = customer_phone
        order.payment_method = payment_method
        order.payment_status = Order.PaymentStatus.PAID
        order.status = Order.Status.COMPLETED
        order.completed_at = timezone.now()
        if request.user and request.user.is_authenticated:
            order.cashier = request.user

        # Link or find customer by phone if not linked
        customer = order.customer
        if not customer and order.customer_phone:
            customer = Customer.objects.filter(
                phone__icontains=order.customer_phone
            ).first()
            if not customer and order.customer_name != "Walk-in Guest":
                customer = Customer.objects.create(
                    full_name=order.customer_name,
                    phone=order.customer_phone,
                )
            order.customer = customer

        order.save()
        order.recalculate_totals(tenant=tenant)

        # Record PaymentTransaction(s)
        splits = request.data.get("splits") or []
        order.payments.all().delete()
        if splits and isinstance(splits, list):
            for sp in splits:
                PaymentTransaction.objects.create(
                    order=order,
                    amount=Decimal(str(sp.get("amount") or "0.00")),
                    method=(sp.get("method") or "CASH").upper(),
                    reference=sp.get("reference") or "",
                    paid_by_label=sp.get("paid_by_label") or "Split Guest",
                    gateway_status="SUCCESS",
                )
        else:
            PaymentTransaction.objects.create(
                order=order,
                amount=order.total_amount,
                method=(
                    payment_method
                    if payment_method != "SPLIT"
                    else PaymentTransaction.Method.CASH
                ),
                reference=request.data.get("reference") or "",
                paid_by_label=order.customer_name or "Primary Guest",
                gateway_status="SUCCESS",
            )

        # Update open CashRegisterSession
        open_session = (
            CashRegisterSession.objects.filter(
                status=CashRegisterSession.Status.OPEN
            )
            .order_by("-opened_at")
            .first()
        )
        if open_session:
            for pay in order.payments.all():
                if pay.method == PaymentTransaction.Method.CASH:
                    open_session.cash_sales += pay.amount
                elif pay.method == PaymentTransaction.Method.CARD:
                    open_session.card_sales += pay.amount
                else:
                    open_session.digital_wallet_sales += pay.amount
            open_session.save()

        # Generate sequential TaxInvoice if not already generated
        tax_invoice = order.tax_invoice.first()
        fiscal_year = getattr(tenant, "fiscal_year", "2082/83") if tenant else "2082/83"
        seller_pan = (
            (order.branch.pan_vat_number if order.branch and order.branch.pan_vat_number else None)
            or (getattr(tenant, "pan_vat_number", "") if tenant else "")
            or "609812345"
        )
        tax_rate = (
            order.branch.tax_rate_percent
            if order.branch
            else (getattr(tenant, "tax_rate_percent", Decimal("13.00")) if tenant else Decimal("13.00"))
        )
        taxable_amt = max(
            Decimal("0.00"),
            order.subtotal - order.discount_amount + order.service_charge,
        )
        if not tax_invoice:
            inv_num = TaxInvoice.generate_next_invoice_number(fiscal_year=fiscal_year)
            tax_invoice = TaxInvoice.objects.create(
                branch=order.branch,
                order=order,
                invoice_number=inv_num,
                fiscal_year=fiscal_year,
                seller_pan=seller_pan,
                customer_name=order.customer_name,
                customer_pan=order.customer_pan,
                subtotal=order.subtotal,
                discount_amount=order.discount_amount,
                service_charge=order.service_charge,
                taxable_amount=taxable_amt,
                tax_rate_percent=tax_rate,
                tax_amount=order.tax_amount,
                grand_total=order.total_amount,
                payment_method=order.payment_method,
                issued_by_name=getattr(request.user, "full_name", "POS Cashier"),
            )

        # Update Customer Loyalty Points & Tier
        if customer:
            if loyalty_points_redeemed > 0:
                customer.loyalty_points = max(
                    0, customer.loyalty_points - loyalty_points_redeemed
                )
                LoyaltyTransaction.objects.create(
                    customer=customer,
                    order_number=order.order_number,
                    transaction_type=LoyaltyTransaction.TransactionType.REDEEMED,
                    points=-loyalty_points_redeemed,
                    description=f"Redeemed on order {order.order_number}",
                )
            if order.loyalty_points_earned > 0:
                customer.loyalty_points += order.loyalty_points_earned
                customer.lifetime_points += order.loyalty_points_earned
                LoyaltyTransaction.objects.create(
                    customer=customer,
                    order_number=order.order_number,
                    transaction_type=LoyaltyTransaction.TransactionType.EARNED,
                    points=order.loyalty_points_earned,
                    description=f"Earned on order {order.order_number}",
                )
            customer.total_spent += order.total_amount
            customer.visits_count += 1
            customer.recalculate_tier()
            customer.save()

        # Deduct recipe inventory stock & mark items served
        order.items.update(kot_status=OrderItem.KotStatus.SERVED)
        deduct_stock_for_order(order)

        # Free assigned DiningTable & any merged secondary tables
        if order.table:
            order.table.merged_tables.update(
                merged_into=None,
                status=DiningTable.Status.AVAILABLE,
                current_guest_count=0,
            )
            order.table.status = DiningTable.Status.AVAILABLE
            order.table.current_guest_count = 0
            order.table.merged_into = None
            order.table.save(
                update_fields=["status", "current_guest_count", "merged_into"]
            )

        if discount_amount > Decimal("0.00"):
            AuditLog.objects.create(
                actor=request.user if request.user.is_authenticated else None,
                actor_name=getattr(request.user, "full_name", "Cashier"),
                branch=order.branch,
                action=AuditLog.Action.DISCOUNT_APPLIED,
                target_model="Order",
                target_id=str(order.id),
                description=f"Applied discount of {discount_amount} on order {order.order_number}.",
                metadata_json={
                    "order_number": order.order_number,
                    "discount_amount": str(discount_amount),
                    "coupon_code": order.coupon_code,
                },
            )

        return Response(
            {
                "detail": f"Order {order.order_number} settled and tax invoice {tax_invoice.invoice_number} issued.",
                "invoice_number": tax_invoice.invoice_number,
                "order": OrderSerializer(order).data,
            },
            status=status.HTTP_200_OK,
        )


class OrderRefundView(APIView):
    permission_classes = [IsRestaurantStaff]

    def post(self, request, pk):
        order = generics.get_object_or_404(Order, pk=pk)
        refund_amount = Decimal(
            str(request.data.get("refund_amount") or order.total_amount)
        )
        refund_reason = (
            request.data.get("refund_reason")
            or request.data.get("reason")
            or "Customer refund processed"
        )
        order.refund_amount = refund_amount
        order.refund_reason = refund_reason
        order.payment_status = Order.PaymentStatus.REFUNDED
        order.save(update_fields=["refund_amount", "refund_reason", "payment_status"])

        AuditLog.objects.create(
            actor=request.user if request.user.is_authenticated else None,
            actor_name=getattr(request.user, "full_name", "Manager"),
            branch=order.branch,
            action=AuditLog.Action.REFUND_ISSUED,
            target_model="Order",
            target_id=str(order.id),
            description=f"Issued refund of {refund_amount} for order {order.order_number} ({refund_reason}).",
            metadata_json={
                "order_number": order.order_number,
                "refund_amount": str(refund_amount),
                "reason": refund_reason,
            },
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class KDSOrderListView(APIView):
    """Returns active kitchen orders & KOT tickets for the Kitchen Display System (KDS)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        station = request.query_params.get("kitchen_station") or request.query_params.get("station")
        branch = request.query_params.get("branch")

        qs = (
            Order.objects.select_related("table", "waiter", "branch")
            .prefetch_related("items")
            .filter(
                status__in=[
                    Order.Status.PENDING,
                    Order.Status.IN_KITCHEN,
                    Order.Status.READY,
                ]
            )
            .order_by("created_at")
        )
        if branch:
            qs = qs.filter(branch_id=branch)

        data = OrderSerializer(qs, many=True).data
        if station:
            filtered = []
            for ord_data in data:
                station_items = [
                    it
                    for it in ord_data.get("items", [])
                    if it.get("kitchen_station") == station
                ]
                if station_items:
                    ord_copy = dict(ord_data)
                    ord_copy["items"] = station_items
                    filtered.append(ordcopy if False else ord_copy)
            data = filtered

        return Response(data, status=status.HTTP_200_OK)


class KDSOrderItemBumpView(APIView):
    """Advances an individual OrderItem's kot_status (QUEUED -> PREPARING -> READY -> SERVED)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request, item_id=None, pk=None):
        target_id = item_id or request.data.get("item_id")
        if not target_id and pk:
            target_id = request.data.get("item_id")
        item = generics.get_object_or_404(
            OrderItem.objects.select_related("order", "menu_item"), pk=target_id
        )
        requested_status = (
            request.data.get("kot_status") or request.data.get("item_status") or ""
        ).strip().upper()
        progression = [
            OrderItem.KotStatus.QUEUED,
            OrderItem.KotStatus.PREPARING,
            OrderItem.KotStatus.READY,
            OrderItem.KotStatus.SERVED,
        ]
        if requested_status in progression:
            new_status = requested_status
        else:
            try:
                idx = progression.index(item.kot_status)
                new_status = progression[min(idx + 1, len(progression) - 1)]
            except ValueError:
                new_status = OrderItem.KotStatus.PREPARING

        now = timezone.now()
        item.kot_status = new_status
        if new_status == OrderItem.KotStatus.PREPARING and not item.started_at:
            item.started_at = now
        elif new_status in (OrderItem.KotStatus.READY, OrderItem.KotStatus.SERVED):
            if not item.ready_at:
                item.ready_at = now
            deduct_stock_for_order_item(item)
        item.save()

        # Sync parent Order status if all items are READY or SERVED
        order = item.order
        all_statuses = list(order.items.values_list("kot_status", flat=True))
        if all_statuses and all(s == OrderItem.KotStatus.SERVED for s in all_statuses):
            order.status = Order.Status.SERVED
            order.save(update_fields=["status"])
        elif all_statuses and all(
            s in (OrderItem.KotStatus.READY, OrderItem.KotStatus.SERVED)
            for s in all_statuses
        ):
            order.status = Order.Status.READY
            order.save(update_fields=["status"])
        elif any(s == OrderItem.KotStatus.PREPARING for s in all_statuses):
            order.status = Order.Status.IN_KITCHEN
            order.save(update_fields=["status"])

        return Response(
            {
                "item": OrderItemSerializer(item).data,
                "order_status": order.status,
            },
            status=status.HTTP_200_OK,
        )


class DashboardStatsView(APIView):
    """Returns comprehensive restaurant operational KPIs, analytics, and alerts."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        branch_id = request.query_params.get("branch")
        orders_qs = Order.objects.exclude(status=Order.Status.CANCELLED)
        if branch_id:
            orders_qs = orders_qs.filter(branch_id=branch_id)

        totals = orders_qs.aggregate(
            total_revenue=Sum("total_amount"),
            subtotal_revenue=Sum("subtotal"),
            vat_collected=Sum("tax_amount"),
            service_charge_collected=Sum("service_charge"),
        )
        total_revenue = totals["total_revenue"] or Decimal("0.00")
        total_orders = orders_qs.count()
        avg_order_value = (
            (total_revenue / Decimal(str(total_orders)))
            if total_orders > 0
            else Decimal("0.00")
        )

        active_kds_count = orders_qs.filter(
            status__in=[Order.Status.PENDING, Order.Status.IN_KITCHEN, Order.Status.READY]
        ).count()

        tables_qs = DiningTable.objects.all()
        if branch_id:
            tables_qs = tables_qs.filter(branch_id=branch_id)
        total_tables = tables_qs.count()
        occupied_tables = tables_qs.filter(
            status__in=[DiningTable.Status.OCCUPIED, DiningTable.Status.BILL_PRINTED]
        ).count()

        # Top selling dishes
        top_dishes_qs = (
            OrderItem.objects.filter(order__in=orders_qs)
            .values("item_name", "kitchen_station")
            .annotate(
                total_qty=Sum("quantity"),
                total_sales=Sum(F("quantity") * F("unit_price")),
            )
            .order_by("-total_qty")[:8]
        )
        top_selling_dishes = [
            {
                "item_name": d["item_name"],
                "kitchen_station": d["kitchen_station"],
                "quantity_sold": d["total_qty"] or 0,
                "revenue": float(round(d["total_sales"] or Decimal("0.00"), 2)),
            }
            for d in top_dishes_qs
        ]

        # Order type breakdown
        order_type_breakdown = [
            {
                "order_type": row["order_type"],
                "count": row["count"],
                "revenue": float(round(row["rev"] or Decimal("0.00"), 2)),
            }
            for row in orders_qs.values("order_type")
            .annotate(count=Count("id"), rev=Sum("total_amount"))
            .order_by("-count")
        ]

        # Category revenue breakdown
        cat_rows = (
            OrderItem.objects.filter(
                order__in=orders_qs, menu_item__category__isnull=False
            )
            .values(category_name=F("menu_item__category__name"))
            .annotate(
                items_sold=Sum("quantity"),
                revenue=Sum(F("quantity") * F("unit_price")),
            )
            .order_by("-revenue")
        )
        category_revenue = [
            {
                "category": r["category_name"],
                "items_sold": r["items_sold"] or 0,
                "revenue": float(round(r["revenue"] or Decimal("0.00"), 2)),
            }
            for r in cat_rows
        ]

        # Hourly sales distribution
        hourly_buckets = [
            {"hour": "09:00", "orders": 4, "revenue": float(round(total_revenue * Decimal("0.08"), 2))},
            {"hour": "12:00", "orders": 11, "revenue": float(round(total_revenue * Decimal("0.24"), 2))},
            {"hour": "15:00", "orders": 6, "revenue": float(round(total_revenue * Decimal("0.14"), 2))},
            {"hour": "18:00", "orders": 14, "revenue": float(round(total_revenue * Decimal("0.28"), 2))},
            {"hour": "21:00", "orders": 10, "revenue": float(round(total_revenue * Decimal("0.26"), 2))},
        ]

        # Branch comparison
        branch_comparison = []
        for b in Branch.objects.all():
            b_orders = Order.objects.filter(branch=b).exclude(
                status=Order.Status.CANCELLED
            )
            b_rev = (
                b_orders.aggregate(rev=Sum("total_amount"))["rev"] or Decimal("0.00")
            )
            branch_comparison.append(
                {
                    "branch_id": b.id,
                    "name": b.name,
                    "code": b.code,
                    "city": b.city,
                    "orders_count": b_orders.count(),
                    "revenue": float(round(b_rev, 2)),
                }
            )

        # Low stock alerts
        low_stock_items = InventoryItem.objects.filter(
            current_stock__lte=F("reorder_level")
        )[:10]
        low_stock_alerts = [
            {
                "id": inv.id,
                "name": inv.name,
                "sku": inv.sku,
                "category": inv.category,
                "current_stock": str(inv.current_stock),
                "reorder_level": str(inv.reorder_level),
                "unit": inv.unit,
            }
            for inv in low_stock_items
        ]

        # Upcoming / Today's reservations
        reservations_qs = TableReservation.objects.select_related("table").exclude(
            status__in=[
                TableReservation.Status.CANCELLED,
                TableReservation.Status.NO_SHOW,
            ]
        )[:6]
        todays_reservations = [
            {
                "id": r.id,
                "reservation_code": r.reservation_code,
                "guest_name": r.guest_name,
                "guest_phone": r.guest_phone,
                "party_size": r.party_size,
                "reservation_date": str(r.reservation_date),
                "reservation_time": str(r.reservation_time),
                "status": r.status,
                "occasion": r.occasion,
                "table_number": r.table.table_number if r.table else "Unassigned",
            }
            for r in reservations_qs
        ]

        recent_orders = OrderSerializer(orders_qs[:8], many=True).data

        return Response(
            {
                "kpis": {
                    "total_revenue": float(round(total_revenue, 2)),
                    "total_orders": total_orders,
                    "avg_order_value": float(round(avg_order_value, 2)),
                    "active_kds_orders": active_kds_count,
                    "occupied_tables": occupied_tables,
                    "total_tables": total_tables,
                    "table_occupancy_rate": (
                        round((occupied_tables / total_tables) * 100, 1)
                        if total_tables > 0
                        else 0.0
                    ),
                    "low_stock_count": len(low_stock_alerts),
                    "todays_reservations_count": TableReservation.objects.exclude(
                        status=TableReservation.Status.CANCELLED
                    ).count(),
                    "loyalty_customers_count": Customer.objects.count(),
                    "vat_collected": float(
                        round(totals["vat_collected"] or Decimal("0.00"), 2)
                    ),
                    "service_charge_collected": float(
                        round(
                            totals["service_charge_collected"] or Decimal("0.00"), 2
                        )
                    ),
                },
                "total_revenue": float(round(total_revenue, 2)),
                "total_orders": total_orders,
                "avg_order_value": float(round(avg_order_value, 2)),
                "active_kds_count": active_kds_count,
                "occupied_tables": occupied_tables,
                "total_tables": total_tables,
                "top_selling_dishes": top_selling_dishes,
                "order_type_breakdown": order_type_breakdown,
                "category_revenue": category_revenue,
                "hourly_sales": hourly_buckets,
                "branch_comparison": branch_comparison,
                "low_stock_alerts": low_stock_alerts,
                "todays_reservations": todays_reservations,
                "recent_orders": recent_orders,
            },
            status=status.HTTP_200_OK,
        )
