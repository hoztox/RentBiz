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
import re

from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password
from .models import Company, Users

class CompanyLoginView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'error': 'Username and password must be provided'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Try to log in as User
        try:
            user = Users.objects.get(username=username)
            if user.status == 'blocked':
                return Response({'error': 'Your account is blocked. Please contact support.'}, status=status.HTTP_403_FORBIDDEN)
            if not user.check_password(password):
                raise Users.DoesNotExist()

            refresh = RefreshToken()
            access_token = refresh.access_token
            access_token['user_id'] = user.id
            access_token['role'] = 'user'

            refresh['user_id'] = user.id
            refresh['role'] = 'user'

            return Response({
                'id': user.id,
                'username': user.username,
                'name': user.name,
                'email': user.email,
                 
                'status': user.status,
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'company_id': user.company.id if user.company else None,
                'role': user.user_role,
                'access': str(access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_200_OK)

        except Users.DoesNotExist:
            pass  

      
        try:
            company = Company.objects.get(user_id=username)
            if company.status == 'blocked':
                return Response({'error': 'Your company is blocked. Please contact support.'}, status=status.HTTP_403_FORBIDDEN)
            if not company.check_password(password):
                raise Company.DoesNotExist()

            refresh = RefreshToken()
            access_token = refresh.access_token
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
                'role': 'company',
                'access': str(access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_200_OK)

        except Company.DoesNotExist:
            return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)





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

from collections import defaultdict
class BuildingCreateView(APIView):
    def post(self, request, *args, **kwargs):
        print("Request data:", request.data)
        
  
        def get_value_or_none(key, convert_type=None):
            value = request.data.get(key, '')
            if value == '' or value is None:
                return None
            if convert_type:
                try:
                    return convert_type(value)
                except (ValueError, TypeError):
                    return None
            return value
        
     
        building_data = {
            'company': request.data.get('company'),
            'building_name': request.data.get('building_name'),
            'building_no': request.data.get('building_no'),
            'plot_no': request.data.get('plot_no'),
            'description': get_value_or_none('description'),
            'remarks': get_value_or_none('remarks'),
            'latitude': get_value_or_none('latitude', float), 
            'longitude': get_value_or_none('longitude', float),  
            'status': request.data.get('status'),
            'land_mark': get_value_or_none('land_mark'),
            'building_address': request.data.get('building_address'),
        }
        
  
        documents_data = []
        document_groups = defaultdict(dict)
        
       
        for key, value in request.data.items():
            if key.startswith('build_comp['):
               
                import re
                match = re.match(r'build_comp\[(\d+)\]\[(\w+)\]', key)
                if match:
                    index = int(match.group(1))
                    field_name = match.group(2)
                    document_groups[index][field_name] = value
        
      
        for index in sorted(document_groups.keys()):
            doc_data = document_groups[index]
       
            if 'upload_file' in doc_data:
         
                documents_data.append(doc_data)
        
   
        final_data = building_data.copy()
        final_data['build_comp'] = documents_data
        
        print("Processed data:", final_data)
        
        
        serializer = BuildingSerializer(data=final_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        print("Serializer errors:", serializer.errors)
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
        
        print("Request data:", request.data)
        
        # Helper function to handle empty values
        def get_value_or_none(key, convert_type=None):
            value = request.data.get(key, '')
            if value == '' or value is None:
                return None
            if convert_type:
                try:
                    return convert_type(value)
                except (ValueError, TypeError):
                    return None
            return value
        
        # Process building data
        building_data = {
            'company': request.data.get('company'),
            'building_name': request.data.get('building_name'),
            'building_no': request.data.get('building_no'),
            'plot_no': request.data.get('plot_no'),
            'description': get_value_or_none('description'),
            'remarks': get_value_or_none('remarks'),
            'latitude': get_value_or_none('latitude', float),
            'longitude': get_value_or_none('longitude', float),
            'status': request.data.get('status'),
            'land_mark': get_value_or_none('land_mark'),
            'building_address': request.data.get('building_address'),
        }
        
        # Process document data - handle both JSON array and form-data formats
        documents_data = []
        documents_provided = False  # Flag to check if documents were explicitly provided
        
        # Check if build_comp is explicitly provided in the request
        if 'build_comp' in request.data:
            documents_provided = True
            
            # Check if build_comp is already a list (JSON format)
            if isinstance(request.data['build_comp'], list):
                documents_data = request.data['build_comp']
            else:
                # Handle form-data format
                document_groups = defaultdict(dict)
                
                for key, value in request.data.items():
                    if key.startswith('build_comp['):
                        match = re.match(r'build_comp\[(\d+)\]\[(\w+)\]', key)
                        if match:
                            index = int(match.group(1))
                            field_name = match.group(2)
                            document_groups[index][field_name] = value
                
                for index in sorted(document_groups.keys()):
                    doc_data = document_groups[index]
                    # Add document if it has any meaningful data (not just upload_file)
                    if any(key in doc_data for key in ['doc_type', 'number', 'issued_date', 'expiry_date', 'upload_file']):
                        # Convert id to integer if present
                        if 'id' in doc_data and doc_data['id']:
                            try:
                                doc_data['id'] = int(doc_data['id'])
                            except (ValueError, TypeError):
                                doc_data.pop('id')  # Remove invalid ID
                        documents_data.append(doc_data)
        
        # Check if any build_comp fields are present in form data
        elif any(key.startswith('build_comp[') for key in request.data.keys()):
            documents_provided = True
            # Handle form-data format when build_comp key itself is not present
            document_groups = defaultdict(dict)
            
            for key, value in request.data.items():
                if key.startswith('build_comp['):
                    match = re.match(r'build_comp\[(\d+)\]\[(\w+)\]', key)
                    if match:
                        index = int(match.group(1))
                        field_name = match.group(2)
                        document_groups[index][field_name] = value
            
            for index in sorted(document_groups.keys()):
                doc_data = document_groups[index]
                # Add document if it has any meaningful data (not just upload_file)
                if any(key in doc_data for key in ['doc_type', 'number', 'issued_date', 'expiry_date', 'upload_file']):
                    # Convert id to integer if present
                    if 'id' in doc_data and doc_data['id']:
                        try:
                            doc_data['id'] = int(doc_data['id'])
                        except (ValueError, TypeError):
                            doc_data.pop('id')  # Remove invalid ID
                    documents_data.append(doc_data)
        
        # Prepare final data
        final_data = building_data.copy()
        
        # Only include build_comp in the data if it was explicitly provided
        if documents_provided:
            final_data['build_comp'] = documents_data
            print("Documents data included:", documents_data)
        else:
            print("No document data provided - preserving existing documents")
        
        print("Processed data:", final_data)
        
        # Use partial=True to allow partial updates
        serializer = BuildingSerializer(building, data=final_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        print("Serializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        building = self.get_object(pk)
        if not building:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        building.delete()
        return Response({'message': 'Building deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
    
class BuildingByCompanyView(APIView):
    def get(self, request, company_id):
        buildings = Building.objects.filter(company__id=company_id)
        serializer = BuildingSerializer(buildings, many=True)
        return Response(serializer.data)



import json

class UnitCreateView(APIView):
    def post(self, request):
        print("Raw request data:", request.data)
        
        # Extract basic unit data
        unit_data = {}
        for key, value in request.data.items():
            if key not in ['unit_comp_json'] and not key.startswith('document_file_'):
                unit_data[key] = value
        
       
        unit_comp_json = request.data.get('unit_comp_json')
        if unit_comp_json:
            try:
                unit_comp_data = json.loads(unit_comp_json)
                
          
                for doc_data in unit_comp_data:
                    file_index = doc_data.pop('file_index', None)
                    if file_index is not None:
                        file_key = f'document_file_{file_index}'
                        if file_key in request.FILES:
                            doc_data['upload_file'] = request.FILES[file_key]
                
                unit_data['unit_comp'] = unit_comp_data
                
            except json.JSONDecodeError:
                return Response(
                    {'error': 'Invalid JSON in unit_comp_json'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        print("Processed unit data:", unit_data)
        
        serializer = UnitSerializer(data=unit_data)
        if serializer.is_valid():
            serializer.save()
            print("Successfully created unit:", serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
 

 
 

class UnitDetailView(APIView):
    def get(self, request, pk):
        unit = get_object_or_404(Units, pk=pk)
        serializer = UnitGetSerializer(unit)
        return Response(serializer.data)

    def delete(self, request, pk):
        unit = get_object_or_404(Units, pk=pk)
        unit.delete()
        return Response({'message': 'Unit deleted'}, status=status.HTTP_204_NO_CONTENT)

class UnitsByCompanyView(APIView):
    def get(self, request, company_id):
        units = Units.objects.filter(company__id=company_id)
        serializer = UnitGetSerializer(units, many=True)
        return Response(serializer.data)
    
    
 
class UnitEditView(APIView):
    def put(self, request, pk):
        """
        Update an existing unit with JSON import functionality
        """
        print("Raw request data:", request.data)
        
        # Get the unit instance to update
        try:
            unit = Units.objects.get(pk=pk)
        except Units.DoesNotExist:
            return Response(
                {'error': 'Unit not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Extract basic unit data
        unit_data = {}
        for key, value in request.data.items():
            if key not in ['unit_comp_json'] and not key.startswith('document_file_'):
                unit_data[key] = value
        
        # Process unit_comp_json if provided
        unit_comp_json = request.data.get('unit_comp_json')
        if unit_comp_json:
            try:
                unit_comp_data = json.loads(unit_comp_json)
                
                # Process file uploads for documents
                for doc_data in unit_comp_data:
                    file_index = doc_data.pop('file_index', None)
                    if file_index is not None:
                        file_key = f'document_file_{file_index}'
                        if file_key in request.FILES:
                            doc_data['upload_file'] = request.FILES[file_key]
                
                unit_data['unit_comp'] = unit_comp_data
                
            except json.JSONDecodeError:
                return Response(
                    {'error': 'Invalid JSON in unit_comp_json'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        print("Processed unit data:", unit_data)
        
        # Use serializer to update the unit
        serializer = UnitSerializer(unit, data=unit_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            print("Successfully updated unit:", serializer.data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        """
        Partially update an existing unit with JSON import functionality
        """
        print("Raw request data:", request.data)
        
        # Get the unit instance to update
        try:
            unit = Units.objects.get(pk=pk)
        except Units.DoesNotExist:
            return Response(
                {'error': 'Unit not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Extract basic unit data
        unit_data = {}
        for key, value in request.data.items():
            if key not in ['unit_comp_json'] and not key.startswith('document_file_'):
                unit_data[key] = value
        
        # Process unit_comp_json if provided
        unit_comp_json = request.data.get('unit_comp_json')
        if unit_comp_json:
            try:
                unit_comp_data = json.loads(unit_comp_json)
                
                # Process file uploads for documents
                for doc_data in unit_comp_data:
                    file_index = doc_data.pop('file_index', None)
                    if file_index is not None:
                        file_key = f'document_file_{file_index}'
                        if file_key in request.FILES:
                            doc_data['upload_file'] = request.FILES[file_key]
                
                unit_data['unit_comp'] = unit_comp_data
                
            except json.JSONDecodeError:
                return Response(
                    {'error': 'Invalid JSON in unit_comp_json'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        print("Processed unit data:", unit_data)
        
        # Use serializer to partially update the unit
        serializer = UnitSerializer(unit, data=unit_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            print("Successfully updated unit:", serializer.data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, pk):
        """
        Retrieve a specific unit for editing
        """
        try:
            unit = Units.objects.get(pk=pk)
            serializer = UnitSerializer(unit)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Units.DoesNotExist:
            return Response(
                {'error': 'Unit not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

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
    def post(self, request):
        print("Raw request data:", request.data)

        tenant_data = {}
        for key, value in request.data.items():
            if key not in ['document_comp_json'] and not key.startswith('document_file_'):
                tenant_data[key] = value

        document_comp_json = request.data.get('document_comp_json')

        if document_comp_json:
            try:
                document_data = json.loads(document_comp_json)

                for doc in document_data:
                    file_index = doc.pop('file_index', None)
                    if file_index is not None:
                        file_key = f'document_file_{file_index}'
                        if file_key in request.FILES:
                            doc['upload_file'] = request.FILES[file_key]

                tenant_data['tenant_comp'] = document_data

            except json.JSONDecodeError:
                return Response({'error': 'Invalid JSON in document_comp_json'}, status=status.HTTP_400_BAD_REQUEST)

        print("Processed tenant data:", tenant_data)

        serializer = TenantSerializer(data=tenant_data)
        if serializer.is_valid():
            tenant = serializer.save()
            print("Successfully created tenant:", serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            print("Serializer errors:", serializer.errors)
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
        unit_types = Charges.objects.filter(company_id=company_id)
        serializer = ChargesGetSerializer(unit_types, many=True)
        return Response(serializer.data)
    
 
class ChargesDetailAPIView(APIView):
    def get_object(self, id):
        return get_object_or_404(Charges, id=id)

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



class TenancyCreateView(APIView):
    """Create a new tenancy with automatic payment schedule generation"""
    
    def post(self, request):
        serializer = TenancyCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            # Create tenancy with payment schedules
            tenancy = serializer.save()
            
            # Return detailed response with payment schedules
            detail_serializer = TenancyDetailSerializer(tenancy)
            
            return Response({
                'success': True,
                'message': 'Tenancy created successfully with payment schedules',
                'tenancy': detail_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class TenancyDetailView(APIView):
    """Get tenancy details with payment schedules"""
    
    def get(self, request, pk):
        try:
            tenancy = Tenancy.objects.select_related('tenant', 'building', 'unit').get(pk=pk)
            serializer = TenancyDetailSerializer(tenancy)
            
            return Response({
                'success': True,
                'tenancy': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Tenancy.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Tenancy not found'
            }, status=status.HTTP_404_NOT_FOUND)
            

    def put(self, request, pk, format=None):
        tenancy = get_object_or_404(Tenancy, pk=pk)
        serializer = TenancyCreateSerializer(tenancy, data=request.data, partial=False)  
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        try:
            tenancy = Tenancy.objects.get(pk=pk)
            tenancy.delete()
            return Response({
                'success': True,
                'message': 'Tenancy deleted successfully'
            }, status=status.HTTP_204_NO_CONTENT)
        except Tenancy.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Tenancy not found'
            }, status=status.HTTP_404_NOT_FOUND)
      
class TenancyByCompanyAPIView(APIView):

    def get(self, request, company_id):
 
        tenancies = Tenancy.objects.filter(company_id=company_id)
        serializer = TenancyListSerializer(tenancies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
    
class PendingTenanciesByCompanyAPIView(APIView):
    def get(self, request, company_id):
        pending_tenancies = Tenancy.objects.filter(company_id=company_id, status='pending')
        serializer = TenancyListSerializer(pending_tenancies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ActiveTenanciesByCompanyAPIView(APIView):
    def get(self, request, company_id):
        pending_tenancies = Tenancy.objects.filter(company_id=company_id, status='active')
        serializer = TenancyListSerializer(pending_tenancies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TerminatiionTenanciesByCompanyAPIView(APIView):
    def get(self, request, company_id):
        pending_tenancies = Tenancy.objects.filter(company_id=company_id,is_termination=True )
        serializer = TenancyListSerializer(pending_tenancies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)    
    

class CloseTenanciesByCompanyAPIView(APIView):
    def get(self, request, company_id):
        pending_tenancies = Tenancy.objects.filter(company_id=company_id,is_close=True )
        serializer = TenancyListSerializer(pending_tenancies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)    


 
class VacantUnitsByBuildingView(APIView):
    def get(self, request, building_id):
        try:
            building = Building.objects.get(id=building_id)
        except Building.DoesNotExist:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        
        vacant_units = Units.objects.filter(building=building, unit_status='vacant')
        serializer = UnitSerializer(vacant_units, many=True)
        return Response(serializer.data)


class BuildingsWithVacantUnitsView(APIView):
    def get(self, request):
        buildings = Building.objects.filter(unit_building__unit_status='vacant').distinct()
        serializer = BuildingSerializer(buildings, many=True)
        return Response(serializer.data)