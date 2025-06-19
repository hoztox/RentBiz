from rest_framework import serializers
from .models import Collection
from company.models import Invoice, PaymentSchedule, AdditionalCharge


class InvoiceSerializer(serializers.ModelSerializer):
    tenancy_name = serializers.CharField(source='tenancy.__str__', read_only=True)
    
    class Meta:
        model = Invoice
        fields = ['id', 'invoice_number', 'tenancy', 'tenancy_name', 'total_amount', 'status', 'in_date', 'end_date']

class CollectionSerializer(serializers.ModelSerializer):
    invoice = serializers.PrimaryKeyRelatedField(queryset=Invoice.objects.all())
    
    class Meta:
        model = Collection
        fields = ['id', 'invoice', 'amount', 'collection_date', 'collection_mode', 'status', 'reference_number']
        
    def validate(self, data):
        invoice = data['invoice']
        if invoice.status != 'unpaid':
            raise serializers.ValidationError("Can only create collections for unpaid invoices")
        total_collected = sum(collection.amount for collection in invoice.collections.all()) + data['amount']
        if total_collected > invoice.total_amount:
            raise serializers.ValidationError("Collection amount exceeds invoice total")
        return data