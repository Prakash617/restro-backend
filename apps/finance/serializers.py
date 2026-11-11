from rest_framework import serializers
from .models import CashRegisterSession, Expense, TaxInvoice


class CashRegisterSessionSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(
        source="branch.name", read_only=True, default=""
    )
    opened_by_name = serializers.CharField(
        source="opened_by.full_name", read_only=True, default="Cashier"
    )
    closed_by_name = serializers.CharField(
        source="closed_by.full_name", read_only=True, default=""
    )

    class Meta:
        model = CashRegisterSession
        fields = [
            "id",
            "branch",
            "branch_name",
            "opened_by",
            "opened_by_name",
            "closed_by",
            "closed_by_name",
            "register_name",
            "status",
            "opening_float",
            "cash_sales",
            "card_sales",
            "digital_wallet_sales",
            "cash_in",
            "cash_out",
            "expected_closing_cash",
            "actual_closing_cash",
            "variance",
            "notes",
            "opened_at",
            "closed_at",
        ]
        read_only_fields = [
            "id",
            "branch_name",
            "opened_by_name",
            "closed_by_name",
            "expected_closing_cash",
            "variance",
            "opened_at",
            "closed_at",
        ]


class TaxInvoiceSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    branch_name = serializers.CharField(
        source="branch.name", read_only=True, default=""
    )
    copy_label = serializers.SerializerMethodField()

    class Meta:
        model = TaxInvoice
        fields = [
            "id",
            "branch",
            "branch_name",
            "order",
            "order_number",
            "invoice_number",
            "fiscal_year",
            "seller_pan",
            "customer_name",
            "customer_pan",
            "subtotal",
            "discount_amount",
            "service_charge",
            "taxable_amount",
            "tax_rate_percent",
            "tax_amount",
            "grand_total",
            "payment_method",
            "print_count",
            "copy_label",
            "is_void",
            "void_reason",
            "issued_by_name",
            "issued_at",
        ]
        read_only_fields = [
            "id",
            "branch_name",
            "order_number",
            "copy_label",
            "issued_at",
        ]

    def get_copy_label(self, obj):
        return "COPY OF ORIGINAL" if obj.print_count > 1 else "ORIGINAL TAX INVOICE"


class ExpenseSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(
        source="branch.name", read_only=True, default=""
    )
    recorded_by_name = serializers.CharField(
        source="recorded_by.full_name", read_only=True, default="Staff"
    )

    class Meta:
        model = Expense
        fields = [
            "id",
            "branch",
            "branch_name",
            "category",
            "title",
            "vendor_name",
            "amount",
            "payment_method",
            "reference_number",
            "expense_date",
            "notes",
            "recorded_by",
            "recorded_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "branch_name", "recorded_by_name", "created_at"]
