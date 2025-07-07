from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Q
import csv
from .models import Tenancy


class TenancyExportAPIView(APIView):
    def get(self, request, company_id):

        tenancies = Tenancy.objects.filter(company_id=company_id)

        # Apply filters
        search = request.query_params.get('search', None)
        tenancy_code = request.query_params.get('tenancy_code', None)
        tenant = request.query_params.get('tenant', None)
        building = request.query_params.get('building', None)
        unit = request.query_params.get('unit', None)
        status = request.query_params.get('status', None)
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)

        if search:
            tenancies = tenancies.filter(
                Q(tenancy_code__icontains=search) |
                Q(tenant__tenant_name__icontains=search) |
                Q(building__building_name__icontains=search) |
                Q(unit__unit_name__icontains=search)
            )

        if tenancy_code:
            tenancies = tenancies.filter(tenancy_code=tenancy_code)
        if tenant:
            tenancies = tenancies.filter(tenant__tenant_name=tenant)
        if building:
            tenancies = tenancies.filter(building__building_name=building)
        if unit:
            tenancies = tenancies.filter(unit__unit_name=unit)
        if status:
            tenancies = tenancies.filter(status=status)
        if start_date:
            tenancies = tenancies.filter(start_date__gte=start_date)
        if end_date:
            tenancies = tenancies.filter(end_date__lte=end_date)

        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="tenancies.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Tenancy Code',
            'Tenant Name',
            'Building Name',
            'Unit Name',
            'Rental Months',
            'Status',
            'Start Date',
            'End Date',
            'Rent per Frequency',
            'Total Rent Receivable'
        ])

        for tenancy in tenancies:
            writer.writerow([
                tenancy.tenancy_code or '',
                tenancy.tenant.tenant_name if tenancy.tenant else 'N/A',
                tenancy.building.building_name if tenancy.building else 'N/A',
                tenancy.unit.unit_name if tenancy.unit else 'N/A',
                tenancy.rental_months or '',
                tenancy.status or '',
                tenancy.start_date or '',
                tenancy.end_date or '',
                tenancy.rent_per_frequency or '',
                tenancy.total_rent_receivable or ''
            ])

        return response