from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote
from collections import defaultdict
from .models import Collection
from company.models import (
    Invoice, PaymentSchedule, AdditionalCharge, Charges,
    Tenancy, ChargeCode, Users
)
from .models import Expense, Refund,Overpayment,PaymentDistribution
from .serializers import (
    InvoiceSerializer, CollectionSerializer, ExpenseSerializer,
    ExpenseGetSerializer, RefundSerializer
)
from rentbiz.utils.pagination import paginate_queryset
from django.db import transaction


class CalculateTotalView(APIView):
    """
    API to calculate the total amount including taxes for a given charge.

    Endpoint: POST /api/calculate-total/
    Purpose: Calculates the tax and total amount for a specified charge type, company, amount, and due date.
    Request Body:
        {
            "company": <company_id> (int, required),
            "charge_type": <charge_type_id> (int, required),
            "amount": <amount> (decimal, required),
            "due_date": <due_date> (string, YYYY-MM-DD, required)
        }
    Response:
        - 200 OK:
            {
                "tax": <tax_amount> (string),
                "total_amount": <total_amount> (string),
                "tax_details": [
                    {
                        "tax_type": <tax_type> (string),
                        "tax_percentage": <percentage> (string),
                        "tax_amount": <amount> (string)
                    },
                    ...
                ]
            }
        - 400 Bad Request: Invalid input data or missing fields.
        - 404 Not Found: Charge type not found.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X POST http://localhost:8000/api/calculate-total/ \
        -H "Content-Type: application/json" \
        -d '{"company": 1, "charge_type": 1, "amount": 100.00, "due_date": "2025-07-01"}'
    Example Response:
        {
            "tax": "18.00",
            "total_amount": "118.00",
            "tax_details": [
                {"tax_type": "GST", "tax_percentage": "18", "tax_amount": "18.00"}
            ]
        }
    """

    def _validate_request_data(self, data):
        required_fields = ['company', 'charge_type', 'amount', 'due_date']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        try:
            due_date_str = data['due_date']
            datetime.strptime(due_date_str, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Invalid date format for due_date. Expected YYYY-MM-DD")

        validated_data = {
            'company_id': int(data.get('company')),
            'charge_type_id': int(data.get('charge_type')),
            'amount': Decimal(str(data.get('amount'))),
            'due_date': data.get('due_date')
        }

        if validated_data['amount'] < 0:
            raise ValueError("Amount must be non-negative")

        return validated_data

    def _calculate_tax(self, amount, charge, reference_date):
        try:
            tax_amount = Decimal('0.00')
            tax_details = []

            if reference_date is None:
                raise ValueError("Reference date cannot be None")

            reference_date_obj = datetime.strptime(reference_date, '%Y-%m-%d').date()
            applicable_taxes = charge.taxes.filter(
                Q(company=charge.company, is_active=True, applicable_from__lte=reference_date_obj) &
                (Q(applicable_to__gte=reference_date_obj) | Q(applicable_to__isnull=True))
            )

            for tax in applicable_taxes:
                tax_percentage = Decimal(str(tax.tax_percentage))
                tax_contribution = (amount * tax_percentage) / Decimal('100')
                tax_amount += tax_contribution
                tax_details.append({
                    'tax_type': tax.tax_type,
                    'tax_percentage': str(tax_percentage),
                    'tax_amount': str(tax_contribution.quantize(Decimal('0.01')))
                })

            if charge.vat_percentage:
                vat_percentage = Decimal(str(charge.vat_percentage))
                vat_amount = (amount * vat_percentage) / Decimal('100')
                tax_amount += vat_amount
                tax_details.append({
                    'tax_type': 'VAT',
                    'tax_percentage': str(vat_percentage),
                    'tax_amount': str(vat_amount.quantize(Decimal('0.01')))
                })

            return tax_amount.quantize(Decimal('0.01')), tax_details
        except Exception:
            return Decimal('0.00'), []

    def post(self, request):
        try:
            validated_data = self._validate_request_data(request.data)
            amount = validated_data['amount']
            charge_id = validated_data['charge_type_id']
            company_id = validated_data['company_id']
            due_date = validated_data['due_date']

            charge = Charges.objects.filter(id=charge_id, company_id=company_id).first()
            if not charge:
                return Response(
                    {'error': f"Charge type with id {charge_id} not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            tax_amount, tax_details = self._calculate_tax(amount, charge, due_date)
            total_amount = amount + tax_amount

            response_data = {
                'tax': str(tax_amount),
                'total_amount': str(total_amount),
                'tax_details': tax_details
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Charges.DoesNotExist:
            return Response({'error': 'Invalid charge type'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AddExpenseAPIView(APIView):
    """
    API to add a new expense.

    Endpoint: POST /api/expenses/
    Purpose: Creates a new expense record based on provided data.
    Request Body:
        {
            "company": <company_id> (int, required),
            "expense_type": <expense_type> (string, e.g., 'tenancy' or 'general', required),
            "tenancy": <tenancy_id> (int, required if expense_type is 'tenancy'),
            "tenant": <tenant_id> (int, required if expense_type is 'tenancy'),
            "unit": <unit_id> (int, required if expense_type is 'tenancy'),
            "amount": <amount> (decimal, required),
            ...
        }
    Response:
        - 201 Created:
            {
                "message": "Expense added successfully",
                "data": <serialized_expense_data>
            }
        - 400 Bad Request: Invalid input data or validation errors.
    Example Request:
        curl -X POST http://localhost:8000/api/expenses/ \
        -H "Content-Type: application/json" \
        -d '{"company": 1, "expense_type": "general", "amount": 500.00}'
    Example Response:
        {
            "message": "Expense added successfully",
            "data": {
                "id": 1,
                "company": 1,
                "expense_type": "general",
                "amount": "500.00",
                ...
            }
        }
    """

    def post(self, request):
        try:
            serializer = ExpenseSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {
                        'message': 'Expense added successfully',
                        'data': serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExpensesByCompanyAPIView(APIView):
    """
    API to retrieve expenses for a specific company.

    Endpoint: GET /api/expenses/company/<company_id>/
    Purpose: Fetches all expenses associated with a given company ID, ordered by creation date (descending).
    Response:
        - 200 OK: List of serialized expense data.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X GET http://localhost:8000/api/expenses/company/1/
    Example Response:
        [
            {
                "id": 1,
                "company": 1,
                "expense_type": "general",
                "amount": "500.00",
                ...
            },
            ...
        ]
    """

    def get(self, request, company_id):
        try:
            expenses = Expense.objects.filter(company_id=company_id).order_by('-created_at')
            serializer = ExpenseGetSerializer(expenses, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExpenseUpdateView(APIView):
    """
    API to retrieve and update an existing expense.

    Endpoints:
        - GET /api/expenses/<pk>/
        - PUT /api/expenses/<pk>/
    Purpose:
        - GET: Retrieves details of a specific expense by ID.
        - PUT: Updates an existing expense with provided data.
    GET Response:
        - 200 OK: Serialized expense data.
        - 404 Not Found: Expense not found.
        - 500 Internal Server Error: Unexpected server error.
    PUT Request Body:
        {
            "expense_type": <expense_type> (string, optional),
            "tenancy": <tenancy_id> (int, required if expense_type is 'tenancy'),
            "tenant": <tenant_id> (int, required if expense_type is 'tenancy'),
            "unit": <unit_id> (int, required if expense_type is 'tenancy'),
            ...
        }
    PUT Response:
        - 200 OK: Updated serialized expense data.
        - 400 Bad Request: Invalid input data or missing required fields.
        - 404 Not Found: Expense not found.
        - 500 Internal Server Error: Unexpected server error.
    Example GET Request:
        curl -X GET http://localhost:8000/api/expenses/1/
    Example GET Response:
        {
            "id": 1,
            "company": 1,
            "expense_type": "general",
            ...
        }
    Example PUT Request:
        curl -X PUT http://localhost:8000/api/expenses/1/ \
        -H "Content-Type: application/json" \
        -d '{"expense_type": "tenancy", "tenancy": 1, "tenant": 1, "unit": 1}'
    Example PUT Response:
        {
            "id": 1,
            "expense_type": "tenancy",
            ...
        }
    """

    def get(self, request, pk):
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
        try:
            expense = get_object_or_404(Expense, pk=pk)
            serializer = ExpenseSerializer(expense, data=request.data, partial=True)
            if serializer.is_valid():
                validated_data = serializer.validated_data
                if validated_data.get('expense_type') == 'tenancy':
                    required_fields = ['tenancy', 'tenant', 'unit']
                    missing_fields = [field for field in required_fields if not validated_data.get(field)]
                    if missing_fields:
                        return Response(
                            {
                                "error": f"Missing required fields for tenancy expense: {', '.join(missing_fields)}"
                            },
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
    """
    API to retrieve all unpaid invoices.

    Endpoint: GET /api/invoices/unpaid/
    Purpose: Fetches all invoices with status 'unpaid', including related tenancy data.
    Response:
        - 200 OK: List of serialized unpaid invoice data.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X GET http://localhost:8000/api/invoices/unpaid/
    Example Response:
        [
            {
                "id": 1,
                "tenancy": {...},
                "status": "unpaid",
                ...
            },
            ...
        ]
    """

    def get(self, request):
        try:
            unpaid_invoices = Invoice.objects.filter(status='unpaid').select_related('tenancy')
            serializer = InvoiceSerializer(unpaid_invoices, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvoiceDetailsAPIView(APIView):
    """
    API to retrieve details of an unpaid invoice.

    Endpoint: GET /api/invoices/<invoice_id>/
    Purpose: Fetches details of an unpaid invoice, including payment schedules, additional charges,
             total amount to collect, and tax details.
    Response:
        - 200 OK:
            {
                "invoice": <serialized_invoice_data>,
                "total_amount_to_collect": <amount> (string),
                "total_tax_amount": <tax_amount> (string),
                "taxes": [
                    {
                        "tax_type": <tax_type> (string),
                        "tax_percentage": <percentage> (string),
                        "tax_amount": <amount> (string)
                    },
                    ...
                ],
                "payment_schedules": [...],
                "additional_charges": [...]
            }
        - 404 Not Found: Invoice not found.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X GET http://localhost:8000/api/invoices/1/
    Example Response:
        {
            "invoice": {...},
            "total_amount_to_collect": "1500.00",
            "total_tax_amount": "270.00",
            "taxes": [
                {"tax_type": "GST", "tax_percentage": "18", "tax_amount": "270.00"}
            ],
            "payment_schedules": [...],
            "additional_charges": [...]
        }
    """

    def get(self, request, invoice_id):
        try:
            invoice = Invoice.objects.get(id=invoice_id, status='unpaid')
            payment_schedules = invoice.payment_schedules.all()
            additional_charges = invoice.additional_charges.all()

            total_collected = sum(collection.amount for collection in invoice.collections.all())
            total_amount_to_collect = invoice.total_amount - total_collected

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
                            'tax_amount': str(tax_amount)
                        })
            for ac in additional_charges:
                if ac.charge_type and ac.charge_type.taxes.exists():
                    for tax in ac.charge_type.taxes.all():
                        tax_amount = ac.amount * (tax.tax_percentage / 100)
                        total_tax_amount += tax_amount
                        tax_details.append({
                            'tax_type': tax.tax_type,
                            'tax_percentage': str(tax.tax_percentage),
                            'tax_amount': str(tax_amount)
                        })

            unique_tax_details = {
                f"{tax['tax_type']}:{tax['tax_percentage']}": tax for tax in tax_details
            }
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
                        'balance': str(
                            ps.total - sum(
                                collection.amount for collection in Collection.objects.filter(invoice=invoice)
                            )
                        )
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
                        'balance': str(
                            ac.total - sum(
                                collection.amount for collection in Collection.objects.filter(invoice=invoice)
                            )
                        )
                    } for ac in additional_charges
                ]
            }
            return Response(response_data, status=status.HTTP_200_OK)
        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {'error': f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# class CollectionCreateAPIView(APIView):
#     """
#     API to create a new collection for an invoice.

#     Endpoint: POST /api/collections/
#     Purpose: Records a payment collection for an invoice, distributes it across payment schedules
#              and additional charges, handles overpayments, and updates invoice status.
#     Request Body:
#         {
#             "invoice": <invoice_id> (int, required),
#             "amount": <amount> (decimal, required),
#             "collection_mode": <payment_method> (string, required),
#             "collection_date": <date> (string, YYYY-MM-DD, required),
#             ...
#         }
#     Response:
#         - 201 Created: Serialized collection data.
#         - 400 Bad Request: Invalid input data.
#         - 500 Internal Server Error: Unexpected server error.
#     Example Request:
#         curl -X POST http://localhost:8000/api/collections/
#         -H "Content-Type: application/json" 
#         -d '{"invoice": 1, "amount": 200.00, "collection_mode": "cash", "collection_date": "2025-07-01"}'
#     Example Response:
#         {
#             "id": 1,
#             "invoice": 1,
#             "amount": "200.00",
#             "collection_mode": "cash",
#             ...
#         }
#     """

#     def post(self, request, *args, **kwargs):
#         try:
#             with transaction.atomic():
#                 serializer = CollectionSerializer(data=request.data)
#                 if not serializer.is_valid():
#                     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#                 collection = serializer.save()
#                 invoice = collection.invoice
#                 collection_amount = collection.amount

#                 payment_schedules = invoice.payment_schedules.all()
#                 additional_charges = invoice.additional_charges.all()
#                 components = list(payment_schedules) + list(additional_charges)
#                 total_components = len(components)

#                 if total_components == 0:
#                     return Response(
#                         {"error": "Invoice has no payment schedules or additional charges."},
#                         status=status.HTTP_400_BAD_REQUEST
#                     )

#                 total_outstanding = Decimal('0.00')
#                 for component in components:
#                     amount_paid = (
#                         PaymentDistribution.objects.filter(
#                             collection__invoice=invoice,
#                             collection__status='completed',
#                             payment_schedule=component if isinstance(component, PaymentSchedule) else None,
#                             additional_charge=component if isinstance(component, AdditionalCharge) else None
#                         ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
#                     )
#                     remaining_balance = (component.total or Decimal('0.00')) - amount_paid
#                     total_outstanding += remaining_balance

#                 overpayment_amount = Decimal('0.00')
#                 if collection_amount > total_outstanding:
#                     overpayment_amount = collection_amount - total_outstanding
#                     collection_amount = total_outstanding

#                 if collection_amount > 0:
#                     amount_per_component = collection_amount / total_components

#                     for component in components:
#                         amount_paid = (
#                             PaymentDistribution.objects.filter(
#                                 collection__invoice=invoice,
#                                 collection__status='completed',
#                                 payment_schedule=component if isinstance(component, PaymentSchedule) else None,
#                                 additional_charge=component if isinstance(component, AdditionalCharge) else None
#                             ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
#                         )
#                         remaining_balance = (component.total or Decimal('0.00')) - amount_paid
#                         distributed_amount = min(amount_per_component, remaining_balance)

#                         if distributed_amount > 0:
#                             PaymentDistribution.objects.create(
#                                 collection=collection,
#                                 payment_schedule=component if isinstance(component, PaymentSchedule) else None,
#                                 additional_charge=component if isinstance(component, AdditionalCharge) else None,
#                                 amount=distributed_amount
#                             )

#                         total_paid_for_component = amount_paid + (distributed_amount if distributed_amount > 0 else Decimal('0.00'))
#                         if total_paid_for_component >= (component.total or Decimal('0.00')):
#                             component.status = 'paid'
#                         elif total_paid_for_component > 0:
#                             component.status = 'partially_paid'
#                         else:
#                             component.status = 'pending'
#                         component.save()

#                 if overpayment_amount > 0:
#                     Overpayment.objects.create(
#                         tenancy=invoice.tenancy,
#                         invoice=invoice,
#                         collection=collection,
#                         amount=overpayment_amount,
#                         status='available'
#                     )

#                 total_collected = (
#                     Collection.objects.filter(invoice=invoice, status='completed')
#                     .aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
#                 )
#                 if total_collected >= invoice.total_amount:
#                     invoice.status = 'paid'
#                 elif total_collected > 0:
#                     invoice.status = 'partially_paid'
#                 else:
#                     invoice.status = 'unpaid'
#                 invoice.save()

#                 return Response(serializer.data, status=status.HTTP_201_CREATED)

#         except Exception as e:
#             return Response(
#                 {"error": f"An error occurred while processing the collection: {str(e)}"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )



class CollectionCreateAPIView(APIView):
    """
    API to create a new collection for an invoice.

    Endpoint: POST /api/collections/
    Purpose: Records a payment collection for an invoice, distributes it across payment schedules
             and additional charges sequentially, handles overpayments, and updates invoice status.
    """

    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                serializer = CollectionSerializer(data=request.data)
                if not serializer.is_valid():
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                collection = serializer.save()
                invoice = collection.invoice
                collection_amount = collection.amount

                payment_schedules = invoice.payment_schedules.all().order_by("due_date")
                additional_charges = invoice.additional_charges.all()
                components = list(payment_schedules) + list(additional_charges)

                if not components:
                    return Response(
                        {"error": "Invoice has no payment schedules or additional charges."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Calculate total outstanding
                total_outstanding = Decimal('0.00')
                for component in components:
                    amount_paid = (
                        PaymentDistribution.objects.filter(
                            collection__invoice=invoice,
                            collection__status='completed',
                            payment_schedule=component if isinstance(component, PaymentSchedule) else None,
                            additional_charge=component if isinstance(component, AdditionalCharge) else None
                        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    )
                    remaining_balance = (component.total or Decimal('0.00')) - amount_paid
                    total_outstanding += remaining_balance

                # Handle overpayment
                overpayment_amount = Decimal('0.00')
                if collection_amount > total_outstanding:
                    overpayment_amount = collection_amount - total_outstanding
                    collection_amount = total_outstanding

                # ✅ Sequential allocation (not equal split)
                if collection_amount > 0:
                    for component in components:
                        # Already paid for this component
                        amount_paid = (
                            PaymentDistribution.objects.filter(
                                collection__invoice=invoice,
                                collection__status='completed',
                                payment_schedule=component if isinstance(component, PaymentSchedule) else None,
                                additional_charge=component if isinstance(component, AdditionalCharge) else None
                            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                        )

                        remaining_balance = (component.total or Decimal('0.00')) - amount_paid
                        if remaining_balance <= 0:
                            component.status = 'paid'
                            component.save()
                            continue

                        # Allocate payment sequentially
                        distributed_amount = min(collection_amount, remaining_balance)

                        if distributed_amount > 0:
                            PaymentDistribution.objects.create(
                                collection=collection,
                                payment_schedule=component if isinstance(component, PaymentSchedule) else None,
                                additional_charge=component if isinstance(component, AdditionalCharge) else None,
                                amount=distributed_amount
                            )
                            collection_amount -= distributed_amount

                        # Update component status
                        if amount_paid + distributed_amount >= (component.total or Decimal('0.00')):
                            component.status = 'paid'
                        elif amount_paid + distributed_amount > 0:
                            component.status = 'partially_paid'
                        else:
                            component.status = 'pending'
                        component.save()

                        # Stop if no money left
                        if collection_amount <= 0:
                            break

                # Save overpayment if exists
                if overpayment_amount > 0:
                    Overpayment.objects.create(
                        tenancy=invoice.tenancy,
                        invoice=invoice,
                        collection=collection,
                        amount=overpayment_amount,
                        status='available'
                    )

                # Update invoice status
                total_collected = (
                    Collection.objects.filter(invoice=invoice, status='completed')
                    .aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
                )
                if total_collected >= invoice.total_amount:
                    invoice.status = 'paid'
                elif total_collected > 0:
                    invoice.status = 'partially_paid'
                else:
                    invoice.status = 'unpaid'
                invoice.save()

                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": f"An error occurred while processing the collection: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CollectionUpdateAPIView(APIView):
    """
    API to update an existing collection for an invoice.

    Endpoint: PUT /api/collections/<int:pk>/
    Purpose: Updates a payment collection, redistributes it across payment schedules
             and additional charges, handles overpayments, and updates invoice status.
    Request Body:
        {
            "invoice": <invoice_id> (int, required),
            "amount": <amount> (decimal, required),
            "collection_mode": <payment_method> (string, required),
            "collection_date": <date> (string, YYYY-MM-DD, required),
            "reference_number": <string> (optional),
            "account_holder_name": <string> (optional),
            "account_number": <string> (optional),
            "cheque_number": <string> (optional),
            "cheque_date": <date> (string, YYYY-MM-DD, optional)
        }
    Response:
        - 200 OK: Serialized updated collection data.
        - 400 Bad Request: Invalid input data or invoice not found.
        - 404 Not Found: Collection not found.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X PUT http://localhost:8000/api/collections/1/
        -H "Content-Type: application/json" 
        -d '{"invoice": 1, "amount": 250.00, "collection_mode": "bank_transfer", "collection_date": "2025-07-02", "reference_number": "TX123", "account_holder_name": "John Doe", "account_number": "1234567890"}'
    Example Response:
        {
            "id": 1,
            "invoice": 1,
            "amount": "250.00",
            "collection_mode": "bank_transfer",
            "collection_date": "02 Jul 2025",
            ...
        }
    """

    def put(self, request, pk, *args, **kwargs):

        try:
            with transaction.atomic():
                # Retrieve the collection
                try:
                    collection = Collection.objects.get(pk=pk)
                except Collection.DoesNotExist:
                    return Response(
                        {"error": "Collection not found."},
                        status=status.HTTP_404_NOT_FOUND
                    )

                # Serialize and validate the updated data
                serializer = CollectionSerializer(collection, data=request.data, partial=True)
                if not serializer.is_valid():
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                # Save the updated collection
                collection = serializer.save()

                # Delete existing payment distributions to redistribute
                PaymentDistribution.objects.filter(collection=collection).delete()
                Overpayment.objects.filter(collection=collection).delete()

                invoice = collection.invoice
                collection_amount = collection.amount

                # Get all payment schedules and additional charges for the invoice
                payment_schedules = invoice.payment_schedules.all()
                additional_charges = invoice.additional_charges.all()
                components = list(payment_schedules) + list(additional_charges)
                total_components = len(components)

                if total_components == 0:
                    return Response(
                        {"error": "Invoice has no payment schedules or additional charges."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Calculate total outstanding amount for the invoice
                total_outstanding = sum(
                    (component.total - (
                        component.invoices.filter(collections__status='completed')
                        .exclude(collections__id=collection.id)
                        .aggregate(total=Sum('collections__amount'))['total'] or Decimal('0.00')
                    )) for component in components
                )

                overpayment_amount = Decimal('0.00')
                if collection_amount > total_outstanding:
                    overpayment_amount = collection_amount - total_outstanding
                    collection_amount = total_outstanding

                # Distribute the collection amount equally across components
                if collection_amount > 0:
                    amount_per_component = collection_amount / total_components

                    for component in components:
                        # Calculate remaining balance for this component
                        amount_paid = (
                            component.invoices.filter(collections__status='completed')
                            .exclude(collections__id=collection.id)
                            .aggregate(total=Sum('collections__amount'))['total'] or Decimal('0.00')
                        )
                        remaining_balance = component.total - amount_paid

                        # Cap the distribution amount to the remaining balance
                        distributed_amount = min(amount_per_component, remaining_balance)

                        # Create PaymentDistribution record
                        PaymentDistribution.objects.create(
                            collection=collection,
                            payment_schedule=component if isinstance(component, PaymentSchedule) else None,
                            additional_charge=component if isinstance(component, AdditionalCharge) else None,
                            amount=distributed_amount
                        )

                        # Update component status
                        total_paid_for_component = amount_paid + distributed_amount
                        if total_paid_for_component >= component.total:
                            component.status = 'paid'
                        elif total_paid_for_component > 0:
                            component.status = 'partially_paid'
                        else:
                            component.status = 'pending'
                        component.save()

                # Create Overpayment record if applicable
                if overpayment_amount > 0:
                    Overpayment.objects.create(
                        tenancy=invoice.tenancy,
                        invoice=invoice,
                        collection=collection,
                        amount=overpayment_amount,
                        status='available'
                    )

                # Update invoice status
                total_collected = (
                    Collection.objects.filter(invoice=invoice, status='completed')
                    .aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
                )
                if total_collected >= invoice.total_amount:
                    invoice.status = 'paid'
                elif total_collected > 0:
                    invoice.status = 'partially_paid'
                else:
                    invoice.status = 'unpaid'
                invoice.save()

                return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"An error occurred while updating the collection: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CollectionDetailAPIView(APIView):
    """
    API to retrieve details of a specific collection, including full invoice details.

    Endpoint: GET /api/collections/<int:pk>/
    Purpose: Fetches detailed information about a collection, including invoice details,
             payment schedules, additional charges, and tax details.
    Response:
        - 200 OK: Detailed collection data with invoice, payment schedules, additional charges, and tax details.
        - 404 Not Found: Collection not found.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X GET http://localhost:8000/api/collections/1/
    Example Response:
        {
            "id": 1,
            "invoice": {
                "id": 1,
                "invoice_number": "INV-001",
                "tenancy_name": "John Doe",
                "end_date": "2025-12-31",
                "total_amount": "1000.00",
                "total_tax_amount": "100.00",
                "total_amount_to_collect": "0.00",
                "taxes": [
                    {
                        "tax_type": "GST",
                        "tax_percentage": "18",
                        "tax_amount": "90.00"
                    }
                ]
            },
            "amount": "300.00",
            "collection_mode": "bank_transfer",
            "collection_date": "2025-07-02",
            "reference_number": "TX123",
            "account_holder_name": "John Doe",
            "account_number": "1234567890",
            "cheque_number": null,
            "cheque_date": null,
            "status": "completed",
            "payment_schedules": [
                {
                    "id": 1,
                    "charge_type": "rent",
                    "reason": "Monthly Rent",
                    "due_date": "2025-07-01",
                    "amount": "100.00",
                    "tax": "10.00",
                    "total": "110.00",
                    "amount_paid": "110.00",
                    "balance": "0.00"
                },
                {
                    "id": 2,
                    "charge_type": "rent",
                    "reason": "Monthly Rent",
                    "due_date": "2025-08-01",
                    "amount": "100.00",
                    "tax": "10.00",
                    "total": "110.00",
                    "amount_paid": "110.00",
                    "balance": "0.00"
                }
            ],
            "additional_charges": [
                {
                    "id": 1,
                    "charge_type": "utility",
                    "reason": "Electricity Bill",
                    "due_date": "2025-07-01",
                    "amount": "100.00",
                    "tax": "10.00",
                    "total": "110.00",
                    "amount_paid": "110.00",
                    "balance": "0.00"
                }
            ]
        }
    """
    def get(self, request, pk):
        try:
            # Fetch collection with related invoice data
            collection = Collection.objects.select_related(
                'invoice', 'invoice__tenancy', 'invoice__tenancy__tenant'
            ).get(pk=pk)
            
            # Fetch the invoice
            invoice = collection.invoice
            if not invoice:
                return Response(
                    {"error": "No invoice associated with this collection."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Fetch related payment schedules and additional charges
            payment_schedules = PaymentSchedule.objects.filter(invoices=invoice)
            additional_charges = AdditionalCharge.objects.filter(invoices=invoice)

            # Calculate total collected and amount to collect
            total_collected = sum(collection.amount for collection in invoice.collections.filter(status='completed'))
            total_amount_to_collect = invoice.total_amount - total_collected

            # Calculate tax details
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
                            'tax_amount': f"{tax_amount:.2f}"
                        })
            for ac in additional_charges:
                if ac.charge_type and ac.charge_type.taxes.exists():
                    for tax in ac.charge_type.taxes.all():
                        tax_amount = ac.amount * (tax.tax_percentage / 100)
                        total_tax_amount += tax_amount
                        tax_details.append({
                            'tax_type': tax.tax_type,
                            'tax_percentage': str(tax.tax_percentage),
                            'tax_amount': f"{tax_amount:.2f}"
                        })

            # Remove duplicate taxes
            unique_tax_details = {
                f"{tax['tax_type']}:{tax['tax_percentage']}": tax for tax in tax_details
            }
            tax_details = list(unique_tax_details.values())

            # Serialize collection data
            collection_data = CollectionSerializer(collection).data
            
            # Add invoice details with tax information
            collection_data['invoice'] = {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'tenancy_name': invoice.tenancy.tenant.tenant_name if invoice.tenancy and invoice.tenancy.tenant else '',
                'end_date': invoice.end_date.strftime('%Y-%m-%d') if invoice.end_date else '',
                'total_amount': f"{invoice.total_amount or 0:.2f}",
                'total_tax_amount': f"{total_tax_amount:.2f}",
                'total_amount_to_collect': f"{total_amount_to_collect:.2f}",
                'taxes': tax_details
            }
            
            # Add payment schedules with balance and amount paid from PaymentDistribution
            collection_data['payment_schedules'] = [
                {
                    'id': ps.id,
                    'charge_type': ps.charge_type.name if ps.charge_type else '',
                    'reason': ps.reason or '',
                    'due_date': ps.due_date.strftime('%Y-%m-%d') if ps.due_date else '',
                    'amount': f"{ps.amount or 0:.2f}",
                    'tax': f"{ps.tax or 0:.2f}",
                    'total': f"{ps.total or 0:.2f}",
                    'amount_paid': f"{(
                        PaymentDistribution.objects.filter(
                            payment_schedule=ps,
                            collection__status='completed'
                        ).aggregate(total=Sum('amount'))['total'] or 0
                    ):.2f}",
                    'balance': f"{(ps.total or 0) - (
                        PaymentDistribution.objects.filter(
                            payment_schedule=ps,
                            collection__status='completed'
                        ).aggregate(total=Sum('amount'))['total'] or 0
                    ):.2f}"
                } for ps in payment_schedules
            ]
            
            # Add additional charges with balance and amount paid from PaymentDistribution
            collection_data['additional_charges'] = [
                {
                    'id': ac.id,
                    'charge_type': ac.charge_type.name if ac.charge_type else '',
                    'reason': ac.reason or '',
                    'due_date': ac.due_date.strftime('%Y-%m-%d') if ac.due_date else '',
                    'amount': f"{ac.amount or 0:.2f}",
                    'tax': f"{ac.tax or 0:.2f}",
                    'total': f"{ac.total or 0:.2f}",
                    'amount_paid': f"{(
                        PaymentDistribution.objects.filter(
                            additional_charge=ac,
                            collection__status='completed'
                        ).aggregate(total=Sum('amount'))['total'] or 0
                    ):.2f}",
                    'balance': f"{(ac.total or 0) - (
                        PaymentDistribution.objects.filter(
                            additional_charge=ac,
                            collection__status='completed'
                        ).aggregate(total=Sum('amount'))['total'] or 0
                    ):.2f}"
                } for ac in additional_charges
            ]

            return Response(collection_data, status=status.HTTP_200_OK)

        except Collection.DoesNotExist:
            return Response(
                {"error": "Collection not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CollectionListAPIView(APIView):
    """
    API to list collections for a specific company with optional search and filters.
    """

    def get(self, request, company_id):
        try:
            search = request.query_params.get('search', '')
            payment_method = request.query_params.get('payment_method', '')
            status_param = request.query_params.get('status', '')
            upcoming_payments = request.query_params.get('upcoming_payments', '').lower() == 'true'
            id_filter = request.query_params.get('id', '')
            tenancy_id = request.query_params.get('tenancy_id', '')
            tenant_name = request.query_params.get('tenant_name', '')
            start_date = request.query_params.get('start_date', '')
            end_date = request.query_params.get('end_date', '')

            # 🔹 Base queryset filtered by company
            collections = Collection.objects.select_related(
                'invoice', 'invoice__tenancy', 'invoice__tenancy__tenant'
            ).filter(company_id=company_id)

            # 🔹 Apply filters
            if search:
                collections = collections.filter(
                    Q(id__icontains=search) |
                    Q(invoice__tenancy__id__icontains=search) |
                    Q(invoice__tenancy__tenant__tenant_name__icontains=search) |
                    Q(amount__icontains=search) |
                    Q(collection_mode__icontains=search) |
                    Q(status__icontains=search)
                )

            if payment_method:
                collections = collections.filter(collection_mode=payment_method)
            if status_param:
                collections = collections.filter(status=status_param)
            if upcoming_payments:
                collections = collections.filter(
                    invoice__status__in=['unpaid', 'partially_paid']
                )
            if id_filter:
                collections = collections.filter(id=id_filter)
            if tenancy_id:
                collections = collections.filter(invoice__tenancy__id=tenancy_id)
            if tenant_name:
                collections = collections.filter(
                    invoice__tenancy__tenant__tenant_name__icontains=tenant_name
                )
            if start_date:
                collections = collections.filter(collection_date__gte=start_date)
            if end_date:
                collections = collections.filter(collection_date__lte=end_date)

            collections = collections.order_by('-collection_date')

            return paginate_queryset(collections, request, CollectionSerializer)

        except Exception as e:
            return Response(
                {'error': f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class ExcessDepositsAPIView(APIView):
    """
    API to retrieve excess deposits and refundable amounts for a tenancy.

    Endpoint: GET /api/excess-deposits/<tenancy_id>/
    Purpose: Calculates total deposits, excess payments, and refundable amounts for a tenancy,
             including details of payment schedules and additional charges.
    Response:
        - 200 OK:
            {
                "tenancy_id": <tenancy_id>,
                "deposit_amount": <total_deposit>,
                "excess_amount": <total_excess>,
                "total_refundable": <total_refundable>,
                "already_refunded": <already_refunded>,
                "refund_items": [...]
            }
        - 404 Not Found: Tenancy not found.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X GET http://localhost:8000/api/excess-deposits/1/
    Example Response:
        {
            "tenancy_id": 1,
            "deposit_amount": 5000.0,
            "excess_amount": 200.0,
            "total_refundable": 5200.0,
            "already_refunded": 0.0,
            "refund_items": [
                {
                    "type": "PaymentSchedule",
                    "id": 1,
                    ...
                },
                ...
            ]
        }
    """

    def get(self, request, tenancy_id):
        try:
            tenancy = get_object_or_404(Tenancy, id=tenancy_id)
            deposit_charge_codes = ChargeCode.objects.filter(title__iexact="Deposit")
            refund_items = []
            total_deposit = 0.0
            total_excess = 0.0
            already_refunded = 0.0

            # Calculate total excess from Overpayment model
            total_excess = float(
                Overpayment.objects.filter(
                    tenancy=tenancy, status='available'
                ).aggregate(total=Sum('amount'))['total'] or 0.0
            )

            payment_schedules = PaymentSchedule.objects.filter(
                tenancy=tenancy, status__in=['paid', 'partially_paid', 'invoiced']
            ).select_related('charge_type').prefetch_related('invoices')

            for ps in payment_schedules:
                invoices = ps.invoices.all()
                # Use PaymentDistribution to get collected amount
                collections = PaymentDistribution.objects.filter(
                    payment_schedule=ps,
                    collection__status='completed'
                )
                invoice_collections = {}
                for invoice in invoices:
                    total_collected = (
                        collections.filter(collection__invoice=invoice)
                        .aggregate(total=Sum('amount'))['total'] or 0.0
                    )
                    invoice_collections[invoice.invoice_number] = float(total_collected)

                collected = sum(invoice_collections.values())
                invoice_numbers = [invoice.invoice_number for invoice in invoices]
                is_deposit = (
                    ps.charge_type.charge_code in deposit_charge_codes
                    if ps.charge_type and hasattr(ps.charge_type, 'charge_code') and ps.charge_type.charge_code
                    else False
                )

                total_or_amount = float(ps.total or ps.amount)
                deposit_amount = total_or_amount if is_deposit and ps.status in ['paid', 'invoiced'] else 0.0
                # Excess is handled at tenancy level via Overpayment, so set to 0 here
                excess = 0.0
                total_refundable = deposit_amount + excess

                total_deposit += deposit_amount

                if total_refundable > 0:
                    refund_items.append({
                        'type': 'PaymentSchedule',
                        'id': ps.id,
                        'charge_type': str(ps.charge_type),
                        'reason': ps.reason or '',
                        'due_date': ps.due_date.strftime('%Y-%m-%d') if ps.due_date else '',
                        'original_amount': float(ps.amount),
                        'vat': float(ps.vat or 0),
                        'tax': float(ps.tax or 0),
                        'total': total_or_amount,
                        'collected_amount': float(collected),
                        'deposit_amount': deposit_amount,
                        'excess_amount': excess,
                        'total_refundable': total_refundable,
                        'status': ps.status,
                        'invoice_numbers': invoice_numbers or [],
                        'collections_per_invoice': invoice_collections
                    })

            additional_charges = AdditionalCharge.objects.filter(
                tenancy=tenancy, status__in=['paid', 'partially_paid', 'invoiced']
            ).select_related('charge_type').prefetch_related('invoices')

            for ac in additional_charges:
                invoices = ac.invoices.all()
                # Use PaymentDistribution to get collected amount
                collections = PaymentDistribution.objects.filter(
                    additional_charge=ac,
                    collection__status='completed'
                )
                invoice_collections = {}
                for invoice in invoices:
                    total_collected = (
                        collections.filter(collection__invoice=invoice)
                        .aggregate(total=Sum('amount'))['total'] or 0.0
                    )
                    invoice_collections[invoice.invoice_number] = float(total_collected)

                collected = sum(invoice_collections.values())
                invoice_numbers = [invoice.invoice_number for invoice in invoices]
                is_deposit = (
                    ac.charge_type.charge_code in deposit_charge_codes
                    if ac.charge_type and hasattr(ac.charge_type, 'charge_code') and ac.charge_type.charge_code
                    else False
                )

                total_or_amount = float(ac.total or ac.amount)
                deposit_amount = total_or_amount if is_deposit and ac.status in ['paid', 'invoiced'] else 0.0
                # Excess is handled at tenancy level via Overpayment, so set to 0 here
                excess = 0.0
                total_refundable = deposit_amount + excess

                total_deposit += deposit_amount

                if total_refundable > 0:
                    refund_items.append({
                        'type': 'AdditionalCharge',
                        'id': ac.id,
                        'charge_type': str(ac.charge_type),
                        'reason': ac.reason or '',
                        'due_date': ac.due_date.strftime('%Y-%m-%d') if ac.due_date else '',
                        'original_amount': float(ac.amount),
                        'vat': float(ac.vat or 0),
                        'tax': float(ac.tax or 0),
                        'total': total_or_amount,
                        'collected_amount': float(collected),
                        'deposit_amount': deposit_amount,
                        'excess_amount': excess,
                        'total_refundable': total_refundable,
                        'status': ac.status,
                        'invoice_numbers': invoice_numbers or [],
                        'collections_per_invoice': invoice_collections
                    })

            already_refunded = float(
                Refund.objects.filter(tenancy=tenancy).aggregate(total=Sum('amount'))['total'] or 0.0
            )

            return Response({
                'tenancy_id': tenancy_id,
                'deposit_amount': total_deposit,
                'excess_amount': total_excess,
                'total_refundable': total_deposit + total_excess,
                'already_refunded': already_refunded,
                'refund_items': refund_items
            }, status=status.HTTP_200_OK)

        except Tenancy.DoesNotExist:
            return Response({'error': 'Tenancy not found'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            print(f"Error retrieving excess deposits: {str(e)}")
            return Response(
                {'error': f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreateRefundAPIView(APIView):
    """
    API to create a refund for a tenancy.

    Endpoint: POST /api/refunds/
    Purpose: Creates a refund record for a tenancy, validating that the refund amount
             does not exceed the available refundable amount (deposits + excess).
    Request Body:
        {
            "tenancy_id": <tenancy_id> (int, required),
            "amount_refunded": <amount> (decimal, required),
            "payment_method": <method> (string, required),
            "remarks": <remarks> (string, optional),
            "payment_date": <date> (string, YYYY-MM-DD, required)
        }
    Response:
        - 201 Created: {"message": "Refund created successfully"}
        - 400 Bad Request: Missing required fields or refund amount exceeds limit.
        - 404 Not Found: Tenancy or user not found.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X POST http://localhost:8000/api/refunds/ \
        -H "Content-Type: application/json" \
        -d '{"tenancy_id": 1, "amount_refunded": 1000.00, "payment_method": "bank_transfer", "payment_date": "2025-07-01"}'
    Example Response:
        {
            "message": "Refund created successfully"
        }
    """

    def post(self, request):
        try:
            data = request.data
            tenancy_id = data.get('tenancy_id')
            amount_refunded = float(data.get('amount_refunded') or 0)
            payment_method = data.get('payment_method')
            remarks = data.get('remarks')
            payment_date = data.get('payment_date')
            processed_by_id = request.user.id if request.user.is_authenticated else None

            if not (tenancy_id and payment_method and payment_date and amount_refunded > 0):
                return Response(
                    {'error': 'Missing required fields or invalid refund amount'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            tenancy = get_object_or_404(Tenancy, id=tenancy_id)
            processed_by = get_object_or_404(Users, id=processed_by_id) if processed_by_id else None
            deposit_charge_codes = ChargeCode.objects.filter(title__iexact="Deposit")

            total_deposit = 0.0
            total_excess = 0.0

            payment_schedules = PaymentSchedule.objects.filter(
                tenancy=tenancy, status__in=['paid', 'partially_paid', 'invoiced']
            ).select_related('charge_type').prefetch_related('invoices')

            for ps in payment_schedules:
                invoices = ps.invoices.all()
                collections = Collection.objects.filter(invoice__in=invoices)
                collected = float(collections.aggregate(total=Sum('amount'))['total'] or 0.0)
                is_deposit = (
                    ps.charge_type.charge_code in deposit_charge_codes
                    if ps.charge_type and hasattr(ps.charge_type, 'charge_code') and ps.charge_type.charge_code
                    else False
                )
                total_or_amount = float(ps.total or ps.amount)
                deposit_amount = total_or_amount if is_deposit and ps.status in ['paid', 'invoiced'] else 0.0
                excess = (
                    float(collected - total_or_amount)
                    if collected > total_or_amount and ps.status in ['paid', 'partially_paid']
                    else 0.0
                )
                total_deposit += deposit_amount
                total_excess += excess

            additional_charges = AdditionalCharge.objects.filter(
                tenancy=tenancy, status__in=['paid', 'partially_paid', 'invoiced']
            ).select_related('charge_type').prefetch_related('invoices')

            for ac in additional_charges:
                invoices = ac.invoices.all()
                collections = Collection.objects.filter(invoice__in=invoices)
                collected = float(collections.aggregate(total=Sum('amount'))['total'] or 0.0)
                is_deposit = (
                    ac.charge_type.charge_code in deposit_charge_codes
                    if ac.charge_type and hasattr(ac.charge_type, 'charge_code') and ac.charge_type.charge_code
                    else False
                )
                total_or_amount = float(ac.total or ac.amount)
                deposit_amount = total_or_amount if is_deposit and ac.status in ['paid', 'invoiced'] else 0.0
                excess = (
                    float(collected - total_or_amount)
                    if collected > total_or_amount and ac.status in ['paid', 'partially_paid']
                    else 0.0
                )
                total_deposit += deposit_amount
                total_excess += excess

            already_refunded = float(
                Refund.objects.filter(tenancy=tenancy).aggregate(total=Sum('amount'))['total'] or 0.0
            )
            total_refundable = total_deposit + total_excess

            if amount_refunded > (total_refundable - already_refunded):
                return Response(
                    {'error': 'Refund amount exceeds available refundable amount'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            refund_type = (
                'deposit' if total_deposit > 0 else 'excess' if total_excess > 0 else 'other'
            )
            Refund.objects.create(
                tenancy=tenancy,
                refund_type=refund_type,
                amount=amount_refunded,
                refund_method=payment_method,
                reason=remarks,
                processed_date=payment_date,
                processed_by=processed_by if processed_by else None
            )

            return Response(
                {'message': 'Refund created successfully'},
                status=status.HTTP_201_CREATED
            )

        except Tenancy.DoesNotExist:
            return Response({'error': 'Tenancy not found'}, status=status.HTTP_404_NOT_FOUND)
        except Users.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {'error': f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RefundListAPIView(APIView):
    """
    API to list refunds with optional search and filters.

    Endpoint: GET /api/refunds/
    Purpose: Retrieves a paginated list of refunds, supporting search by ID, processed date,
             tenancy code, tenant name, amount, or refund method, and filtering by type.
    Query Parameters:
        - search: Search term for filtering refunds.
        - filter: Filter type (e.g., 'showing').
    Response:
        - 200 OK: Paginated list of serialized refund data.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X GET http://localhost:8000/api/refunds/?search=1000
    Example Response:
        {
            "count": 5,
            "next": null,
            "previous": null,
            "results": [
                {
                    "id": 1,
                    "tenancy": {...},
                    "amount": "1000.00",
                    ...
                },
                ...
            ]
        }
    """

    def get(self, request):
        try:
            search_term = request.query_params.get('search', '').strip()
            filter_type = request.query_params.get('filter', 'showing').lower()

            queryset = Refund.objects.select_related('tenancy').order_by('-processed_date')

            if search_term:
                queryset = queryset.filter(
                    Q(id__icontains=search_term) |
                    Q(processed_date__icontains=search_term) |
                    Q(tenancy__tenancy_code__icontains=search_term) |
                    Q(tenancy__tenant__tenant_name__icontains=search_term) |
                    Q(amount__icontains=search_term) |
                    Q(refund_method__icontains=search_term)
                )

            return paginate_queryset(queryset, request, RefundSerializer)

        except Exception as e:
            return Response(
                {'error': 'Failed to fetch refunds'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UpdateRefundAPIView(APIView):
    """
    API to update an existing refund for a tenancy.

    Endpoint: PUT /api/refunds/<refund_id>/
    Purpose: Updates a refund record for a tenancy, validating that the updated refund amount
             does not exceed the available refundable amount (deposits + excess).
    Request Body:
        {
            "tenancy_id": <tenancy_id> (int, required),
            "amount_refunded": <amount> (decimal, required),
            "payment_method": <method> (string, required),
            "remarks": <remarks> (string, optional),
            "payment_date": <date> (string, YYYY-MM-DD, required),
            "account_holder_name": <name> (string, optional),
            "account_number": <number> (string, optional),
            "cheque_number": <number> (string, optional),
            "cheque_date": <date> (string, YYYY-MM-DD, optional)
        }
    Response:
        - 200 OK: {"message": "Refund updated successfully"}
        - 400 Bad Request: Missing required fields or refund amount exceeds limit.
        - 404 Not Found: Refund or tenancy not found.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X PUT http://localhost:8000/api/refunds/1/ \
        -H "Content-Type: application/json" \
        -d '{"tenancy_id": 1, "amount_refunded": 1000.00, "payment_method": "bank_transfer", "payment_date": "2025-07-01"}'
    Example Response:
        {
            "message": "Refund updated successfully"
        }
    """

    def put(self, request, refund_id):
        try:
            refund = get_object_or_404(Refund, id=refund_id)
            data = request.data
            tenancy_id = data.get('tenancy_id')
            amount_refunded = float(data.get('amount_refunded') or 0)
            payment_method = data.get('payment_method')
            remarks = data.get('remarks')
            payment_date = data.get('payment_date')
            account_holder_name = data.get('account_holder_name')
            account_number = data.get('account_number')
            cheque_number = data.get('cheque_number')
            cheque_date = data.get('cheque_date')
            processed_by_id = request.user.id if request.user.is_authenticated else None

            # Validate required fields
            required_fields = [tenancy_id, payment_method, payment_date, amount_refunded]
            if payment_method in ['bank_transfer', 'cheque']:
                required_fields.extend([account_holder_name, account_number])
            if payment_method == 'cheque':
                required_fields.extend([cheque_number, cheque_date])

            if not all(field for field in required_fields if field is not None):
                return Response(
                    {'error': 'Missing required fields or invalid refund amount'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            tenancy = get_object_or_404(Tenancy, id=tenancy_id)
            processed_by = get_object_or_404(Users, id=processed_by_id) if processed_by_id else None

            # Calculate total refundable amount
            deposit_charge_codes = ChargeCode.objects.filter(title__iexact="Deposit")
            total_deposit = 0.0
            total_excess = 0.0

            payment_schedules = PaymentSchedule.objects.filter(
                tenancy=tenancy, status__in=['paid', 'partially_paid', 'invoiced']
            ).select_related('charge_type').prefetch_related('invoices')

            for ps in payment_schedules:
                invoices = ps.invoices.all()
                collections = Collection.objects.filter(invoice__in=invoices)
                collected = float(collections.aggregate(total=Sum('amount'))['total'] or 0.0)
                is_deposit = (
                    ps.charge_type.charge_code in deposit_charge_codes
                    if ps.charge_type and hasattr(ps.charge_type, 'charge_code') and ps.charge_type.charge_code
                    else False
                )
                total_or_amount = float(ps.total or ps.amount)
                deposit_amount = total_or_amount if is_deposit and ps.status in ['paid', 'invoiced'] else 0.0
                total_deposit += deposit_amount

            additional_charges = AdditionalCharge.objects.filter(
                tenancy=tenancy, status__in=['paid', 'partially_paid', 'invoiced']
            ).select_related('charge_type').prefetch_related('invoices')

            for ac in additional_charges:
                invoices = ac.invoices.all()
                collections = Collection.objects.filter(invoice__in=invoices)
                collected = float(collections.aggregate(total=Sum('amount'))['total'] or 0.0)
                is_deposit = (
                    ac.charge_type.charge_code in deposit_charge_codes
                    if ac.charge_type and hasattr(ac.charge_type, 'charge_code') and ac.charge_type.charge_code
                    else False
                )
                total_or_amount = float(ac.total or ac.amount)
                deposit_amount = total_or_amount if is_deposit and ac.status in ['paid', 'invoiced'] else 0.0
                total_deposit += deposit_amount

            total_excess = float(
                Overpayment.objects.filter(
                    tenancy=tenancy, status='available'
                ).aggregate(total=Sum('amount'))['total'] or 0.0
            )

            already_refunded = float(
                Refund.objects.filter(tenancy=tenancy).exclude(id=refund_id).aggregate(total=Sum('amount'))['total'] or 0.0
            )
            total_refundable = total_deposit + total_excess

            if amount_refunded > (total_refundable - already_refunded):
                return Response(
                    {'error': 'Refund amount exceeds available refundable amount'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update refund
            refund_type = (
                'deposit' if total_deposit > 0 else 'excess' if total_excess > 0 else 'other'
            )
            refund.tenancy = tenancy
            refund.refund_type = refund_type
            refund.amount = amount_refunded
            refund.refund_method = payment_method
            refund.reason = remarks
            refund.processed_date = payment_date
            refund.processed_by = processed_by
            refund.reference_number = data.get('reference_number')
            if payment_method in ['bank_transfer', 'cheque']:
                refund.account_holder_name = account_holder_name
                refund.account_number = account_number
            else:
                refund.account_holder_name = None
                refund.account_number = None
            if payment_method == 'cheque':
                refund.cheque_number = cheque_number
                refund.cheque_date = cheque_date
            else:
                refund.cheque_number = None
                refund.cheque_date = None
            refund.save()

            return Response(
                {'message': 'Refund updated successfully'},
                status=status.HTTP_200_OK
            )

        except Refund.DoesNotExist:
            return Response({'error': 'Refund not found'}, status=status.HTTP_404_NOT_FOUND)
        except Tenancy.DoesNotExist:
            return Response({'error': 'Tenancy not found'}, status=status.HTTP_404_NOT_FOUND)
        except Users.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {'error': f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GetRefundAPIView(APIView):
    """
    API to retrieve details of a specific refund by ID.

    Endpoint: GET /api/refunds/<refund_id>/
    Purpose: Fetches the details of a refund record, including associated tenancy information.
    Response:
        - 200 OK:
            {
                "id": <refund_id>,
                "tenancy_id": <tenancy_id>,
                "refund_type": <type>,
                "amount": <amount>,
                "refund_method": <method>,
                "reference_number": <number>,
                "reason": <reason>,
                "processed_date": <date>,
                "account_holder_name": <name>,
                "account_number": <number>,
                "cheque_number": <number>,
                "cheque_date": <date>
            }
        - 404 Not Found: Refund not found.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X GET http://localhost:8000/api/refunds/1/
    Example Response:
        {
            "id": 1,
            "tenancy_id": 12345,
            "refund_type": "deposit",
            "amount": 500.00,
            "refund_method": "bank_transfer",
            "reference_number": "REF12345",
            "reason": "Refund processed for overpayment",
            "processed_date": "2023-06-15",
            "account_holder_name": "John Doe",
            "account_number": "1234567890",
            "cheque_number": null,
            "cheque_date": null
        }
    """

    def get(self, request, refund_id):
        try:
            refund = get_object_or_404(Refund, id=refund_id)
            response_data = {
                'id': refund.id,
                'tenancy_id': refund.tenancy.id if refund.tenancy else None,
                'refund_type': refund.refund_type,
                'amount': float(refund.amount),
                'refund_method': refund.refund_method,
                'reference_number': refund.reference_number,
                'reason': refund.reason,
                'processed_date': refund.processed_date.strftime('%Y-%m-%d') if refund.processed_date else None,
                # 'account_holder_name': refund.account_holder_name,
                # 'account_number': refund.account_number,
                # 'cheque_number': refund.cheque_number,
                # 'cheque_date': refund.cheque_date.strftime('%Y-%m-%d') if refund.cheque_date else None,
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Refund.DoesNotExist:
            return Response({'error': 'Refund not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error retrieving refund details: {str(e)}")
            return Response(
                {'error': f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
