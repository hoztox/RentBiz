import csv
from decimal import Decimal
from datetime import datetime
from accounts.models import Company
from django.http import HttpResponse
from rest_framework import status
from django.db.models import Q,Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Collection, Expense, Refund
from django.db.models.functions import Coalesce
from company.models import Building, Units, Tenant, Tenancy


class CollectionCSVDownloadAPIView(APIView):
    """
    API to download collections as a CSV file with optional filters.

    Endpoint: GET /api/collections/download/
    Purpose: Generates a CSV file of collections based on provided filters, excluding pagination.
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
        - 200 OK: CSV file containing filtered collection data.
        - 500 Internal Server Error: Unexpected server error.
    Example Request:
        curl -X GET http://localhost:8000/api/collections/download/?payment_method=cash&upcoming_payments=true
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

            # Create CSV response
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="collections_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

            writer = csv.writer(response)
            writer.writerow([
                'ID', 'Date', 'Tenancy ID', 'Tenant Name', 'Amount',
                 'Payment Method', 'Status', 'Invoice Status'
            ])

            for collection in collections:
                writer.writerow([
                    collection.id,
                    collection.collection_date.strftime('%d %b %Y'),
                    collection.invoice.tenancy_id,
                    collection.invoice.tenancy.tenant.tenant_name,
                    f"{collection.amount:.2f}",
                    collection.collection_mode.replace('_', ' ').upper(),
                    collection.status.upper(),
                    collection.invoice.status.upper()
                ])

            return response

        except Exception as e:
            print(f"Error generating CSV: {str(e)}")
            return Response(
                {'error': f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FinancialSummaryView(APIView):
    """
    API to retrieve financial summaries for a company, aggregated by building, tenant, tenancy, or unit.

    Endpoint: GET /api/financial-summary/<company_id>/
    Purpose: Generates a financial summary for a specified company, aggregated by the chosen view type
             (building, tenant, tenancy, or unit) with optional date range filters.
    Query Parameters:
        - view_type: Aggregation type ('building', 'tenant', 'tenancy', 'unit'). Default: 'building'.
        - start_date: Filter by collection/expense/refund date start (e.g., '2023-01-01').
        - end_date: Filter by collection/expense/refund date end (e.g., '2023-12-31').
    Response:
        - 200 OK: JSON object containing company details and aggregated financial data.
        - 400 Bad Request: If company_id is missing or view_type is invalid.
        - 404 Not Found: If the company does not exist.
    Example Request:
        curl -X GET http://localhost:8000/api/financial-summary/1/?view_type=building&start_date=2023-01-01&end_date=2023-12-31
    """
    
    def get(self, request, company_id):
        # Extract query parameters from the request
        view_type = request.query_params.get('view_type', 'building')  # Default to 'building' if not specified
        start_date = request.query_params.get('start_date')  # Optional start date filter
        end_date = request.query_params.get('end_date')  # Optional end date filter

        # Validate that company_id is provided
        if not company_id:
            return Response(
                {"error": "company_id is a required parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch the company or return 404 if not found
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response(
                {"error": "Company with the provided ID does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Initialize the response data list
        response_data = []

        # Define base filters for querying collections, expenses, and refunds
        collections_filter = {'invoice__tenancy__building__company': company}
        expenses_filter = {'company': company}
        refunds_filter = {'tenancy__building__company': company}

        # Apply date range filters if provided
        if start_date:
            collections_filter['date__gte'] = start_date
            expenses_filter['date__gte'] = start_date
            refunds_filter['date__gte'] = start_date
        if end_date:
            collections_filter['date__lte'] = end_date
            expenses_filter['date__lte'] = end_date
            refunds_filter['date__lte'] = end_date

        if view_type == 'building':
            # Aggregate financial data by building
            buildings = Building.objects.filter(company=company)
            for building in buildings:
                # Calculate total income from collections for the building
                collections = Collection.objects.filter(
                    invoice__tenancy__building=building, **collections_filter
                ).aggregate(total_income=Coalesce(Sum('amount'), Decimal('0.00')))['total_income']

                # Calculate total expenses for the building
                expenses = Expense.objects.filter(
                    building=building, **expenses_filter
                ).aggregate(total_expense=Coalesce(Sum('total_amount'), Decimal('0.00')))['total_expense']

                # Calculate total general expenses for the building
                general_expenses = Expense.objects.filter(
                    building=building, expense_type='general', **expenses_filter
                ).aggregate(total_general_expense=Coalesce(Sum('total_amount'), Decimal('0.00')))['total_general_expense']

                # Calculate total refunds for the building
                refunds = Refund.objects.filter(
                    tenancy__building=building, **refunds_filter
                ).aggregate(total_refunded=Coalesce(Sum('amount'), Decimal('0.00')))['total_refunded']

                # Append building data to response
                response_data.append({
                    'building_id': building.id,
                    'building_name': building.building_name,
                    'total_income': float(collections),
                    'total_expense': float(expenses),
                    'total_general_expense': float(general_expenses),
                    'total_refunded': float(refunds),
                    'net_income': float(collections - expenses - refunds)
                })

        elif view_type == 'tenant':
            # Aggregate financial data by tenant
            tenants = Tenant.objects.filter(company=company)
            for tenant in tenants:
                # Calculate total income from collections for the tenant
                collections = Collection.objects.filter(
                    invoice__tenancy__tenant=tenant, **collections_filter
                ).aggregate(total_income=Coalesce(Sum('amount'), Decimal('0.00')))['total_income']

                # Calculate total expenses for the tenant
                expenses = Expense.objects.filter(
                    tenant=tenant, **expenses_filter
                ).aggregate(total_expense=Coalesce(Sum('total_amount'), Decimal('0.00')))['total_expense']

                # Calculate total general expenses for the tenant
                general_expenses = Expense.objects.filter(
                    tenant=tenant, expense_type='general', **expenses_filter
                ).aggregate(total_general_expense=Coalesce(Sum('total_amount'), Decimal('0.00')))['total_general_expense']

                # Calculate total refunds for the tenant
                refunds = Refund.objects.filter(
                    tenancy__tenant=tenant, **refunds_filter
                ).aggregate(total_refunded=Coalesce(Sum('amount'), Decimal('0.00')))['total_refunded']

                # Append tenant data to response
                response_data.append({
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.tenant_name,
                    'total_income': float(collections),
                    'total_expense': float(expenses),
                    'total_general_expense': float(general_expenses),
                    'total_refunded': float(refunds),
                    'net_income': float(collections - expenses - refunds)
                })

        elif view_type == 'tenancy':
            # Aggregate financial data by tenancy
            tenancies = Tenancy.objects.filter(company=company)
            for tenancy in tenancies:
                # Calculate total income from collections for the tenancy
                collections = Collection.objects.filter(
                    invoice__tenancy=tenancy, **collections_filter
                ).aggregate(total_income=Coalesce(Sum('amount'), Decimal('0.00')))['total_income']

                # Calculate total expenses for the tenancy
                expenses = Expense.objects.filter(
                    tenancy=tenancy, **expenses_filter
                ).aggregate(total_expense=Coalesce(Sum('total_amount'), Decimal('0.00')))['total_expense']

                # Calculate total general expenses for the tenancy
                general_expenses = Expense.objects.filter(
                    tenancy=tenancy, expense_type='general', **expenses_filter
                ).aggregate(total_general_expense=Coalesce(Sum('total_amount'), Decimal('0.00')))['total_general_expense']

                # Calculate total refunds for the tenancy
                refunds = Refund.objects.filter(
                    tenancy=tenancy, **refunds_filter
                ).aggregate(total_refunded=Coalesce(Sum('amount'), Decimal('0.00')))['total_refunded']

                # Append tenancy data to response
                response_data.append({
                    'tenancy_id': tenancy.id,
                    'tenancy_code': tenancy.tenancy_code,
                    'tenant_name': tenancy.tenant.tenant_name if tenancy.tenant else None,
                    'unit_name': tenancy.unit.unit_name if tenancy.unit else None,
                    'total_income': float(collections),
                    'total_expense': float(expenses),
                    'total_general_expense': float(general_expenses),
                    'total_refunded': float(refunds),
                    'net_income': float(collections - expenses - refunds)
                })

        elif view_type == 'unit':
            # Aggregate financial data by unit
            units = Units.objects.filter(company=company)
            for unit in units:
                # Calculate total income from collections for the unit
                collections = Collection.objects.filter(
                    invoice__tenancy__unit=unit, **collections_filter
                ).aggregate(total_income=Coalesce(Sum('amount'), Decimal('0.00')))['total_income']

                # Calculate total expenses for the unit
                expenses = Expense.objects.filter(
                    unit=unit, **expenses_filter
                ).aggregate(total_expense=Coalesce(Sum('total_amount'), Decimal('0.00')))['total_expense']

                # Calculate total general expenses for the unit
                general_expenses = Expense.objects.filter(
                    unit=unit, expense_type='general', **expenses_filter
                ).aggregate(total_general_expense=Coalesce(Sum('total_amount'), Decimal('0.00')))['total_general_expense']

                # Calculate total refunds for the unit
                refunds = Refund.objects.filter(
                    tenancy__unit=unit, **refunds_filter
                ).aggregate(total_refunded=Coalesce(Sum('amount'), Decimal('0.00')))['total_refunded']

                # Append unit data to response
                response_data.append({
                    'unit_id': unit.id,
                    'unit_name': unit.unit_name,
                    'building_name': unit.building.building_name if unit.building else None,
                    'total_income': float(collections),
                    'total_expense': float(expenses),
                    'total_general_expense': float(general_expenses),
                    'total_refunded': float(refunds),
                    'net_income': float(collections - expenses - refunds)
                })

        else:
            # Return error for invalid view_type
            return Response(
                {"error": "Invalid view_type. Must be one of: 'building', 'tenant', 'tenancy', 'unit'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Construct and return the final response
        return Response({
            'company_id': company.id,
            'company_name': company.company_name,
            'view_type': view_type,
            'data': response_data
        }, status=status.HTTP_200_OK)