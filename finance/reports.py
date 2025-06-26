from datetime import datetime
import csv
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from .models import Collection

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
