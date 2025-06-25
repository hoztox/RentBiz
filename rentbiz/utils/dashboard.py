# views/dashboard.py
from rest_framework.views import APIView
from rest_framework.response import Response
from company.models import Building,Units



class PropertiesSummaryView(APIView):
    def get(self, request, company_id):
        company = company_id

        total_properties = Building.objects.filter(company=company).count()
        total_units = Units.objects.filter(building__company=company).count()
        total_acquired = Units.objects.filter(building__company=company, unit_status='occupied').count()
        total_vacant = Units.objects.filter(building__company=company, unit_status='vacant').count()

        return Response({
            "total_properties": total_properties,
            "total_units": total_units,
            "total_acquired": total_acquired,
            "total_vacant": total_vacant,
        })