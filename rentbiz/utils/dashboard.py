# views/dashboard.py
from rest_framework.views import APIView
from django.db import models
from rest_framework.response import Response
from company.models import Building,Units,Invoice,Tenancy
from finance.models import Collection,Invoice,Expense
from datetime import datetime
from django.utils import timezone
from django.db.models.functions import TruncMonth, TruncYear
from rest_framework import status
from datetime import timedelta
from django.db.models import F, ExpressionWrapper, DurationField, IntegerField,Sum,Func
from rentbiz.utils.pagination import paginate_queryset, CustomPagination
from django.db.models import Q
from django.utils import timezone
from datetime import date
from company.models import Invoice
from company.serializers import InvoiceSerializer



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
    




class RentCollectionView(APIView):
    def get(self, request, company_id):
        # Filter invoices by company
        invoices = Invoice.objects.filter(company=company_id)
        
        # Total invoiced amount
        total_invoiced = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Total collected (completed only)
        collected_rent = Collection.objects.filter(
            invoice__company=company_id,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0

        # Pending = total invoiced - collected confirmed
        pending_rent = max(total_invoiced - collected_rent, 0)

        return Response({
            "total": total_invoiced,
            "collected": collected_rent,
            "pending": pending_rent,
            "filter_options": ["This Month", "Last 3 Months", "This Year"]
        })



class ExtractDays(Func):
    function = 'EXTRACT'
    template = "%(function)s(DAY FROM %(expressions)s)"
    output_field = IntegerField()

class TenancyExpiringView(APIView):
    def get(self, request, company_id):
        today = timezone.now().date()

        # Filter active tenancies
        tenancies = Tenancy.objects.filter(status='active', company_id=company_id)

        # Annotate with days remaining as integer
        tenancies = tenancies.annotate(
            days_remaining=ExtractDays(ExpressionWrapper(
                F('end_date') - today,
                output_field=models.DurationField()
            ))
        )

        # Count tenancies by expiry buckets
        expiring_0_30 = tenancies.filter(days_remaining__gte=0, days_remaining__lte=30).count()
        expiring_31_60 = tenancies.filter(days_remaining__gte=31, days_remaining__lte=60).count()
        expiring_61_90 = tenancies.filter(days_remaining__gte=61, days_remaining__lte=90).count()

        return Response({
            "total_expiring": expiring_0_30 + expiring_31_60 + expiring_61_90,
            "ranges": {
                "0-30_days": expiring_0_30,
                "31-60_days": expiring_31_60,
                "61-90_days": expiring_61_90
            }
        })
    


class FinancialReportView(APIView):
    def get(self, request, company_id):
        """
        Retrieve financial report data for a company, filtered by year if provided.
        - If year is specified, returns monthly breakdown for all 12 months (Jan-Dec) of that year.
        - If year is 'All Years' (not provided), aggregates data across all years.
        """
        year = request.query_params.get('year', None)
        
        # Initialize response data
        response_data = {
            'monthly_breakdown': [],
            'total_money_in': 0.00,
            'total_money_out': 0.00,
            'overall_percentage': 0.00,  # Added overall percentage
            'yearly_summary': {}
        }

        # Validate company_id
        try:
            company_id = int(company_id)
        except ValueError:
            return Response(
                {'error': 'Invalid company_id format'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Base querysets with company filter
        expenses_qs = Expense.objects.filter(company__id=company_id)
        collections_qs = Collection.objects.filter(invoice__company__id=company_id)

        # Apply year filter if provided and validate year
        if year:
            try:
                year = int(year)
                current_year = datetime.now().year  # 2025 based on current date: 11:16 AM IST, June 27, 2025
                if year < 2023 or year > current_year:
                    return Response(
                        {'error': f'Year must be between 2023 and {current_year}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                expenses_qs = expenses_qs.filter(date__year=year)
                collections_qs = collections_qs.filter(collection_date__year=year)
            except ValueError:
                return Response(
                    {'error': 'Invalid year format'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Monthly breakdown with all 12 months (Jan-Dec) if year is specified
        if year:
            # Generate all 12 months for the selected year in order (Jan to Dec)
            all_months = [f"{year}-{str(month).zfill(2)}" for month in range(1, 13)]
            expenses_by_month = expenses_qs.annotate(
                month=TruncMonth('date')
            ).values('month').annotate(
                total_expenses=Sum('total_amount')
            ).order_by('month')
            
            collections_by_month = collections_qs.annotate(
                month=TruncMonth('collection_date')
            ).values('month').annotate(
                total_collections=Sum('amount')
            ).order_by('month')

            # Initialize monthly data with all months in order
            monthly_data = {month: {'month': month, 'expenses': 0.0, 'collections': 0.0} for month in all_months}

            # Update with actual data
            for expense in expenses_by_month:
                month_key = expense['month'].strftime('%Y-%m')
                if month_key in monthly_data:
                    monthly_data[month_key]['expenses'] = float(expense['total_expenses'] or 0)

            for collection in collections_by_month:
                month_key = collection['month'].strftime('%Y-%m')
                if month_key in monthly_data:
                    monthly_data[month_key]['collections'] = float(collection['total_collections'] or 0)

            # Convert to list in Jan-Dec order
            response_data['monthly_breakdown'] = [monthly_data[month] for month in all_months]
            for item in response_data['monthly_breakdown']:
                item['net'] = item['collections'] - item['expenses']
        else:
            # For 'All Years', aggregate all months across years
            expenses_by_month = expenses_qs.annotate(
                month=TruncMonth('date')
            ).values('month').annotate(
                total_expenses=Sum('total_amount')
            ).order_by('month')

            collections_by_month = collections_qs.annotate(
                month=TruncMonth('collection_date')
            ).values('month').annotate(
                total_collections=Sum('amount')
            ).order_by('month')

            monthly_data = {}
            for expense in expenses_by_month:
                month_key = expense['month'].strftime('%Y-%m')
                monthly_data[month_key] = {
                    'month': month_key,
                    'expenses': float(expense['total_expenses'] or 0),
                    'collections': 0.0
                }

            for collection in collections_by_month:
                month_key = collection['month'].strftime('%Y-%m')
                if month_key in monthly_data:
                    monthly_data[month_key]['collections'] = float(collection['total_collections'] or 0)
                else:
                    monthly_data[month_key] = {
                        'month': month_key,
                        'expenses': 0.0,
                        'collections': float(collection['total_collections'] or 0)
                    }

            response_data['monthly_breakdown'] = list(monthly_data.values())
            for item in response_data['monthly_breakdown']:
                item['net'] = item['collections'] - item['expenses']

        # Calculate total money in and out
        response_data['total_money_in'] = float(collections_qs.aggregate(
            total=Sum('amount')
        )['total'] or 0)

        response_data['total_money_out'] = float(expenses_qs.aggregate(
            total=Sum('total_amount')
        )['total'] or 0)

        # Calculate overall percentage (money out as a percentage of money in)
        response_data['overall_percentage'] = ((response_data['total_money_out'] / response_data['total_money_in']) * 100 
                                             if response_data['total_money_in'] else 0.0)

        # Yearly summary
        expenses_by_year = expenses_qs.annotate(
            year=TruncYear('date')
        ).values('year').annotate(
            total_expenses=Sum('total_amount')
        ).order_by('year')

        collections_by_year = collections_qs.annotate(
            year=TruncYear('collection_date')
        ).values('year').annotate(
            total_collections=Sum('amount')
        ).order_by('year')

        yearly_data = {}
        for expense in expenses_by_year:
            year_key = expense['year'].year
            yearly_data[year_key] = {
                'year': year_key,
                'expenses': float(expense['total_expenses'] or 0),
                'collections': 0.0
            }

        for collection in collections_by_year:
            year_key = collection['year'].year
            if year_key in yearly_data:
                yearly_data[year_key]['collections'] = float(collection['total_collections'] or 0)
            else:
                yearly_data[year_key] = {
                    'year': year_key,
                    'expenses': 0.0,
                    'collections': float(collection['total_collections'] or 0)
                }

        response_data['yearly_summary'] = yearly_data

        return Response(response_data, status=status.HTTP_200_OK)
    


