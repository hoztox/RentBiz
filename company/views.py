from django.shortcuts import render
from .serializers import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import logging
from django.shortcuts import get_object_or_404
logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
import jwt
 
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone

class CompanyLoginView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'error': 'Username and password must be provided'}, status=status.HTTP_400_BAD_REQUEST)

     
        user = authenticate(request, username=username, password=password)

        if user:
            if hasattr(user, 'is_trash') and user.is_trash:
                return Response({'error': 'User account not found'}, status=status.HTTP_401_UNAUTHORIZED)

            if hasattr(user, 'status') and user.status == 'blocked':
                return Response({'error': 'Your account is blocked. Please contact support.'}, status=status.HTTP_403_FORBIDDEN)

            if hasattr(user, 'company') and user.company and user.company.status == 'blocked':
                return Response({'error': 'Your company is blocked. Please contact support.'}, status=status.HTTP_403_FORBIDDEN)

            refresh = RefreshToken.for_user(user)

            return Response({
                'id': user.id,
                'username': user.username,
                'first_name': getattr(user, 'first_name', ''),
                'last_name': getattr(user, 'last_name', ''),
                'email': getattr(user, 'email', ''),
                'phone': getattr(user, 'phone', ''),
                'status': getattr(user, 'status', ''),
                'created_at': user.date_joined.strftime('%Y-%m-%d %H:%M:%S') if hasattr(user, 'date_joined') else '',
                'company_id': user.company.id if hasattr(user, 'company') and user.company else None,
                'role': 'user',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_200_OK)

   
       
        try:
            company = Company.objects.get(user_id=username)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)

        if company.status == 'blocked':
            return Response({'error': 'Your company is blocked. Please contact support.'}, status=status.HTTP_403_FORBIDDEN)

        from django.contrib.auth.hashers import check_password

        if not check_password(password, company.password):
            return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)

    
        refresh = RefreshToken()
        access_token = refresh.access_token

        # Add custom claims
        access_token['user_id'] = company.user_id
        access_token['role'] = 'company'

        refresh['user_id'] = company.user_id
        refresh['role'] = 'company'

        return Response({
            'id': company.id,
            'user_id': company.user_id,
            'company_name': company.company_name,
            'company_admin_name': company.company_admin_name,
            'username': company.user_id,
            'phone_no1': company.phone_no1,
            'phone_no2': company.phone_no2,
            'email_address': company.email_address,
            'created_at': company.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
            'company_logo': company.company_logo.url if company.company_logo else None,
            'status': company.status,
            'date_joined': company.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
            'role': 'company',
            'access': str(access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_200_OK)




class UserCreateAPIView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            try:
                self.send_welcome_email_to_user(user)
                logger.info(f"User created and email sent to: {user.email}")
            except Exception as e:
                logger.error(f"Error sending user welcome email: {str(e)}")

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def send_welcome_email_to_user(self, user):
        subject = "Welcome to Rentbiz!"
        recipient_email = user.email

        context = {
            "name": user.name,
            "email": user.email,
            "username": user.username,
            "phone": user.phone,
            "company_name": user.company.company_name if user.company else "N/A"
        }

        html_message = render_to_string("users/add_users.html", context)
        plain_message = strip_tags(html_message)

        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            to=[recipient_email],
        )
        email.attach_alternative(html_message, "text/html")

        if user.company_logo:
            logo_file = user.company_logo
            logo_file.open()
            email.attach(logo_file.name, logo_file.read(), logo_file.file.content_type)
            logo_file.close()

        email.send(fail_silently=False)


class UserListByCompanyAPIView(APIView):
    def get(self, request, company_id):
        users = Users.objects.filter(company_id=company_id)
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
 

class UserDetailAPIView(APIView):
    def get(self, request, user_id):
 
        user = get_object_or_404(Users, id=user_id)
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, user_id):
    
        user = get_object_or_404(Users, id=user_id)
   
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, user_id):
       
        user = get_object_or_404(Users, id=user_id)
        user.delete()
        return Response({"message": "User deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class BuildingCreateView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = BuildingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class BuildingDetailView(APIView):
    def get_object(self, pk):
        try:
            return Building.objects.get(pk=pk)
        except Building.DoesNotExist:
            return None

    def get(self, request, pk):
        building = self.get_object(pk)
        if not building:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = BuildingSerializer(building)
        return Response(serializer.data)

    def put(self, request, pk):
        building = self.get_object(pk)
        if not building:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = BuildingSerializer(building, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        building = self.get_object(pk)
        if not building:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        building.delete()
        return Response({'message': 'Building deleted'}, status=status.HTTP_204_NO_CONTENT)
    
class BuildingByCompanyView(APIView):
    def get(self, request, company_id):
        buildings = Building.objects.filter(company__id=company_id)
        serializer = BuildingSerializer(buildings, many=True)
        return Response(serializer.data)



class UnitCreateView(APIView):
    def post(self, request):
        serializer = UnitSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class UnitDetailView(APIView):
    def get(self, request, pk):
        unit = get_object_or_404(Units, pk=pk)
        serializer = UnitGetSerializer(unit)
        return Response(serializer.data)

    def put(self, request, pk):
        unit = get_object_or_404(Units, pk=pk)
        serializer = UnitSerializer(unit, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        unit = get_object_or_404(Units, pk=pk)
        unit.delete()
        return Response({'message': 'Unit deleted'}, status=status.HTTP_204_NO_CONTENT)

class UnitsByCompanyView(APIView):
    def get(self, request, company_id):
        units = Units.objects.filter(company__id=company_id)
        serializer = UnitGetSerializer(units, many=True)
        return Response(serializer.data)
    
    


class UnitTypeListCreateAPIView(APIView):
    def post(self, request):
        serializer = UnitTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)   
    
class UnitTypeByCompanyAPIView(APIView):
    def get(self, request, company_id):
        unit_types = UnitType.objects.filter(company_id=company_id)
        serializer = UnitTypeSerializer(unit_types, many=True)
        return Response(serializer.data)
    
 
class UnitTypeDetailAPIView(APIView):
    def get_object(self, id):
        return get_object_or_404(UnitType, id=id)

    def get(self, request, id):
        unit_type = self.get_object(id)
        serializer = UnitTypeSerializer(unit_type)
        return Response(serializer.data)

    def put(self, request, id):
        unit_type = self.get_object(id)
        serializer = UnitTypeSerializer(unit_type, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        unit_type = self.get_object(id)
        unit_type.delete()
        return Response({"message": "Deleted successfully"}, status=status.HTTP_204_NO_CONTENT)



class MasterDocumentListCreateAPIView(APIView):
    def post(self, request):
        serializer = MasterDocumentTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)   
    
class MasterDocumentByCompanyAPIView(APIView):
    def get(self, request, company_id):
        unit_types = MasterDocumentType.objects.filter(company_id=company_id)
        serializer = MasterDocumentTypeSerializer(unit_types, many=True)
        return Response(serializer.data)
    
 
class MasterDocumentDetailAPIView(APIView):
    def get_object(self, id):
        return get_object_or_404(MasterDocumentType, id=id)

    def get(self, request, id):
        unit_type = self.get_object(id)
        serializer = MasterDocumentTypeSerializer(unit_type)
        return Response(serializer.data)

    def put(self, request, id):
        unit_type = self.get_object(id)
        serializer = MasterDocumentTypeSerializer(unit_type, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        unit_type = self.get_object(id)
        unit_type.delete()
        return Response({"message": "Deleted successfully"}, status=status.HTTP_204_NO_CONTENT)





class IDListCreateAPIView(APIView):
    def post(self, request):
        serializer = IDTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)   
    
class IDByCompanyAPIView(APIView):
    def get(self, request, company_id):
        unit_types = IDType.objects.filter(company_id=company_id)
        serializer = IDTypeSerializer(unit_types, many=True)
        return Response(serializer.data)
    
 
class IDDetailAPIView(APIView):
    def get_object(self, id):
        return get_object_or_404(IDType, id=id)

    def get(self, request, id):
        unit_type = self.get_object(id)
        serializer = IDTypeSerializer(unit_type)
        return Response(serializer.data)

    def put(self, request, id):
        unit_type = self.get_object(id)
        serializer = IDTypeSerializer(unit_type, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        unit_type = self.get_object(id)
        unit_type.delete()
        return Response({"message": "Deleted successfully"}, status=status.HTTP_204_NO_CONTENT)



class CurrencyListCreateView(APIView):

    def post(self, request):
        serializer = CurrencySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrencyDetailView(APIView):
    def get(self, request, pk):
        currency = get_object_or_404(Currency, pk=pk)
        serializer = CurrencySerializer(currency)
        return Response(serializer.data)

    def put(self, request, pk):
        currency = get_object_or_404(Currency, pk=pk)
        serializer = CurrencySerializer(currency, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        currency = get_object_or_404(Currency, pk=pk)
        currency.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    
class CurrencyByCompanyAPIView(APIView):
    def get(self, request, company_id):
        unit_types = Currency.objects.filter(company_id=company_id)
        serializer = CurrencySerializer(unit_types, many=True)
        return Response(serializer.data)


class TenantCreateView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = TenantSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class TenantDetailView(APIView):
    def get_object(self, pk):
        try:
            return Tenant.objects.get(pk=pk)
        except Tenant.DoesNotExist:
            return None

    def get(self, request, pk):
        building = self.get_object(pk)
        if not building:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = TenantGetSerializer(building)
        return Response(serializer.data)

    def put(self, request, pk):
        building = self.get_object(pk)
        if not building:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = TenantSerializer(building, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        building = self.get_object(pk)
        if not building:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        building.delete()
        return Response({'message': 'Building deleted'}, status=status.HTTP_204_NO_CONTENT)
    
class TenantByCompanyView(APIView):
    def get(self, request, company_id):
        buildings = Tenant.objects.filter(company__id=company_id)
        serializer = TenantGetSerializer(buildings, many=True)
        return Response(serializer.data)
    


class ChargecodeListCreateAPIView(APIView):
    def post(self, request):
        serializer = ChargeCodeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)   
    
class ChargecodeByCompanyAPIView(APIView):
    def get(self, request, company_id):
        unit_types = ChargeCode.objects.filter(company_id=company_id)
        serializer = ChargeCodeSerializer(unit_types, many=True)
        return Response(serializer.data)
    
 
class ChargecodeDetailAPIView(APIView):
    def get_object(self, id):
        return get_object_or_404(ChargeCode, id=id)

    def get(self, request, id):
        unit_type = self.get_object(id)
        serializer = ChargeCodeSerializer(unit_type)
        return Response(serializer.data)

    def put(self, request, id):
        unit_type = self.get_object(id)
        serializer = ChargeCodeSerializer(unit_type, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        unit_type = self.get_object(id)
        unit_type.delete()
        return Response({"message": "Deleted successfully"}, status=status.HTTP_204_NO_CONTENT)



class ChargesListCreateAPIView(APIView):
    def post(self, request):
        serializer = ChargesSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)   
    
class ChargesByCompanyAPIView(APIView):
    def get(self, request, company_id):
        unit_types = ChargeCode.objects.filter(company_id=company_id)
        serializer = ChargesGetSerializer(unit_types, many=True)
        return Response(serializer.data)
    
 
class ChargesDetailAPIView(APIView):
    def get_object(self, id):
        return get_object_or_404(ChargeCode, id=id)

    def get(self, request, id):
        unit_type = self.get_object(id)
        serializer = ChargesGetSerializer(unit_type)
        return Response(serializer.data)

    def put(self, request, id):
        unit_type = self.get_object(id)
        serializer = ChargesSerializer(unit_type, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        unit_type = self.get_object(id)
        unit_type.delete()
        return Response({"message": "Deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
