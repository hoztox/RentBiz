from django.shortcuts import render

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
        try:
            required_fields = ['company', 'charge_type', 'amount', 'due_date']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            try:
                datetime.strptime(data['due_date'], '%Y-%m-%d')
            except ValueError:
                raise ValueError("Invalid date format for due_date. Expected YYYY-MM-DD")

            validated_data = {
                'company_id': int(data.get('company')),
                'charge_type_id': int(data.get('charge_type')),
                'amount': Decimal(str(data.get('amount'))),
                'due_date': data.get('date')
            }

            if validated_data['amount'] < 0:
                raise ValueError("Amount must be non-negative")

            return validated_data
        except (ValueError, TypeError) as e:
            logger.error(f"Data validation error: {str(e)}")
            raise ValueError(f"Data validation error: {str(e)}")

    def _calculate_tax(self, amount, charge, reference_date):
        try:
            tax_amount = Decimal('0.00')
            tax_details = []
            reference_date_obj = datetime.strptime(reference_date, '%Y-%m-%d').date()

            # Filter applicable taxes
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

            return tax_amount.quantize(Decimal('0.01')), tax_details
        except Exception as e:
            logger.error(f"Error calculating tax: {str(e)}")
            return Decimal('0.00'), []

    def post(self, request):
        try:
            logger.debug("=== Incoming Request Data ===")
            logger.debug(request.data)

            # Validate request data
            validated_data = self._validate_request_data(request.data)
            logger.debug(f"Validated Data: {validated_data}")

            amount = validated_data['amount']
            charge_id = validated_data['charge_type_id']
            company_id = validated_data['company_id']
            due_date = validated_data['due_date']

            logger.debug(f"Amount: {amount}")
            logger.debug(f"Charge ID: {charge_id}")
            logger.debug(f"Company ID: {company_id}")
            logger.debug(f"Due Date: {due_date}")

            # Fetch the charge
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
            logger.debug(f"Name: {charge.name}")
            logger.debug(f"VAT: {charge.vat_percentage}")
            logger.debug("Taxes Linked to Charge:")
            logger.debug(charge.taxes.all())

            # Calculate tax and get details
            tax_amount, tax_details = self._calculate_tax(amount, charge, due_date)

            # Calculate total amount
            total_amount = amount + tax_amount

            logger.debug("=== Calculation Summary ===")
            logger.debug(f"Tax Amount: {tax_amount}")
            logger.debug(f"Tax Details: {tax_details}")
            logger.debug(f"Total Amount: {total_amount}")

            return Response({
                'tax': str(tax_amount),
                'total_amount': str(total_amount),
                'tax_details': tax_details
            }, status=status.HTTP_200_OK)

        except ValueError as e:
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