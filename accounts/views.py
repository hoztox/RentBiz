from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Company
from accounts.models import Country, State
from accounts.serializers import StateSerializer, CountrySerializer
from .serializers import CompanySerializer
from django.shortcuts import get_object_or_404
import logging
logger = logging.getLogger(__name__)
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives
from django.conf import settings



class CompanyCreateAPIView(APIView):
    def post(self, request):
        serializer = CompanySerializer(data=request.data)
        if serializer.is_valid():
            company = serializer.save()

            try:
                self.send_welcome_email_with_logo(company)
                logger.info(f"Company created and email sent to: {company.email_address}")
            except Exception as e:
                logger.error(f"Error sending email: {str(e)}")

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def send_welcome_email_with_logo(self, company):
        subject = "Welcome to Rentbiz!"
        recipient_email = company.email_address

 
        context = {
            "company_name": company.company_name,
            "company_admin_name": company.company_admin_name,   
            "user_id": company.user_id,
            "email_address": company.email_address,  
            "phone_no1": company.phone_no1,
            "phone_no2": company.phone_no2,
            "currency": company.currency,
            "currency_code": company.currency_code,
            "date_joined": company.date_joined,            
        }
        
        html_message = render_to_string("company/add_company.html", context)
        plain_message = strip_tags(html_message)

        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            to=[recipient_email],
        )
        email.attach_alternative(html_message, "text/html")

        if company.company_logo:
            logo_file = company.company_logo
            logo_file.open()
            email.attach(logo_file.name, logo_file.read(), logo_file.file.content_type)
            logo_file.close()

        email.send(fail_silently=False)

class CompanyListCreateAPIView(APIView):
    def get(self, request):
        companies = Company.objects.all()
        serializer = CompanySerializer(companies, many=True)
        return Response(serializer.data)

 

class CompanyDetailAPIView(APIView):
    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        serializer = CompanySerializer(company)
        return Response(serializer.data)

    def put(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        serializer = CompanySerializer(company, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        company.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CountryListView(APIView):
    def get(self, request, country_id=None):

            countries = Country.objects.all()
            serializer = CountrySerializer(countries, many=True)
            return Response(serializer.data)


class StateListView(APIView):
    def get(self, request, country_id):
        try:
            states = State.objects.filter(country_id=country_id)
            serializer = StateSerializer(states, many=True)
            return Response(serializer.data)
        except Country.DoesNotExist:
            return Response(
                {"error": "Country not found"},
                status=status.HTTP_404_NOT_FOUND
            )

            
class CompanyDetailView(APIView):
    def get(self, request, company_id):
        try:
            company = Company.objects.get(id=company_id)
            serializer = CompanySerializer(company)
            return Response(serializer.data)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=404)


class CompanyDetailView(APIView):
    def get(self, request, company_id):
        try:
            company = Company.objects.get(id=company_id)
            serializer = CompanySerializer(company)
            return Response(serializer.data)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=404)


class CountryListView(APIView):
    def get(self, request, country_id=None):

            countries = Country.objects.all()
            serializer = CountrySerializer(countries, many=True)
            return Response(serializer.data)


class StateListView(APIView):
    def get(self, request, country_id):
        try:
            states = State.objects.filter(country_id=country_id)
            serializer = StateSerializer(states, many=True)
            return Response(serializer.data)
        except Country.DoesNotExist:
            return Response(
                {"error": "Country not found"},
                status=status.HTTP_404_NOT_FOUND
            )