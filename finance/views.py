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
from .models import Expense, Refund
from .serializers import (
    InvoiceSerializer, CollectionSerializer, ExpenseSerializer,
    ExpenseGetSerializer, RefundSerializer
)
from rentbiz.utils.pagination import paginate_queryset


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
            print(f"Error fetching unpaid invoices: {str(e)}")
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


class CollectionCreateAPIView(APIView):
    """
    API to create a new collection for an invoice.

    Endpoint: POST /api/collections/
    Purpose: Records a payment collection for an invoice and updates the invoice's status
             based on the total collected amount.
    Request Body:
        {
            "invoice": <invoice_id> (int, required),
            "amount": <amount> (decimal, required),
            "collection_mode": <payment_method> (string, required),
            "collection_date": <date> (string, YYYY-MM-DD, required),
            ...
        }
    Response:
        - 201 Created: Serialized collection data.
        - 400 Bad Request: Invalid input data.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X POST http://localhost:8000/api/collections/ \
        -H "Content-Type: application/json" \
        -d '{"invoice": 1, "amount": 1000.00, "collection_mode": "cash", "collection_date": "2025-07-01"}'
    Example Response:
        {
            "id": 1,
            "invoice": 1,
            "amount": "1000.00",
            "collection_mode": "cash",
            ...
        }
    """

    def post(self, request, *args, **kwargs):
        try:
            serializer = CollectionSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            collection = serializer.save()
            invoice = collection.invoice
            total_collected = (
                Collection.objects.filter(invoice=invoice).aggregate(Sum('amount'))['amount__sum'] or 0
            )

            if total_collected >= invoice.total_amount:
                invoice.status = 'paid'
                for item in (invoice.payment_schedules.all(), invoice.additional_charges.all()):
                    for obj in item:
                        obj.status = 'paid'
                        obj.save()
            elif total_collected > 0:
                invoice.status = 'partially_paid'
                for item in (invoice.payment_schedules.all(), invoice.additional_charges.all()):
                    for obj in item:
                        obj.status = 'partially_paid'
                        obj.save()
            else:
                invoice.status = 'unpaid'
                for item in (invoice.payment_schedules.all(), invoice.additional_charges.all()):
                    for obj in item:
                        obj.status = 'pending'
                        obj.save()

            invoice.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": "An error occurred while processing the collection."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CollectionListAPIView(APIView):
    """
    API to list collections with optional search and filters.

    Endpoint: GET /api/collections/
    Purpose: Retrieves a paginated list of collections, supporting search by ID, tenancy, tenant name,
             amount, collection mode, or status, and filters by payment method, status, or upcoming payments.
    Query Parameters:
        - search: Search term for filtering collections.
        - payment_method: Filter by collection mode (e.g., 'cash').
        - status: Filter by collection status.
        - upcoming_payments: Filter collections for invoices with 'unpaid' or 'partially_paid' status (true/false).
        - id: Filter by collection ID.
        - tenancy_id: Filter by tenancy ID.
        - tenant_name: Filter by tenant name.
        - start_date: Filter by collection date start.
        - end_date: Filter by collection date end.
    Response:
        - 200 OK: Paginated list of serialized collection data.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X GET http://localhost:8000/api/collections/?search=1000&payment_method=cash&upcoming_payments=true
    Example Response:
        {
            "count": 10,
            "next": null,
            "previous": null,
            "results": [
                {
                    "id": 1,
                    "invoice": {...},
                    "amount": "1000.00",
                    ...
                },
                ...
            ]
        }
    """

    def get(self, request):
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

            collections = Collection.objects.select_related(
                'invoice', 'invoice__tenancy', 'invoice__tenancy__tenant'
            ).all()

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

            payment_schedules = PaymentSchedule.objects.filter(
                tenancy=tenancy, status__in=['paid', 'partially_paid', 'invoiced']
            ).select_related('charge_type').prefetch_related('invoices')

            for ps in payment_schedules:
                invoices = ps.invoices.all()
                collections = Collection.objects.filter(invoice__in=invoices)
                invoice_collections = {}
                for invoice in invoices:
                    total_collected = (
                        collections.filter(invoice=invoice).aggregate(total=Sum('amount'))['total'] or 0.0
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
                excess = (
                    float(collected - total_or_amount)
                    if collected > total_or_amount and ps.status in ['paid', 'partially_paid']
                    else 0.0
                )
                total_refundable = deposit_amount + excess

                total_deposit += deposit_amount
                total_excess += excess

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
                collections = Collection.objects.filter(invoice__in=invoices)
                invoice_collections = {}
                for invoice in invoices:
                    total_collected = (
                        collections.filter(invoice=invoice).aggregate(total=Sum('amount'))['total'] or 0.0
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
                excess = (
                    float(collected - total_or_amount)
                    if collected > total_or_amount and ac.status in ['paid', 'partially_paid']
                    else 0.0
                )
                total_refundable = deposit_amount + excess

                total_deposit += deposit_amount
                total_excess += excess

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
                processed_by=processed_by
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