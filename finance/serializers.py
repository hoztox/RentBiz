

from rest_framework import serializers
 
from .models import *
from decimal import Decimal
from company.serializers import *
from company.models import *
from django.db.models import Sum
from django.core.exceptions import ValidationError


class ExpenseSerializer(serializers.ModelSerializer):
    # Read-only fields for display
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
        
        # Validation for tenancy type
        if expense_type == 'tenancy':
            if not data.get('tenant'):
                raise serializers.ValidationError("Tenant is required for tenancy expenses")
            if not data.get('unit'):
                raise serializers.ValidationError("Unit is required for tenancy expenses")
        
        # Building is required for both types
        if not data.get('building'):
            raise serializers.ValidationError("Building is required")
            
        return data

    def create(self, validated_data):
        # Calculate tax and total amount before creating
        amount = validated_data.get('amount', 0)
        charge_type = validated_data.get('charge_type')
        
        if charge_type and amount:
            # Calculate total tax from all associated taxes
            total_tax_percentage = Decimal('0')
            
            # Get all active taxes associated with this charge
            current_date = timezone.now().date()
            for tax in charge_type.taxes.filter(is_active=True):
                if (tax.applicable_from <= current_date and 
                    (tax.applicable_to is None or tax.applicable_to >= current_date)):
                    total_tax_percentage += tax.tax_percentage
            
            # If no specific taxes, use vat_percentage from charge
            if total_tax_percentage == 0 and charge_type.vat_percentage:
                total_tax_percentage = Decimal(str(charge_type.vat_percentage))
            
            tax_amount = (amount * total_tax_percentage) / 100
            total_amount = amount + tax_amount
            
            validated_data['tax'] = tax_amount
            validated_data['total_amount'] = total_amount
        
        return super().create(validated_data)
    


class ExpenseGetSerializer(serializers.ModelSerializer):  
    building = BuildingSerializer()
    tenancy = TenancyListSerializer()
    charge_type = ChargesGetSerializer()
    unit = UnitSerializer()
    tenant = TenantSerializer()
    
    
    class Meta:
        model = Expense
        fields = '__all__'
        
class InvoiceSerializer(serializers.ModelSerializer):
    tenancy_name = serializers.CharField(source='tenancy.__str__', read_only=True)
    
    class Meta:
        model = Invoice
        fields = ['id', 'invoice_number', 'tenancy', 'tenancy_name', 'total_amount', 'status', 'in_date', 'end_date']
        

class CollectionSerializer(serializers.ModelSerializer):
    invoice = serializers.PrimaryKeyRelatedField(queryset=Invoice.objects.all())
    tenancy_id = serializers.CharField(source='invoice.tenancy_id', read_only=True)
    tenant_name = serializers.CharField(source='invoice.tenancy.tenant_name', read_only=True)

    class Meta:
        model = Collection
        fields = [
            'id', 'invoice', 'amount', 'collection_date', 'collection_mode',
            'reference_number', 'status', 'account_holder_name',
            'account_number', 'cheque_number', 'cheque_date',
            'tenancy_id', 'tenant_name'
        ]

    def validate(self, data):
        invoice = data['invoice']
        if invoice.status != 'unpaid':
            raise serializers.ValidationError("Can only create collections for unpaid invoices")
        total_collected = sum(collection.amount for collection in invoice.collections.all()) + data['amount']
        if total_collected > invoice.total_amount:
            raise serializers.ValidationError("Collection amount exceeds invoice total")
        return data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['collection_date'] = instance.collection_date.strftime('%d %b %Y')
        representation['amount'] = f"{instance.amount:.2f}"
        return representation