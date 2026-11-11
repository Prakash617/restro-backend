import secrets
from decimal import Decimal
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.accounts.permissions import IsRestaurantStaff
from .models import CashRegisterSession, Expense, TaxInvoice
from .serializers import (
    CashRegisterSessionSerializer,
    ExpenseSerializer,
    TaxInvoiceSerializer,
)


class CashRegisterSessionListCreateView(generics.ListCreateAPIView):
    serializer_class = CashRegisterSessionSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = CashRegisterSession.objects.select_related(
            "branch", "opened_by", "closed_by"
        ).all()
        status_param = self.request.query_params.get("status")
        branch = self.request.query_params.get("branch")
        if status_param:
            qs = qs.filter(status=status_param)
        if branch:
            qs = qs.filter(branch_id=branch)
        return qs

    def perform_create(self, serializer):
        session = serializer.save(
            opened_by=self.request.user if self.request.user.is_authenticated else None,
            status=CashRegisterSession.Status.OPEN,
        )
        AuditLog.objects.create(
            actor=self.request.user if self.request.user.is_authenticated else None,
            actor_name=getattr(self.request.user, "full_name", "Cashier"),
            branch=session.branch,
            action=AuditLog.Action.REGISTER_OPENED,
            target_model="CashRegisterSession",
            target_id=str(session.id),
            description=f"Opened {session.register_name} with opening float {session.opening_float}.",
            metadata_json={"opening_float": str(session.opening_float)},
        )


class CashRegisterSessionCloseView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        session = generics.get_object_or_404(CashRegisterSession, pk=pk)
        actual_cash = Decimal(
            str(
                request.data.get("actual_closing_cash")
                or session.expected_closing_cash
                or "0.00"
            )
        )
        notes = request.data.get("notes")
        session.actual_closing_cash = actual_cash
        session.status = CashRegisterSession.Status.CLOSED
        session.closed_by = request.user if request.user.is_authenticated else None
        session.closed_at = timezone.now()
        if notes is not None:
            session.notes = notes
        session.save()

        AuditLog.objects.create(
            actor=request.user if request.user.is_authenticated else None,
            actor_name=getattr(request.user, "full_name", "Cashier"),
            branch=session.branch,
            action=AuditLog.Action.REGISTER_CLOSED,
            target_model="CashRegisterSession",
            target_id=str(session.id),
            description=(
                f"Closed {session.register_name}. Expected: {session.expected_closing_cash}, "
                f"Actual: {session.actual_closing_cash}, Variance: {session.variance}."
            ),
            metadata_json={
                "expected": str(session.expected_closing_cash),
                "actual": str(session.actual_closing_cash),
                "variance": str(session.variance),
            },
        )
        return Response(
            CashRegisterSessionSerializer(session).data,
            status=status.HTTP_200_OK,
        )


class TaxInvoiceListView(generics.ListAPIView):
    serializer_class = TaxInvoiceSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = TaxInvoice.objects.select_related("order", "branch").all()
        branch = self.request.query_params.get("branch")
        is_void = self.request.query_params.get("is_void")
        if branch:
            qs = qs.filter(branch_id=branch)
        if is_void is not None:
            qs = qs.filter(is_void=is_void.lower() in ("true", "1"))
        return qs


class TaxInvoicePrintView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        invoice = generics.get_object_or_404(TaxInvoice, pk=pk)
        invoice.print_count += 1
        invoice.save(update_fields=["print_count"])
        data = TaxInvoiceSerializer(invoice).data
        data["is_copy"] = invoice.print_count > 1
        data["copy_flag"] = (
            "COPY OF ORIGINAL" if invoice.print_count > 1 else "ORIGINAL TAX INVOICE"
        )
        return Response(data, status=status.HTTP_200_OK)


class TaxInvoiceVoidView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        invoice = generics.get_object_or_404(TaxInvoice, pk=pk)
        reason = (
            request.data.get("void_reason")
            or request.data.get("reason")
            or "Voided by manager"
        )
        invoice.is_void = True
        invoice.void_reason = reason
        invoice.save(update_fields=["is_void", "void_reason"])

        AuditLog.objects.create(
            actor=request.user if request.user.is_authenticated else None,
            actor_name=getattr(request.user, "full_name", "Manager"),
            branch=invoice.branch,
            action=AuditLog.Action.ORDER_VOID,
            target_model="TaxInvoice",
            target_id=str(invoice.id),
            description=f"Voided tax invoice {invoice.invoice_number} ({reason}).",
            metadata_json={"invoice_number": invoice.invoice_number, "reason": reason},
        )
        return Response(
            TaxInvoiceSerializer(invoice).data,
            status=status.HTTP_200_OK,
        )


class ExpenseListCreateView(generics.ListCreateAPIView):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Expense.objects.select_related("branch", "recorded_by").all()
        category = self.request.query_params.get("category")
        branch = self.request.query_params.get("branch")
        if category:
            qs = qs.filter(category=category)
        if branch:
            qs = qs.filter(branch_id=branch)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            recorded_by=self.request.user if self.request.user.is_authenticated else None
        )


class ExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Expense.objects.select_related("branch", "recorded_by").all()
    serializer_class = ExpenseSerializer
    permission_classes = [IsRestaurantStaff]


class FinanceSummaryView(APIView):
    permission_classes = [IsRestaurantStaff]

    def get(self, request):
        from apps.branches.models import Branch
        from apps.orders.models import Order, OrderItem, PaymentTransaction

        branch_id = request.query_params.get("branch")
        orders_qs = Order.objects.exclude(status=Order.Status.CANCELLED)
        expenses_qs = Expense.objects.all()
        payments_qs = PaymentTransaction.objects.all()

        if branch_id:
            orders_qs = orders_qs.filter(branch_id=branch_id)
            expenses_qs = expenses_qs.filter(branch_id=branch_id)
            payments_qs = payments_qs.filter(order__branch_id=branch_id)

        totals = orders_qs.aggregate(
            gross_revenue=Sum("total_amount"),
            subtotal=Sum("subtotal"),
            discounts=Sum("discount_amount"),
            service_charge=Sum("service_charge"),
            vat_collected=Sum("tax_amount"),
            refunds=Sum("refund_amount"),
        )

        gross_revenue = totals["gross_revenue"] or Decimal("0.00")
        subtotal = totals["subtotal"] or Decimal("0.00")
        discounts = totals["discounts"] or Decimal("0.00")
        service_charge = totals["service_charge"] or Decimal("0.00")
        vat_collected = totals["vat_collected"] or Decimal("0.00")
        refunds = totals["refunds"] or Decimal("0.00")

        # Calculate estimated COGS from OrderItems -> MenuItem.cost_price
        cogs = Decimal("0.00")
        for oi in OrderItem.objects.select_related("menu_item").filter(
            order__in=orders_qs
        ):
            item_cost = (
                oi.menu_item.cost_price
                if oi.menu_item and oi.menu_item.cost_price
                else (oi.unit_price * Decimal("0.32"))
            )
            cogs += item_cost * Decimal(str(oi.quantity))

        total_expenses = (
            expenses_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        )
        net_profit = gross_revenue - vat_collected - cogs - total_expenses - refunds

        # Payment reconciliation by method
        reconciliation = {}
        for method_code, _ in PaymentTransaction.Method.choices:
            amt = (
                payments_qs.filter(method=method_code).aggregate(total=Sum("amount"))[
                    "total"
                ]
                or Decimal("0.00")
            )
            reconciliation[method_code] = float(round(amt, 2))

        # Also fallback to Order.payment_method if no PaymentTransaction rows for some orders
        if sum(reconciliation.values()) == 0:
            for method_code, _ in Order.PaymentMethod.choices:
                amt = (
                    orders_qs.filter(
                        payment_method=method_code, payment_status="PAID"
                    ).aggregate(total=Sum("total_amount"))["total"]
                    or Decimal("0.00")
                )
                reconciliation[method_code] = float(round(amt, 2))

        # Expense breakdown by category
        expenses_by_category = [
            {
                "category": item["category"],
                "amount": float(round(item["total"] or Decimal("0.00"), 2)),
            }
            for item in expenses_qs.values("category")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        ]

        # Branch comparison
        branch_comparison = []
        for b in Branch.objects.all():
            b_orders = Order.objects.filter(branch=b).exclude(
                status=Order.Status.CANCELLED
            )
            b_rev = (
                b_orders.aggregate(total=Sum("total_amount"))["total"]
                or Decimal("0.00")
            )
            b_exp = (
                Expense.objects.filter(branch=b).aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            )
            branch_comparison.append(
                {
                    "branch_id": b.id,
                    "branch_name": b.name,
                    "code": b.code,
                    "orders_count": b_orders.count(),
                    "revenue": float(round(b_rev, 2)),
                    "expenses": float(round(b_exp, 2)),
                    "net_contribution": float(round(b_rev - b_exp, 2)),
                }
            )

        open_registers = CashRegisterSessionSerializer(
            CashRegisterSession.objects.filter(
                status=CashRegisterSession.Status.OPEN
            )[:5],
            many=True,
        ).data

        return Response(
            {
                "gross_revenue": float(round(gross_revenue, 2)),
                "net_sales_subtotal": float(round(subtotal - discounts, 2)),
                "discounts_given": float(round(discounts, 2)),
                "service_charge_collected": float(round(service_charge, 2)),
                "vat_collected": float(round(vat_collected, 2)),
                "refunds_issued": float(round(refunds, 2)),
                "estimated_cogs": float(round(cogs, 2)),
                "operating_expenses": float(round(total_expenses, 2)),
                "net_profit": float(round(net_profit, 2)),
                "payment_reconciliation": reconciliation,
                "expenses_by_category": expenses_by_category,
                "branch_comparison": branch_comparison,
                "open_registers": open_registers,
                "total_tax_invoices": TaxInvoice.objects.filter(is_void=False).count(),
                "void_tax_invoices": TaxInvoice.objects.filter(is_void=True).count(),
            },
            status=status.HTTP_200_OK,
        )


class PaymentGatewayInitiateView(APIView):
    """Simulates/initiates eSewa, Khalti, Fonepay Dynamic QR, or Stripe payment payload."""

    permission_classes = [IsRestaurantStaff]

    def post(self, request):
        gateway = (request.data.get("gateway") or "FONEPAY").strip().upper()
        amount = Decimal(str(request.data.get("amount") or "0.00"))
        order_number = request.data.get("order_number") or f"ORD-{secrets.token_hex(3).upper()}"
        tenant = getattr(request, "tenant", None)
        merchant_name = tenant.name if tenant else "RestoCloud Merchant"

        tx_ref = f"{gateway}-{secrets.token_hex(4).upper()}"
        qr_payload = (
            f"fonepay://pay?merchant={merchant_name}&amount={amount}&ref={tx_ref}&order={order_number}"
            if gateway in ("FONEPAY", "ESEWA", "KHALTI", "QR_WALLET")
            else f"https://checkout.stripe.com/pay/{tx_ref}"
        )

        return Response(
            {
                "gateway": gateway,
                "merchant_name": merchant_name,
                "order_number": order_number,
                "amount": str(round(amount, 2)),
                "currency": getattr(tenant, "currency", "NPR"),
                "transaction_reference": tx_ref,
                "status": "INITIATED",
                "qr_string": qr_payload,
                "expires_in_seconds": 300,
                "instructions": f"Scan {gateway} Dynamic QR or confirm payment of {amount} for {order_number}.",
            },
            status=status.HTTP_200_OK,
        )
