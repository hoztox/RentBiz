
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Collection
from company.models import Invoice, PaymentSchedule, AdditionalCharge
from .serializers import InvoiceSerializer, CollectionSerializer
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import render
from rentbiz.utils.pagination import paginate_queryset

# Create your views here.
from django.shortcuts import render, get_object_or_404
 
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
 
from datetime import datetime, timedelta, date
 
from urllib.parse import quote
from collections import defaultdict
import re
import logging
logger = logging.getLogger(__name__)
from decimal import Decimal
from company.models import *
from company.serializers import *
from .serializers import *


class CalculateTotalView(APIView):
    def _validate_request_data(self, data):
        logger.debug("=== Starting Request Data Validation ===")
        logger.debug(f"Input data: {data}")
        try:
            required_fields = ['company', 'charge_type', 'amount', 'due_date']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                logger.error(f"Missing required fields: {', '.join(missing_fields)}")
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            logger.debug("All required fields present")
            try:
                due_date_str = data['due_date']
                logger.debug(f"Validating due_date: {due_date_str}")
                datetime.strptime(due_date_str, '%Y-%m-%d')
                logger.debug("Due date format is valid")
            except ValueError as e:
                logger.error(f"Invalid date format for due_date: {str(e)}. Expected YYYY-MM-DD")
                raise ValueError("Invalid date format for due_date. Expected YYYY-MM-DD")

            validated_data = {
                'company_id': int(data.get('company')),
                'charge_type_id': int(data.get('charge_type')),
                'amount': Decimal(str(data.get('amount'))),
                'due_date': data.get('due_date')  # Fixed: Changed 'date' to 'due_date'
            }
            logger.debug(f"Constructed validated_data: {validated_data}")

            if validated_data['amount'] < 0:
                logger.error("Amount is negative")
                raise ValueError("Amount must be non-negative")

            logger.debug("Data validation successful")
            return validated_data
        except (ValueError, TypeError) as e:
            logger.error(f"Data validation error: {str(e)}")
            raise ValueError(f"Data validation error: {str(e)}")

    def _calculate_tax(self, amount, charge, reference_date):
        logger.debug("=== Starting Tax Calculation ===")
        logger.debug(f"Input - Amount: {amount}, Charge: {charge.name}, Reference Date: {reference_date}")
        try:
            tax_amount = Decimal('0.00')
            tax_details = []
            logger.debug(f"Attempting to parse reference_date: {reference_date}")
            if reference_date is None:
                logger.error("Reference date is None")
                raise ValueError("Reference date cannot be None")

            reference_date_obj = datetime.strptime(reference_date, '%Y-%m-%d').date()
            logger.debug(f"Parsed reference_date: {reference_date_obj}")

            # Filter applicable taxes
            logger.debug("Fetching applicable taxes")
            applicable_taxes = charge.taxes.filter(
                company=charge.company,
                is_active=True,
                applicable_from__lte=reference_date_obj,
                applicable_to__gte=reference_date_obj
            ) | charge.taxes.filter(
                company=charge.company,
                is_active=True,
                applicable_from__lte=reference_date_obj,
                applicable_to__isnull=True
            )
            logger.debug(f"Found {applicable_taxes.count()} applicable taxes")

            logger.debug("Applicable Taxes:")
            for tax in applicable_taxes:
                logger.debug(f"- {tax.tax_type}: {tax.tax_percentage}%")

            # Calculate taxes
            for tax in applicable_taxes:
                tax_percentage = Decimal(str(tax.tax_percentage))
                tax_contribution = (amount * tax_percentage) / Decimal('100')
                tax_amount += tax_contribution
                tax_details.append({
                    'tax_type': tax.tax_type,
                    'tax_percentage': str(tax_percentage),
                    'tax_amount': str(tax_contribution.quantize(Decimal('0.01')))
                })
                logger.debug(f"Calculated tax - {tax.tax_type}: {tax_contribution} ({tax_percentage}%)")

            # Add VAT if applicable
            if charge.vat_percentage:
                vat_percentage = Decimal(str(charge.vat_percentage))
                vat_amount = (amount * vat_percentage) / Decimal('100')
                tax_amount += vat_amount
                tax_details.append({
                    'tax_type': 'VAT',
                    'tax_percentage': str(vat_percentage),
                    'tax_amount': str(vat_amount.quantize(Decimal('0.01')))
                })
                logger.debug(f"VAT Amount: {vat_amount} ({vat_percentage}%)")

            logger.debug(f"Total Tax Amount: {tax_amount.quantize(Decimal('0.01'))}")
            logger.debug(f"Tax Details: {tax_details}")
            return tax_amount.quantize(Decimal('0.01')), tax_details
        except Exception as e:
            logger.error(f"Error calculating tax: {str(e)}")
            return Decimal('0.00'), []

    def post(self, request):
        logger.debug("=== Processing POST Request ===")
        logger.debug(f"Request Data: {request.data}")
        try:
            # Validate request data
            validated_data = self._validate_request_data(request.data)
            logger.debug(f"Validated Data: {validated_data}")

            amount = validated_data['amount']
            charge_id = validated_data['charge_type_id']
            company_id = validated_data['company_id']
            due_date = validated_data['due_date']

            logger.debug(f"Extracted - Amount: {amount}, Charge ID: {charge_id}, Company ID: {company_id}, Due Date: {due_date}")

            # Fetch the charge
            logger.debug(f"Fetching charge with ID {charge_id} for company {company_id}")
            charge = Charges.objects.filter(
                id=charge_id,
                company_id=company_id
            ).first()

            if not charge:
                logger.error(f"Charge ID {charge_id} not found for company {company_id}")
                return Response({
                    'error': f"Charge type with id {charge_id} not found"
                }, status=status.HTTP_400_BAD_REQUEST)

            logger.debug("Charge Retrieved:")
            logger.debug(f"Name: {charge.name}, VAT: {charge.vat_percentage}")
            logger.debug(f"Taxes Linked to Charge: {list(charge.taxes.all())}")

            # Calculate tax and get details
            logger.debug("Calculating tax")
            tax_amount, tax_details = self._calculate_tax(amount, charge, due_date)

            # Calculate total amount
            total_amount = amount + tax_amount
            logger.debug("=== Calculation Summary ===")
            logger.debug(f"Tax Amount: {tax_amount}")
            logger.debug(f"Tax Details: {tax_details}")
            logger.debug(f"Total Amount: {total_amount}")

            response_data = {
                'tax': str(tax_amount),
                'total_amount': str(total_amount),
                'tax_details': tax_details
            }
            logger.debug(f"Response Data: {response_data}")
            return Response(response_data, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Charges.DoesNotExist:
            logger.error(f"Charge ID {charge_id} not found")
            return Response({
                'error': 'Invalid charge type'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 

class AddExpenseAPIView(APIView):
    def post(self, request):
        print("Received data:", request.data)
        serializer = ExpenseSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Expense added successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        # Print the errors to the console for debugging
        print("Validation errors:", serializer.errors)
        
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ExpensesByCompanyAPIView(APIView):
    def get(self, request, company_id):
        expenses = Expense.objects.filter(company_id=company_id).order_by('-created_at')
        serializer = ExpenseGetSerializer(expenses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



 
class ExpenseUpdateView(APIView):
    def get(self, request, pk):
        """Retrieve a specific expense for editing."""
        try:
            expense = get_object_or_404(Expense, pk=pk)
            serializer = ExpenseSerializer(expense)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Expense.DoesNotExist:
            return Response(
                {"error": "Expense not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, pk):
        """Update an existing expense."""
        try:
            expense = get_object_or_404(Expense, pk=pk)
            serializer = ExpenseSerializer(expense, data=request.data, partial=True)
            if serializer.is_valid():
                # Handle optional fields and validation
                validated_data = serializer.validated_data

                # Ensure tenancy-related fields are provided for tenancy expense type
                if validated_data.get('expense_type') == 'tenancy':
                    required_fields = ['tenancy', 'tenant', 'unit']
                    missing_fields = [field for field in required_fields if not validated_data.get(field)]
                    if missing_fields:
                        return Response(
                            {"error": f"Missing required fields for tenancy expense: {', '.join(missing_fields)}"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Expense.DoesNotExist:
            return Response(
                {"error": "Expense not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
            
            # Calculate total amount to be collected (balance)
            total_collected = sum(collection.amount for collection in invoice.collections.all())
            total_amount_to_collect = invoice.total_amount - total_collected

            # Calculate tax amounts from Taxes model
            tax_details = []
            total_tax_amount = 0
            for ps in payment_schedules:
                if ps.charge_type and ps.charge_type.taxes.exists():
                    for tax in ps.charge_type.taxes.all():
                        tax_amount = ps.amount * (tax.tax_percentage / 100)
                        total_tax_amount += tax_amount
                        tax_details.append({
                            'tax_type': tax.tax_type,
                            'tax_percentage': str(tax.tax_percentage),
                            'tax_amount': str(tax_amount),
                        })
            for ac in additional_charges:
                if ac.charge_type and ac.charge_type.taxes.exists():
                    for tax in ac.charge_type.taxes.all():
                        tax_amount = ac.amount * (tax.tax_percentage / 100)
                        total_tax_amount += tax_amount
                        tax_details.append({
                            'tax_type': tax.tax_type,
                            'tax_percentage': str(tax.tax_percentage),
                            'tax_amount': str(tax_amount),
                        })

            # Remove duplicate tax entries (based on tax_type and percentage)
            unique_tax_details = {f"{tax['tax_type']}:{tax['tax_percentage']}": tax for tax in tax_details}
            tax_details = list(unique_tax_details.values())

            response_data = {
                'invoice': InvoiceSerializer(invoice).data,
                'total_amount_to_collect': str(total_amount_to_collect),
                'total_tax_amount': str(total_tax_amount),
                'taxes': tax_details,
                'payment_schedules': [
                    {
                        'id': ps.id,
                        'charge_type': ps.charge_type.name if ps.charge_type else '',
                        'reason': ps.reason,
                        'due_date': ps.due_date,
                        'amount': str(ps.amount),
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
            print(f"Invoice status updated: {invoice.status}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        print(f"Serializer errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CollectionListAPIView(APIView):
    def get(self, request):
        # Get query parameters for search and filters
        search = request.query_params.get('search', '')
        payment_method = request.query_params.get('payment_method', '')
        status = request.query_params.get('status', '')

        # Base queryset
        collections = Collection.objects.select_related('invoice', 'invoice__tenancy', 'invoice__tenancy__tenant').all()

        # Apply search
        if search:
            collections = collections.filter(
                Q(id__icontains=search) |
                Q(invoice__tenancy__id__icontains=search) |
                Q(invoice__tenancy__tenant__tenant_name__icontains=search) |  
                Q(amount__icontains=search) |
                Q(collection_mode__icontains=search) |
                Q(status__icontains=search)
            )

        # Apply filters
        if payment_method:
            collections = collections.filter(collection_mode=payment_method)
        if status:
            collections = collections.filter(status=status)

        # Order by date descending
        collections = collections.order_by('-collection_date')

        # Paginate and serialize
        return paginate_queryset(collections, request, CollectionSerializer)