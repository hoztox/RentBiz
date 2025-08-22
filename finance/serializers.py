from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
from .models import Expense, Collection, Invoice, Refund
from company.models import Charges
from company.serializers import (
    BuildingSerializer, TenancyListSerializer,
    ChargesGetSerializer, UnitSerializer, TenantSerializer
)


class ExpenseSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating Expense objects.

    Purpose:
        Handles serialization and validation of Expense model data for POST and PUT requests.
        Automatically calculates tax and total amount based on the associated charge type.
        Validates required fields based on expense type (e.g., tenancy expenses require tenant and unit).

    Fields:
        - All fields from the Expense model.
        - Read-only fields: tax, total_amount, created_at, tenant_name, building_name, unit_name, charge_name.
        - tenant_name: Derived from tenant.name.
        - building_name: Derived from building.name.
        - unit_name: Derived from unit.name.
        - charge_name: Derived from charge_type.name.

    Validation:
        - Ensures 'building' is provided for all expense types.
        - For 'tenancy' expense type, requires 'tenant' and 'unit'.
        - Calculates tax based on active taxes and VAT associated with the charge type.

    Usage:
        Used in AddExpenseAPIView (POST) and ExpenseUpdateView (PUT) to validate and save expense data.

    Example Request Data:
        {
            "company": 1,
            "expense_type": "tenancy",
            "tenant": 1,
            "unit": 1,
            "building": 1,
            "charge_type": 1,
            "amount": 500.00
        }
    """
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    building_name = serializers.CharField(source='building.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    charge_name = serializers.CharField(source='charge_type.name', read_only=True)

    class Meta:
        model = Expense
        fields = '__all__'
        read_only_fields = ['tax', 'total_amount', 'created_at']

    def validate(self, data):
        expense_type = data.get('expense_type')
        if expense_type == 'tenancy':
            if not data.get('tenant'):
                raise serializers.ValidationError("Tenant is required for tenancy expenses")
            if not data.get('unit'):
                raise serializers.ValidationError("Unit is required for tenancy expenses")
        if not data.get('building'):
            raise serializers.ValidationError("Building is required")
        return data

    def create(self, validated_data):
        try:
            amount = validated_data.get('amount', Decimal('0'))
            charge_type = validated_data.get('charge_type')
            if charge_type and amount:
                total_tax_percentage = Decimal('0')
                current_date = timezone.now().date()
                for tax in charge_type.taxes.filter(is_active=True):
                    if (tax.applicable_from <= current_date and
                            (tax.applicable_to is None or tax.applicable_to >= current_date)):
                        total_tax_percentage += tax.tax_percentage

                # Fallback to VAT if no tax records found
                if total_tax_percentage == 0 and charge_type.vat_percentage:
                    total_tax_percentage = Decimal(str(charge_type.vat_percentage))

                tax_amount = (amount * total_tax_percentage) / 100
                total_amount = amount * (1 + (total_tax_percentage / 100))

                validated_data['tax'] = tax_amount
                validated_data['total_amount'] = total_amount

            return super().create(validated_data)

        except Exception as e:
            raise serializers.ValidationError(f"Error calculating tax or creating expense: {str(e)}")
    def update(self, instance, validated_data):
        try:
            amount = validated_data.get('amount', instance.amount)
            charge_type = validated_data.get('charge_type', instance.charge_type)

            if charge_type and amount:
                total_tax_percentage = Decimal('0')
                current_date = timezone.now().date()

                for tax in charge_type.taxes.filter(is_active=True):
                    if (tax.applicable_from <= current_date and
                            (tax.applicable_to is None or tax.applicable_to >= current_date)):
                        total_tax_percentage += tax.tax_percentage

                if total_tax_percentage == 0 and charge_type.vat_percentage:
                    total_tax_percentage = Decimal(str(charge_type.vat_percentage))

                tax_amount = (amount * total_tax_percentage) / 100
                total_amount = amount * (1 + (total_tax_percentage / 100))

                validated_data['tax'] = tax_amount
                validated_data['total_amount'] = total_amount

            return super().update(instance, validated_data)

        except Exception as e:
            raise serializers.ValidationError(f"Error calculating tax or updating expense: {str(e)}")


class ExpenseGetSerializer(serializers.ModelSerializer):
    """
    Serializer for retrieving Expense objects with related data.

    Purpose:
        Used for GET requests to fetch detailed expense data, including nested representations
        of related models (building, tenancy, charge_type, unit, tenant).

    Fields:
        - All fields from the Expense model.
        - Nested serializers:
            - building: BuildingSerializer
            - tenancy: TenancyListSerializer
            - charge_type: ChargesGetSerializer
            - unit: UnitSerializer
            - tenant: TenantSerializer

    Usage:
        Used in ExpensesByCompanyAPIView and ExpenseUpdateView (GET) to return detailed expense data.

    """
    building = BuildingSerializer()
    tenancy = TenancyListSerializer()
    charge_type = ChargesGetSerializer()
    unit = UnitSerializer()
    tenant = TenantSerializer()

    class Meta:
        model = Expense
        fields = '__all__'


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Serializer for Invoice objects.

    Purpose:
        Serializes Invoice model data for display, including a derived tenancy name.
        Used primarily for listing and retrieving invoice details.

    Fields:
        - id, invoice_number, tenancy, total_amount, status, in_date, end_date
        - tenancy_name: Derived from tenancy.tenant.tenant_name (read-only)

    Usage:
        Used in UnpaidInvoicesAPIView and InvoiceDetailsAPIView to return invoice data.

    Optimization:
        Use select_related('tenancy__tenant') in the view's queryset to avoid N+1 queries.
    """
    tenancy_name = serializers.CharField(source='tenancy.tenant.tenant_name', read_only=True)


    class Meta:
        model = Invoice
        fields = ['id', 'invoice_number', 'tenancy', 'tenancy_name', 'total_amount', 'status', 'in_date', 'end_date']



class CollectionSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and retrieving Collection objects.

    Purpose:
        Handles serialization and validation of Collection model data for POST and GET requests.
        Validates that collections are only created for unpaid invoices.
        Formats collection_date and amount for display.

    Fields:
        - id, invoice, amount, collection_date, collection_mode, reference_number, status,
          account_holder_name, account_number, cheque_number, cheque_date
        - tenancy_id: Derived from invoice.tenancy_id (read-only)
        - tenant_name: Derived from invoice.tenancy.tenant_name (read-only)
        - invoice_status: Derived from invoice.status (read-only)

    Validation:
        - Ensures the associated invoice has 'unpaid' status.
        - Validates required fields via the model.

    Usage:
        Used in CollectionCreateAPIView (POST) and CollectionListAPIView (GET).

    Example Request Data (POST):
        {
            "invoice": 1,
            "amount": 1000.00,
            "collection_date": "2025-07-01",
            "collection_mode": "cash"
        }
    """
    invoice = serializers.PrimaryKeyRelatedField(queryset=Invoice.objects.all())
    tenancy_id = serializers.CharField(source='invoice.tenancy_id', read_only=True)
    tenant_name = serializers.CharField(source='invoice.tenancy.tenant.tenant_name', read_only=True)
    invoice_status = serializers.CharField(source='invoice.status', read_only=True)

    class Meta:
        model = Collection
        fields = [
            'id', 'invoice', 'amount', 'collection_date', 'collection_mode',
            'reference_number', 'status', 'account_holder_name',
            'account_number', 'cheque_number', 'cheque_date',
            'tenancy_id', 'tenant_name', 'invoice_status'
        ]

    def validate(self, data):
        invoice = data.get('invoice')
        # Only enforce 'unpaid' status for creation (when self.instance is None)
        if invoice and not self.instance and invoice.status != 'unpaid':
            raise serializers.ValidationError(
                f"Cannot create collection for invoice {invoice.id} with status '{invoice.status}'"
            )
        print(f"Serializer validation passed for invoice {invoice.id}, instance exists: {bool(self.instance)}")
        return data

    def to_representation(self, instance):
        try:
            representation = super().to_representation(instance)
            representation['collection_date'] = instance.collection_date.strftime('%d %b %Y')
            representation['amount'] = f"{instance.amount:.2f}"
            return representation
        except Exception as e:
            raise serializers.ValidationError(f"Error formatting collection data: {str(e)}")


class RefundSerializer(serializers.ModelSerializer):
    tenancy_id = serializers.CharField(source='tenancy.tenancy_code', allow_null=True)  
    tenant_name = serializers.CharField(source='tenancy.tenant.tenant_name', allow_null=True)
    status = serializers.CharField(default='Paid')

    class Meta:
        model = Refund
        fields = ['id', 'processed_date', 'tenancy_id', 'tenant_name', 'amount', 'refund_method', 'status']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['processed_date'] = instance.processed_date.strftime('%d %b %Y')
        representation['amount'] = f"{float(instance.amount):.2f}"
        return representation
