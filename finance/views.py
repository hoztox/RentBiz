
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Collection
from company.models import Invoice, PaymentSchedule, AdditionalCharge
from .serializers import InvoiceSerializer, CollectionSerializer
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import render

# Create your views here.

class UnpaidInvoicesAPIView(APIView):
    def get(self, request):
        # Fetch unpaid invoices
        unpaid_invoices = Invoice.objects.filter(status='unpaid').select_related('tenancy')
        serializer = InvoiceSerializer(unpaid_invoices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class InvoiceDetailsAPIView(APIView):
    def get(self, request, invoice_id):
        try:
            invoice = Invoice.objects.get(id=invoice_id, status='unpaid')
            payment_schedules = invoice.payment_schedules.all()
            additional_charges = invoice.additional_charges.all()
            
            response_data = {
                'invoice': InvoiceSerializer(invoice).data,
                'payment_schedules': [
                    {
                        'id': ps.id,
                        'charge_type': ps.charge_type.name if ps.charge_type else '',
                        'reason': ps.reason,
                        'due_date': ps.due_date,
                        'amount': str(ps.amount),
                        'vat': str(ps.vat),
                        'tax': str(ps.tax),
                        'total': str(ps.total),
                        'balance': str(ps.total - sum(collection.amount for collection in Collection.objects.filter(invoice=invoice)))
                    } for ps in payment_schedules
                ],
                'additional_charges': [
                    {
                        'id': ac.id,
                        'charge_type': ac.charge_type.name if ac.charge_type else '',
                        'reason': ac.reason,
                        'due_date': ac.due_date,
                        'amount': str(ac.amount),
                        'vat': str(ac.vat),
                        'tax': str(ac.tax),
                        'total': str(ac.total),
                        'balance': str(ac.total - sum(collection.amount for collection in Collection.objects.filter(invoice=invoice)))
                    } for ac in additional_charges
                ]
            }
            return Response(response_data, status=status.HTTP_200_OK)
        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)

class CreateCollectionAPIView(APIView):
    def post(self, request):
        serializer = CollectionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            # Update invoice status if fully paid
            invoice = serializer.validated_data['invoice']
            total_collected = sum(collection.amount for collection in invoice.collections.all())
            if total_collected >= invoice.total_amount:
                invoice.status = 'paid'
                invoice.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)