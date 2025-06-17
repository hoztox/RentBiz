# ------------------------------------------------------------------
# Django imports  
# ------------------------------------------------------------------
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string, get_template
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.db.models import Q
from django.utils import timezone

# ------------------------------------------------------------------
# REST Framework imports  
# ------------------------------------------------------------------
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics
from rest_framework_simplejwt.tokens import RefreshToken

# ------------------------------------------------------------------
# Python Standard Library imports  
# ------------------------------------------------------------------
from datetime import datetime, timedelta, date
import logging
import csv
import io
import json
import uuid
from urllib.parse import quote
from collections import defaultdict
import re

# ------------------------------------------------------------------
# Third-Party imports  
# ------------------------------------------------------------------
from datetime import date
from django.template.loader import get_template
from django.core.exceptions import ObjectDoesNotExist
from xhtml2pdf import pisa
from io import BytesIO


# ------------------------------------------------------------------
# Local Application imports  
# ------------------------------------------------------------------
from .serializers import *
from .models import *
from rentbiz.utils.pagination import paginate_queryset, CustomPagination

# ------------------------------------------------------------------
# Logger Configuration  
# ------------------------------------------------------------------
logger = logging.getLogger(__name__)

 
class CompanyLoginView(APIView):
    def post(self, request, *args, **kwargs):
        print("=== LOGIN REQUEST DEBUG ===")
        print("Request data:", request.data)
        
        username = request.data.get('username')
        password = request.data.get('password')
        
        print(f"Username received: '{username}'")
        print(f"Password received: '{password}'")
        
        if not username or not password:
            print("Missing username or password")
            return Response({'error': 'Username and password must be provided'}, status=status.HTTP_400_BAD_REQUEST)
        
 
        print("\n--- Checking for USER ---")
        try:
            user = Users.objects.get(username=username)
            print(f"Found user: {user.name} (ID: {user.id})")
            print(f"User status: {user.status}")
            
            if user.status == 'blocked':
                print("User is blocked")
                return Response({'error': 'Your account is blocked. Please contact support.'}, status=status.HTTP_403_FORBIDDEN)
            
            print(f"Checking user password...")
            password_check = user.check_password(password)
            print(f"User password check result: {password_check}")
            
            if not password_check:
                print("User password check failed, continuing to company check")
                raise Users.DoesNotExist()
            
            print("User login successful, generating tokens...")
            refresh = RefreshToken()
            access_token = refresh.access_token
            access_token['user_id'] = user.id
            access_token['role'] = 'user'
            
            refresh['user_id'] = user.id
            refresh['role'] = 'user'
            
            response_data = {
                'id': user.id,
                'username': user.username,
                'name': user.name,
                'email': user.email,
                'status': user.status,
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'company_id': user.company.id if user.company else None,
                'role': 'user',
                'user_role': user.user_role,
                'access': str(access_token),
                'refresh': str(refresh),
            }
            print("User login response:", response_data)
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Users.DoesNotExist:
            print("User not found or password incorrect")
        
        # Try to find company
        print("\n--- Checking for COMPANY ---")
        try:
            print(f"Looking for company with user_id: '{username}'")
            company = Company.objects.get(user_id=username)
            print(f"Found company: {company.company_name} (ID: {company.id})")
            print(f"Company user_id: {company.user_id}")
            print(f"Company status: {company.status}")
            print(f"Company password hash: {company.password[:50]}..." if company.password else "No password set")
            
            if company.status == 'blocked':
                print("Company is blocked")
                return Response({'error': 'Your company is blocked. Please contact support.'}, status=status.HTTP_403_FORBIDDEN)
            
            print(f"Checking company password...")
            password_check = company.check_password(password)
            print(f"Company password check result: {password_check}")
            
            # If password check fails, try to detect if it's a plain text password
            if not password_check:
                print("Password check failed, checking if password is stored as plain text...")
                
                # Check if the stored password matches the input password directly (plain text)
                if company.password == password:
                    print("Password was stored as plain text! Fixing it now...")
                    # Hash the password properly
                    company.set_password(password)
                    print("Password has been hashed and saved properly")
                    
                    # Now the password check should work
                    password_check = company.check_password(password)
                    print(f"Password check after fixing: {password_check}")
                else:
                    print("Password doesn't match plain text either")
                
                if not password_check:
                    print("Company password check failed even after plain text fix")
                    raise Company.DoesNotExist()
            
            print("Company login successful, generating tokens...")
            refresh = RefreshToken()
            access_token = refresh.access_token
            access_token['user_id'] = company.user_id
            access_token['role'] = 'company'
            
            refresh['user_id'] = company.user_id
            refresh['role'] = 'company'
            
            response_data = {
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
            }
            print("Company login response:", response_data)
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Company.DoesNotExist:
            print("Company not found or password incorrect")
            print("=== LOGIN FAILED ===")
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
        search_query = request.query_params.get('search', '').strip()
        status_filter = request.query_params.get('status', '').strip().lower()
        users = Users.objects.filter(company_id=company_id)
        

        if search_query:
            users = users.filter(
                Q( name__icontains= search_query) |
                Q( username__icontains = search_query)   |
                Q( user_role__icontains = search_query)|
                Q( created_at__icontains = search_query)
               

            )

        if status_filter in ['active','blocked']:
            users = users.filter(status=status_filter)
        users = users.order_by('id')


        return paginate_queryset(users, request, UserSerializer)
    
    
    
 

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

        # Include country and state in building_data
        building_data = {
            'company': get_value_or_none('company'),
            'building_name': get_value_or_none('building_name'),
            'building_no': get_value_or_none('building_no'),
            'plot_no': get_value_or_none('plot_no'),
            'description': get_value_or_none('description'),
            'remarks': get_value_or_none('remarks'),
            'latitude': get_value_or_none('latitude', float),
            'longitude': get_value_or_none('longitude', float),
            'status': get_value_or_none('status'),
            'land_mark': get_value_or_none('land_mark'),
            'building_address': get_value_or_none('building_address'),
            'country': get_value_or_none('country', int),  # Convert to int for ForeignKey
            'state': get_value_or_none('state', int),      # Convert to int for ForeignKey
            'user': get_value_or_none('user'),            # Include user if sent
        }

        # Process documents
        documents_data = []
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
            if 'upload_file' in doc_data:
                documents_data.append(doc_data)

        # Combine building and documents data
        final_data = building_data.copy()
        final_data['build_comp'] = documents_data

        print("Processed data:", final_data)

        # Serialize and save
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
        unit_count = building.unit_building.count()  

        data = serializer.data
        data['unit_count'] = unit_count   

        return Response(data)

    def put(self, request, pk):
        building = self.get_object(pk)
        if not building:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        
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
            'status': get_value_or_none('status') or building.status,

            'land_mark': get_value_or_none('land_mark'),
            'building_address': get_value_or_none('building_address'),
        }
        
     
        documents_data = []
        documents_provided = False   
        
        
        if 'build_comp' in request.data:
            documents_provided = True
            
   
            if isinstance(request.data['build_comp'], list):
                documents_data = request.data['build_comp']
            else:
 
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
                  
                    if any(key in doc_data for key in ['doc_type', 'number', 'issued_date', 'expiry_date', 'upload_file']):
              
                        if 'id' in doc_data and doc_data['id']:
                            try:
                                doc_data['id'] = int(doc_data['id'])
                            except (ValueError, TypeError):
                                doc_data.pop('id')  
                        documents_data.append(doc_data)
        
  
        elif any(key.startswith('build_comp[') for key in request.data.keys()):
            documents_provided = True
        
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
               
                if any(key in doc_data for key in ['doc_type', 'number', 'issued_date', 'expiry_date', 'upload_file']):
          
                    if 'id' in doc_data and doc_data['id']:
                        try:
                            doc_data['id'] = int(doc_data['id'])
                        except (ValueError, TypeError):
                            doc_data.pop('id')   
                    documents_data.append(doc_data)
        
       
        final_data = building_data.copy()
        
      
        if documents_provided:
            final_data['build_comp'] = documents_data
            print("Documents data included:", documents_data)
        else:
            print("No document data provided - preserving existing documents")
        
        print("Processed data:", final_data)
        
   
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

# class BuildingDetailView(APIView):
#     def get_object(self, pk):
#         try:
#             return Building.objects.get(pk=pk)
#         except Building.DoesNotExist:
#             return None

#     def get(self, request, pk):
#         building = self.get_object(pk)
#         if not building:
#             return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
#         serializer = BuildingSerializer(building)
#         return Response(serializer.data)

#     def put(self, request, pk):
#         building = self.get_object(pk)
#         if not building:
#             return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
#         # Helper function to handle empty values
#         def get_value_or_none(key, convert_type=None):
#             value = request.data.get(key, '')
#             if value == '' or value is None:
#                 return None
#             if convert_type:
#                 try:
#                     return convert_type(value)
#                 except (ValueError, TypeError):
#                     return None
#             return value
#         # Process building data
#         building_data = {
#             'company': request.data.get('company'),
#             'building_name': request.data.get('building_name'),
#             'building_no': request.data.get('building_no'),
#             'plot_no': request.data.get('plot_no'),
#             'description': get_value_or_none('description'),
#             'remarks': get_value_or_none('remarks'),
#             'latitude': get_value_or_none('latitude', float),
#             'longitude': get_value_or_none('longitude', float),
#             'status': request.data.get('status'),
#             'land_mark': get_value_or_none('land_mark'),
#             'building_address': request.data.get('building_address'),
#             'country': request.data.get('country',int),
#             'state': request.data.get('state',int),
#         }
#         # Process document data
#         documents_data = []
#         document_files = []
#         # Handle both form-data and JSON formats
#         if 'build_comp' in request.data:
#             # JSON format
#             if isinstance(request.data['build_comp'], list):
#                 documents_data = request.data['build_comp']
#             else:
#                 # Form-data format
#                 document_groups = defaultdict(dict)
#                 for key, value in request.data.items():
#                     if key.startswith('build_comp['):
#                         match = re.match(r'build_comp\[(\d+)\]\[(\w+)\]', key)
#                         if match:
#                             index = int(match.group(1))
#                             field_name = match.group(2)
#                             document_groups[index][field_name] = value
#                 for index in sorted(document_groups.keys()):
#                     documents_data.append(document_groups[index])
#         # Handle file uploads separately
#         for file_key, file_obj in request.FILES.items():
#             if file_key.startswith('build_comp['):
#                 match = re.match(r'build_comp\[(\d+)\]\[upload_file\]', file_key)
#                 if match:
#                     index = int(match.group(1))
#                     if index < len(documents_data):
#                         documents_data[index]['upload_file'] = file_obj
#         try:
#             with transaction.atomic():
#                 # Update building data
#                 building_serializer = BuildingSerializer(building, data=building_data, partial=True)
#                 if not building_serializer.is_valid():
#                     return Response(building_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#                 updated_building = building_serializer.save()
#                 # Handle documents
#                 if documents_data:
#                     # First delete existing documents if we're replacing them
#                     DocumentType.objects.filter(building=updated_building).delete()
#                     # Create new documents
#                     for doc_data in documents_data:
#                         doc_serializer = DocumentTypeSerializer(data={
#                             'building': updated_building.id,
#                             'doc_type': doc_data.get('doc_type'),
#                             'number': doc_data.get('number'),
#                             'issued_date': doc_data.get('issued_date'),
#                             'expiry_date': doc_data.get('expiry_date'),
#                             'upload_file': doc_data.get('upload_file'),
#                         })
#                         if not doc_serializer.is_valid():
#                             return Response(doc_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#                         doc_serializer.save()
#                 return Response(building_serializer.data)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

#     def delete(self, request, pk):
#         building = self.get_object(pk)
#         if not building:
#             return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
#         building.delete()
#         return Response({'message': 'Building deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


class BuildingByCompanyView(APIView):
    def get(self, request, company_id):
        status_filter = request.query_params.get('status', '').strip().lower()
        search_query = request.query_params.get('search', '').strip()
        buildings = Building.objects.filter(company__id=company_id)
        if search_query:
            buildings = buildings.filter(
                Q(building_name__icontains = search_query) |
                Q(created_at__icontains = search_query)   |
                Q(building_address__icontains = search_query)|
                Q(code__icontains = search_query)

            )
        if status_filter in ['active','inactive']:
            buildings = buildings.filter(status=status_filter)
        buildings = buildings.order_by('id') 
            
        return paginate_queryset(buildings, request, BuildingSerializer)
        
 
 

class UnitCreateView(APIView):
    def post(self, request):
        print("Raw request data:", request.data)
        
        # Extract base unit data (excluding nested unit_comp fields)
        unit_data = {}
        for key, value in request.data.items():
            if not key.startswith('unit_comp['):
                unit_data[key] = value
        
        # Parse unit_comp (nested document data)
        unit_comp_data = self.parse_unit_comp_data(request.data, request.FILES)
        
        # Always assign unit_comp (even if it's an empty list)
        unit_data['unit_comp'] = unit_comp_data
        print("Processed unit data:", unit_data)
        
        serializer = UnitSerializer(data=unit_data)
        if serializer.is_valid():
            serializer.save()
            print("Successfully created unit:", serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def parse_unit_comp_data(self, data, files):
        documents = defaultdict(dict)
        
        print("Starting to parse unit_comp data...")
        print("Available keys:", list(data.keys()))
        print("Available file keys:", list(files.keys()))
        
        # Handle regular form fields (non-file fields)
        for key, value in data.items():
            print(f"Processing key: {key}, value: {value}, type: {type(value)}")
            if key.startswith("unit_comp["):
                try:
                    # Remove unit_comp[ and split by ][
                    key_without_prefix = key[10:]  # Remove 'unit_comp['
                    parts = key_without_prefix.split('][')
                    
                    if len(parts) == 2:
                        index_part = parts[0]  # Should be '0', '1', etc.
                        field_part = parts[1].rstrip(']')  # Remove trailing ']'
                        
                        index = int(index_part)
                        field = field_part
                        
                        # Skip file fields in request.data (handled in request.FILES)
                        if field == 'upload_file':
                            continue
                        
                        # Handle QueryDict values (lists or single values)
                        actual_value = value[0] if isinstance(value, list) and value else value
                        
                        documents[index][field] = actual_value
                        print(f"✅ Parsed field: {key} -> index={index}, field={field}, value={actual_value}")
                    else:
                        print(f"❌ Invalid key format: {key}, parts: {parts}")
                        
                except (ValueError, IndexError, AttributeError) as e:
                    print(f"❌ Error parsing key {key}: {e}")
        
        # Handle file uploads
        for file_key, file_value in files.items():
            print(f"Processing file key: {file_key}, value type: {type(file_value)}")
            if file_key.startswith("unit_comp["):
                try:
                    # Remove unit_comp[ and split by ][
                    key_without_prefix = file_key[10:]  # Remove 'unit_comp['
                    parts = key_without_prefix.split('][')
                    
                    if len(parts) == 2:
                        index_part = parts[0]  # Should be '0', '1', etc.
                        field_part = parts[1].rstrip(']')  # Remove trailing ']'
                        
                        index = int(index_part)
                        field = field_part
                        
                        if field == 'upload_file':
                            documents[index][field] = file_value
                            print(f"✅ Parsed file: {file_key} -> index={index}, field={field}")
                        else:
                            print(f"❌ Unexpected file field: {field}")
                    else:
                        print(f"❌ Invalid file key format: {file_key}, parts: {parts}")
                        
                except (ValueError, IndexError) as e:
                    print(f"❌ Error parsing file key {file_key}: {e}")
        
        print("Raw documents dict:", dict(documents))
        result = list(documents.values())
        print("Final unit_comp list:", result)
        print("Number of documents parsed:", len(result))
        
        return result
 
 

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
        search_query = request.query_params.get('search', '').strip()
        status_filter = request.query_params.get('status', '').strip().lower()
        if search_query:
            units = units.filter(
                Q(code__icontains = search_query) |
                Q(created_at__icontains = search_query)|
                Q(unit_name__icontains = search_query)|
                Q(address__icontains = search_query) |
                Q(building__building_name__icontains=search_query) |
                Q(unit_type__title__icontains = search_query)  

            )
        if status_filter in ['occupied','renovation','vacant', 'disputed' ]:
            units = units.filter(unit_status__iexact=status_filter)
        units = units.order_by('id')

        return paginate_queryset(units,request,UnitGetSerializer)
    
 

class UnitEditAPIView(APIView):
    def get_object(self, id):
        return get_object_or_404(Units, id=id)

    def get(self, request, id):
        unit = self.get_object(id)
        serializer = UnitSerializer(unit)
        return Response(serializer.data)

    def put(self, request, id):
        print("Incoming PUT data:", request.data)
        unit = self.get_object(id)

        # Extract unit data (excluding document-related fields)
        unit_data = {}
        excluded_keys = ['id', 'doc_type', 'number', 'issued_date', 'expiry_date', 'unit_comp_json']
        for key, value in request.data.items():
            if key not in excluded_keys and not key.startswith('document_file_'):
                unit_data[key] = value

        # Parse unit_comp_json if present
        unit_comp_data = []
        if 'unit_comp_json' in request.data:
            try:
                unit_comp_json = request.data['unit_comp_json']
                # Handle case where unit_comp_json is a list (QueryDict may wrap it)
                if isinstance(unit_comp_json, list):
                    unit_comp_json = unit_comp_json[0]
                unit_comp_data = json.loads(unit_comp_json)
                print("Parsed unit_comp_json:", unit_comp_data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error parsing unit_comp_json: {e}")
                return Response({"error": "Invalid unit_comp_json format"}, status=status.HTTP_400_BAD_REQUEST)

        # Handle file uploads
        for index, doc_data in enumerate(unit_comp_data):
            file_key = f'document_file_{index}'
            if file_key in request.FILES:
                doc_data['upload_file'] = request.FILES[file_key]
                print(f"Added file for document {index}: {doc_data['upload_file'].name}")

        unit_data['unit_comp'] = unit_comp_data
        print("Processed unit data:", unit_data)

        serializer = UnitSerializer(unit, data=unit_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            print("Unit updated successfully")
            return Response(serializer.data)
        else:
            print("Errors in serializer:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
        tenant = self.get_object(pk)
        if not tenant:
            return Response({'error': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = TenantGetSerializer(tenant)
        return Response(serializer.data)
    def put(self, request, pk):
        print("Raw data:", request.data)
        tenant = self.get_object(pk)
        if not tenant:
            return Response({'error': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        # Transform FormData into nested JSON structure
        tenant_data = {}
        tenant_comp = []
        comp_index = 0
        # Extract tenant fields
        for key, value in request.data.items():
            if not key.startswith('tenant_comp'):
                # Handle QueryDict lists (e.g., company: ['4', '4'] -> '4')
                tenant_data[key] = value[0] if isinstance(value, list) and len(value) == 1 else value
        # Extract tenant_comp fields (place the provided snippet here)
        while f'tenant_comp[{comp_index}][doc_type]' in request.data:
            doc_data = {
                'doc_type': request.data.get(f'tenant_comp[{comp_index}][doc_type]'),
                'number': request.data.get(f'tenant_comp[{comp_index}][number]'),
                'issued_date': request.data.get(f'tenant_comp[{comp_index}][issued_date]'),
                'expiry_date': request.data.get(f'tenant_comp[{comp_index}][expiry_date]'),
                'id': request.data.get(f'tenant_comp[{comp_index}][id]'),  # Include document ID if provided
            }
            file_key = f'tenant_comp[{comp_index}][upload_file]'
            existing_file_key = f'tenant_comp[{comp_index}][existing_file_url]'
            if file_key in request.FILES:
                doc_data['upload_file'] = request.FILES[file_key]
            elif file_key in request.data:
                doc_data['upload_file'] = request.data.get(file_key)
            elif existing_file_key in request.data:
                doc_data['existing_file_url'] = request.data.get(existing_file_key)
            tenant_comp.append(doc_data)
            comp_index += 1
        if tenant_comp:
            tenant_data['tenant_comp'] = tenant_comp
        print("Processed tenant data:", tenant_data)
        serializer = TenantSerializer(tenant, data=tenant_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            print("Updated tenant:", serializer.data)
            return Response(serializer.data)
        print("Serializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    def delete(self, request, pk):
        building = self.get_object(pk)
        if not building:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        building.delete()
        return Response({'message': 'Building deleted'}, status=status.HTTP_204_NO_CONTENT)


class TenantByCompanyView(APIView):
    def get(self, request, company_id):
        search_query = request.query_params.get('search', '').strip()
        status_filter = request.query_params.get('status', '').strip().lower()
        tenants = Tenant.objects.filter(company__id=company_id)
        if search_query:
            tenants = tenants.filter(
                Q(tenant_name__icontains = search_query) |
                Q(created_at__icontains = search_query)   |
                Q(phone__icontains = search_query)|
                Q(code__icontains = search_query)|
                Q(id_type__title__icontains = search_query)
               

            )
        if status_filter in ['active','inactive']:
            tenants = tenants.filter(status__iexact=status_filter)
        serializer = TenantGetSerializer(tenants, many=True)
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


class PaymentSchedulePreviewView(APIView):
    def _ensure_charge_types(self, company_id):
        charge_types = {'Rent': None, 'Deposit': None, 'Commission': None}
        try:
            for charge_name in charge_types:
                charge_code = ChargeCode.objects.filter(title=charge_name, company_id=company_id).first()
                if not charge_code:
                    charge_code = ChargeCode.objects.create(company_id=company_id, title=charge_name)

                charge = Charges.objects.filter(name=charge_name, company_id=company_id).first()
                if not charge:
                    charge = Charges.objects.create(company_id=company_id, name=charge_name, charge_code=charge_code)

                charge_types[charge_name] = charge
            return charge_types
        except Exception as e:
            raise Exception(f"Error ensuring charge types: {str(e)}") 

    def _validate_request_data(self, data):
        try:
            required_fields = ['company', 'first_rent_due_on', 'start_date']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            date_fields = ['first_rent_due_on', 'start_date']
            for field in date_fields:
                if data.get(field):
                    try:
                        datetime.strptime(data[field], '%Y-%m-%d')
                    except ValueError:
                        raise ValueError(f"Invalid date format for {field}. Expected YYYY-MM-DD")

            validated_data = {
                'company_id': int(data.get('company')),
                'rental_months': int(data.get('rental_months', 12)),
                'no_payments': int(data.get('no_payments', 0)),
                'first_rent_due_on': data.get('first_rent_due_on'),
                'start_date': data.get('start_date'),
            }

            decimal_fields = {
                'rent_per_frequency': data.get('rent_per_frequency', 0),
                'deposit': data.get('deposit', 0),
                'commission': data.get('commission', 0)
            }

            for field, value in decimal_fields.items():
                try:
                    validated_data[field] = Decimal(str(value)) if value else Decimal('0')
                except (InvalidOperation, ValueError):
                    raise ValueError(f"Invalid decimal value for {field}: {value}")

            if validated_data['rental_months'] <= 0:
                raise ValueError("Rental months must be greater than 0")
            if validated_data['no_payments'] < 0:
                raise ValueError("Number of payments cannot be negative")

            return validated_data
        except (ValueError, TypeError) as e:
            raise ValueError(f"Data validation error: {str(e)}")

    def _calculate_tax(self, amount, charge, reference_date):
        try:
            tax_amount = Decimal('0.00')
            tax_details = []
            reference_date_obj = datetime.strptime(reference_date, '%Y-%m-%d').date() if reference_date else date.today()

            print(f"Calculating tax for charge: {charge.name}, amount: {amount}, reference_date: {reference_date_obj}")

            taxes = charge.taxes.filter(
                company=charge.company,
                is_active=True,
                applicable_from__lte=reference_date_obj,
                applicable_to__gte=reference_date_obj
            ) | charge.taxes.filter(
                company=charge.company,
                is_active=True,
                applicable_from__lte=reference_date_obj,
                applicable_to__isnull=True
            )

            print(f"Found {taxes.count()} taxes for charge {charge.name}")

            for tax in taxes:
                tax_percentage = Decimal(str(tax.tax_percentage))
                tax_contribution = (amount * tax_percentage) / Decimal('100')
                tax_amount += tax_contribution
                tax_details.append({
                    'tax_type': tax.tax_type,
                    'tax_percentage': str(tax_percentage),  # Convert to string for serialization
                    'tax_amount': str(tax_contribution.quantize(Decimal('0.01')))  # Convert to string
                })
                print(f"Tax: {tax.tax_type}, percentage: {tax_percentage}, contribution: {tax_contribution}")

            if not taxes.exists():
                print(f"No applicable taxes found for charge {charge.name} on {reference_date_obj}")

            return tax_amount.quantize(Decimal('0.01')), tax_details
        except Exception as e:
            print(f"Error calculating tax for charge {charge.name}: {str(e)}")
            return Decimal('0.00'), []

    def _generate_deposit_schedule(self, validated_data, charge_types):
        schedules = []
        deposit = validated_data['deposit']
        deposit_charge = charge_types['Deposit']
        if deposit and deposit_charge:
            tax_amount, tax_details = self._calculate_tax(deposit, deposit_charge, validated_data['start_date'])
            total = deposit + tax_amount
            schedules.append({
                'id': '01',
                'charge_type': deposit_charge,
                'charge_type_name': deposit_charge.name,
                'reason': 'Deposit',
                'due_date': validated_data['start_date'],
                'status': 'pending',
                'amount': deposit,
                'tax': tax_amount,
                'total': total,
                'tax_details': tax_details
            })
        return schedules

    def _generate_commission_schedule(self, validated_data, charge_types):
        schedules = []
        commission = validated_data['commission']
        commission_charge = charge_types['Commission']
        if commission and commission_charge:
            tax_amount, tax_details = self._calculate_tax(commission, commission_charge, validated_data['start_date'])
            total = commission + tax_amount
            schedules.append({
                'id': '02',
                'charge_type': commission_charge,
                'charge_type_name': commission_charge.name,
                'reason': 'Commission',
                'due_date': validated_data['start_date'],
                'status': 'pending',
                'amount': commission,
                'tax': tax_amount,
                'total': total,
                'tax_details': tax_details
            })
        return schedules

    def _generate_rent_schedule(self, validated_data, charge_types):
        schedules = []
        rent_per_frequency = validated_data['rent_per_frequency']
        no_payments = validated_data['no_payments']
        rental_months = validated_data['rental_months']
        rent_charge = charge_types['Rent']
        if not (rent_per_frequency and no_payments and rent_charge):
            return schedules

        try:
            # Calculate total rent amount
            total_rent = rent_per_frequency * rental_months
            # Calculate rent amount per payment
            if no_payments > 0:
                rent_per_payment = total_rent / no_payments
            else:
                rent_per_payment = total_rent  # If no_payments is 0, treat as single payment

            # Calculate tax based on rent per payment
            rent_tax, tax_details = self._calculate_tax(rent_per_payment, rent_charge, validated_data['first_rent_due_on'])

            # Determine payment frequency in months
            payment_frequency_months = rental_months // no_payments if no_payments > 0 else rental_months
            reason_map = {
                1: 'Monthly Rent',
                2: 'Bi-Monthly Rent',
                3: 'Quarterly Rent',
                6: 'Semi-Annual Rent',
                12: 'Annual Rent'
            }
            reason = reason_map.get(payment_frequency_months, f'{payment_frequency_months}-Monthly Rent')

            for i in range(max(1, no_payments)):  # Ensure at least one payment if no_payments is 0
                due_date = validated_data['first_rent_due_on']
                if i > 0:
                    due_date_obj = datetime.strptime(validated_data['first_rent_due_on'], '%Y-%m-%d')
                    year = due_date_obj.year
                    month = due_date_obj.month + (i * payment_frequency_months)
                    while month > 12:
                        year += 1
                        month -= 12
                    due_date = due_date_obj.replace(year=year, month=month).strftime('%Y-%m-%d')

                total = rent_per_payment + rent_tax
                schedules.append({
                    'id': str(i + 3).zfill(2),
                    'charge_type': rent_charge,
                    'charge_type_name': rent_charge.name,
                    'reason': reason,
                    'due_date': due_date,
                    'status': 'pending',
                    'amount': rent_per_payment.quantize(Decimal('0.01')),
                    'tax': rent_tax,
                    'total': total.quantize(Decimal('0.01')),
                    'tax_details': tax_details
                })
        except Exception as e:
            raise Exception(f"Error generating rent schedule: {str(e)}")
        return schedules

    def post(self, request):
        try:
            validated_data = self._validate_request_data(request.data)
            with transaction.atomic():
                charge_types = self._ensure_charge_types(validated_data['company_id'])

            payment_schedules = []
            payment_schedules.extend(self._generate_deposit_schedule(validated_data, charge_types))
            payment_schedules.extend(self._generate_commission_schedule(validated_data, charge_types))
            payment_schedules.extend(self._generate_rent_schedule(validated_data, charge_types))

            serializer = PaymentSchedulePreviewSerializer(payment_schedules, many=True)
            return Response({
                'success': True,
                'message': 'Payment schedule preview generated successfully',
                'payment_schedules': serializer.data
            }, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            error_message = f'Error generating payment schedule preview: {str(e)}'
            return Response({
                'success': False,
                'message': error_message
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdditionalChargeTaxPreviewView(APIView):
    """
    Generate a preview of tax calculations for an additional charge.
    
    Request Method: POST
    
    Request Body Parameters:
    - company (int, required): Company ID
    - charge_type (int, required): Charge type ID
    - amount (float/str, required): Charge amount
    - due_date (str, required): Due date in YYYY-MM-DD format
    
    Response Format:
    {
        "success": bool,
        "message": str,
        "additional_charge": {
            "id": str,
            "charge_type": int,
            "charge_type_name": str,
            "reason": str,
            "due_date": str,
            "status": str,
            "amount": decimal,
            "tax": decimal,
            "total": decimal,
            "tax_details": [
                {
                    "tax_type": str,
                    "tax_percentage": decimal,
                    "tax_amount": decimal
                }
            ]
        }
    }
    
    Error Responses:
    - 400: Missing required fields, invalid data types, or processing errors
    - 500: Internal server errors
    """

    def _validate_request_data(self, data):
        try:
            required_fields = ['company', 'charge_type', 'amount', 'due_date']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            try:
                datetime.strptime(data['due_date'], '%Y-%m-%d')
            except ValueError:
                raise ValueError("Invalid date format for due_date. Expected YYYY-MM-DD")

            validated_data = {
                'company_id': int(data.get('company')),
                'charge_type_id': int(data.get('charge_type')),
                'amount': Decimal(str(data.get('amount'))),
                'due_date': data.get('due_date'),
                'reason': data.get('reason', 'Additional Charge')
            }

            if validated_data['amount'] < 0:
                raise ValueError("Amount must be non-negative")

            return validated_data
        except (ValueError, TypeError, InvalidOperation) as e:
            raise ValueError(f"Data validation error: {str(e)}")

    def _calculate_tax(self, amount, charge, reference_date):
        try:
            tax_amount = Decimal('0.00')
            tax_details = []
            reference_date_obj = datetime.strptime(reference_date, '%Y-%m-%d').date()

            taxes = charge.taxes.filter(
                company=charge.company,
                is_active=True,
                applicable_from__lte=reference_date_obj,
                applicable_to__gte=reference_date_obj
            ) | charge.taxes.filter(
                company=charge.company,
                is_active=True,
                applicable_from__lte=reference_date_obj,
                applicable_to__isnull=True
            )

            for tax in taxes:
                tax_percentage = Decimal(str(tax.tax_percentage))
                tax_contribution = (amount * tax_percentage) / Decimal('100')
                tax_amount += tax_contribution
                tax_details.append({
                    'tax_type': tax.tax_type,
                    'tax_percentage': tax_percentage,
                    'tax_amount': tax_contribution.quantize(Decimal('0.01'))
                })

            return tax_amount.quantize(Decimal('0.01')), tax_details
        except Exception as e:
            return Decimal('0.00'), []

    def post(self, request):
        try:
            validated_data = self._validate_request_data(request.data)
            
            charge_type = Charges.objects.filter(
                id=validated_data['charge_type_id'],
                company_id=validated_data['company_id']
            ).first()

            if not charge_type:
                return Response({
                    'success': False,
                    'message': f"Charge type with id {validated_data['charge_type_id']} not found"
                }, status=status.HTTP_400_BAD_REQUEST)

            tax_amount, tax_details = self._calculate_tax(
                validated_data['amount'],
                charge_type,
                validated_data['due_date']
            )
            total = validated_data['amount'] + tax_amount

            # Create a dictionary for preview instead of model instance
            additional_charge_data = {
                'id': str(uuid.uuid4()),  # Generate a unique temporary ID
                'charge_type': charge_type.id,
                'charge_type_name': charge_type.name,
                'reason': validated_data['reason'],
                'due_date': validated_data['due_date'],
                'status': 'pending',
                'amount': validated_data['amount'],
                'tax': tax_amount,
                'total': total,
                'tax_details': tax_details
            }

            # Pass the dictionary directly to the serializer
            serializer = AdditionalChargeSerializer(data=additional_charge_data)
            if serializer.is_valid():
                return Response({
                    'success': True,
                    'message': 'Additional charge tax preview generated successfully',
                    'additional_charge': serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': f"Serialization error: {serializer.errors}"
                }, status=status.HTTP_400_BAD_REQUEST)

        except ValueError as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            error_message = f'Error generating additional charge tax preview: {str(e)}'
            return Response({
                'success': False,
                'message': error_message
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TenancyCreateView(APIView):
    """Create a new tenancy with automatic payment schedule generation"""
    
    def post(self, request):
        serializer = TenancyCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            tenancy = serializer.save()
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
            serializer = TenancyListSerializer(tenancy)
            
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
    def get(self, request, company_id):
        buildings = Building.objects.filter(
            company_id=company_id,
            unit_building__unit_status='vacant'
        ).distinct()
        serializer = BuildingSerializer(buildings, many=True)
        return Response(serializer.data)
    
    
class ConfirmTenancyView(APIView):
    def post(self, request, pk):
        tenancy = get_object_or_404(Tenancy, pk=pk)

        if tenancy.status == 'active':
            return Response({'detail': 'Tenancy is already active.'}, status=status.HTTP_400_BAD_REQUEST)

        unit = tenancy.unit
        if not unit:
            return Response({'detail': 'Tenancy has no unit assigned.'}, status=status.HTTP_400_BAD_REQUEST)

        tenancy.status = 'active'
        tenancy.save()

        unit.unit_status = 'occupied'

        unit.save()

        return Response({'detail': 'Tenancy confirmed and unit status set to occupied.'}, status=status.HTTP_200_OK)
    
    

class OccupiedUnitsByBuildingView(APIView):
    def get(self, request, building_id):
        try:
            building = Building.objects.get(id=building_id)
        except Building.DoesNotExist:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        
        vacant_units = Units.objects.filter(building=building, unit_status='occupied')
        serializer = UnitSerializer(vacant_units, many=True)
        return Response(serializer.data)


class BuildingsWithOccupiedUnitsView(APIView):
    def get(self, request, company_id):
        buildings = Building.objects.filter(
            company_id=company_id,
            unit_building__unit_status='occupied'
        ).distinct()
        serializer = BuildingSerializer(buildings, many=True)
        return Response(serializer.data)
 
 
class TenancyRenewalView(APIView):
    """Renew an existing tenancy"""
    
    def post(self, request, tenancy_id):
 
        original_tenancy = get_object_or_404(Tenancy, id=tenancy_id)
        
         
        if original_tenancy.status not in ['active', 'terminated']:
            return Response({
                'success': False,
                'message': 'Only active or terminated tenancies can be renewed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        
        if Tenancy.objects.filter(previous_tenancy=original_tenancy).exists():
            return Response({
                'success': False,
                'message': 'This tenancy has already been renewed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        print("Renewal request data:", request.data)
        
    
        serializer = TenancyRenewalSerializer(
            data=request.data,
            context={'original_tenancy_id': tenancy_id}
        )
        
        if serializer.is_valid():
            try:
                renewed_tenancy = serializer.save()
                
    
                detail_serializer = TenancyDetailSerializer(renewed_tenancy)
                
                return Response({
                    'success': True,
                    'message': 'Tenancy renewed successfully',
                    'original_tenancy_id': original_tenancy.id,
                    'renewed_tenancy': detail_serializer.data,
                    'renewal_number': renewed_tenancy.get_renewal_number()
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({
                    'success': False,
                    'message': f'Error renewing tenancy: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
        
class UserDetailView(APIView):
    def get(self, request, user_id):
        try:
            user = Users.objects.get(id=user_id)
            serializer = UserSerializer(user)
            return Response(serializer.data)
        except Users.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)


class TaxesAPIView(APIView):
    """
    API View for managing tax records with versioning support and robust error handling.
    Supports CRUD operations for tax records associated with a specific company.
    """

    def get(self, request, company_id, tax_id=None):
        """
        Retrieve a single tax record by tax_id or a list of tax records for a company.
        
        Args:
            request: The HTTP request object containing query parameters.
            company_id: The ID of the company whose tax records are being queried.
            tax_id: Optional ID of a specific tax record to retrieve (default: None).

        Returns:
            Response: JSON response with tax data or error details.
        """
        try:
            # Input Validation
            # Ensure company_id is a valid positive integer
            if not company_id or not str(company_id).isdigit():
                return Response(
                    {"detail": "Invalid company ID provided."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Database Operations
            # Fetch the company to ensure it exists
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                return Response(
                    {"detail": "Company not found."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Single Tax Retrieval
            if tax_id:
                # Validate tax_id is a positive integer
                if not str(tax_id).isdigit():
                    return Response(
                        {"detail": "Invalid tax ID provided."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Fetch and serialize the specific tax record
                try:
                    tax = Taxes.objects.get(id=tax_id, company=company)
                    serializer = TaxesSerializer(tax)
                    return Response(serializer.data, status=status.HTTP_200_OK)
                except Taxes.DoesNotExist:
                    return Response(
                        {"detail": "Tax record not found."}, 
                        status=status.HTTP_404_NOT_FOUND
                    )

            # Multiple Taxes Retrieval with Filtering
            # Extract query parameters for filtering tax records
            show_history = request.query_params.get('history', 'false').lower() == 'true'
            active_only = request.query_params.get('active_only', 'false').lower() == 'true'
            effective_date_str = request.query_params.get('effective_date')

            # Base query for all tax records of the company
            taxes = Taxes.objects.filter(company=company)

            # Apply date-based filtering if effective_date is provided
            if effective_date_str:
                try:
                    effective_date = date.fromisoformat(effective_date_str)
                    # Filter taxes that were applicable on the given date
                    taxes = taxes.filter(
                        applicable_from__lte=effective_date
                    ).filter(
                        models.Q(applicable_to__isnull=True) | 
                        models.Q(applicable_to__gte=effective_date)
                    )
                except ValueError:
                    return Response(
                        {"detail": "Invalid date format. Use YYYY-MM-DD."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            # Filter active taxes only if history is not requested or active_only is true
            elif active_only or not show_history:
                taxes = taxes.filter(is_active=True)

            # Serialize and return the filtered tax records
            serializer = TaxesSerializer(taxes, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            # Log unexpected errors for debugging
            logger.error(f"Unexpected error in GET taxes: {str(e)}")
            return Response(
                {"detail": "An unexpected error occurred while retrieving taxes."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, company_id):
        """
        Create a new tax record for a company, handling versioning for existing taxes.
        
        Args:
            request: The HTTP request object containing tax data in JSON format.
            company_id: The ID of the company to associate the new tax record with.

        Returns:
            Response: JSON response with the created tax data or error details.
        """
        try:
            # Input Validation
            # Ensure company_id is a valid positive integer
            if not company_id or not str(company_id).isdigit():
                return Response(
                    {"detail": "Invalid company ID provided."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Database Operations
            # Verify the company exists
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                return Response(
                    {"detail": "Company not found."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Validate Request Data
            # Ensure request body contains data
            if not request.data:
                return Response(
                    {"detail": "Request data is required."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Serialize and validate the incoming tax data
            serializer = TaxesSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Transaction Block
            # Use atomic transaction to ensure database consistency
            try:
                with transaction.atomic():
                    tax_type = serializer.validated_data['tax_type']
                    applicable_from = serializer.validated_data.get('applicable_from', date.today())

                    # Check for Existing Active Tax
                    # Find any active tax of the same type with no end date
                    existing_tax = Taxes.objects.filter(
                        company=company,
                        tax_type=tax_type,
                        is_active=True,
                        applicable_to__isnull=True
                    ).first()

                    if existing_tax:
                        # Close the existing tax period
                        end_date = applicable_from - timedelta(days=1)
                        if end_date < existing_tax.applicable_from:
                            return Response(
                                {"detail": "New tax applicable_from date cannot be before existing tax start date."}, 
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        
                        # Update the existing tax to set its end date and link to the new tax
                        existing_tax.close_tax_period(end_date)

                        # Create the new tax version
                        new_tax = serializer.save(
                            company=company,
                            applicable_from=applicable_from,
                            superseded_by=None
                        )
                        
                        # Link the existing tax to the new one
                        existing_tax.superseded_by = new_tax
                        existing_tax.save()
                    else:
                        # Create a new tax record without versioning
                        new_tax = serializer.save(
                            company=company,
                            applicable_from=applicable_from
                        )

                    # Return the serialized new tax record
                    return Response(serializer.data, status=status.HTTP_201_CREATED)

            except IntegrityError as e:
                # Handle database constraint violations
                logger.error(f"Database integrity error in POST taxes: {str(e)}")
                return Response(
                    {"detail": "A database constraint was violated. Please check your data."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            except ValidationError as e:
                # Handle validation errors from the model
                logger.error(f"Validation error in POST taxes: {str(e)}")
                return Response(
                    {"detail": f"Validation error: {str(e)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            # Log unexpected errors for debugging
            logger.error(f"Unexpected error in POST taxes: {str(e)}")
            return Response(
                {"detail": "An unexpected error occurred while creating the tax record."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, company_id, tax_id):
        """
        Update an existing tax record or create a new version if critical fields change.
        
        Args:
            request: The HTTP request object containing updated tax data in JSON format.
            company_id: The ID of the company associated with the tax record.
            tax_id: The ID of the tax record to update.

        Returns:
            Response: JSON response with the updated or new tax data or error details.
        """
        try:
            # Input Validation
            # Ensure company_id and tax_id are valid positive integers
            if not company_id or not str(company_id).isdigit():
                return Response(
                    {"detail": "Invalid company ID provided."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not tax_id or not str(tax_id).isdigit():
                return Response(
                    {"detail": "Invalid tax ID provided."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Database Operations
            # Verify the company exists
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                return Response(
                    {"detail": "Company not found."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Fetch the existing tax record
            try:
                existing_tax = Taxes.objects.get(id=tax_id, company=company)
            except Taxes.DoesNotExist:
                return Response(
                    {"detail": "Tax record not found."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Validate Request Data
            # Ensure request body contains data
            if not request.data:
                return Response(
                    {"detail": "Request data is required."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Prepare Data for Update
            # Create a mutable copy of request data, preserving existing values for unspecified fields
            data = request.data.copy()
            if 'is_active' not in data:
                data['is_active'] = existing_tax.is_active
            if 'applicable_to' not in data:
                data['applicable_to'] = existing_tax.applicable_to
            if 'applicable_from' not in data:
                data['applicable_from'] = existing_tax.applicable_from

            # Serialize and validate the updated data
            serializer = TaxesSerializer(existing_tax, data=data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Transaction Block
            # Use atomic transaction to ensure database consistency
            try:
                with transaction.atomic():
                    validated_data = serializer.validated_data
                    applicable_from = validated_data.get('applicable_from', existing_tax.applicable_from)
                    
                    # Handle string to date conversion for applicable_from
                    if isinstance(applicable_from, str):
                        try:
                            applicable_from = date.fromisoformat(applicable_from)
                        except ValueError:
                            return Response(
                                {"detail": "Invalid date format for applicable_from. Use YYYY-MM-DD."}, 
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    # Check for Critical Field Changes
                    # Determine if tax_percentage, applicable_from, or applicable_to have changed
                    critical_fields_changed = (
                        validated_data.get('tax_percentage') != existing_tax.tax_percentage or
                        validated_data.get('applicable_from') != existing_tax.applicable_from or
                        validated_data.get('applicable_to') != existing_tax.applicable_to
                    )

                    if critical_fields_changed:
                        # Validate new applicable_from date
                        if applicable_from < existing_tax.applicable_from:
                            return Response(
                                {"detail": "New applicable_from date cannot be before the current tax start date."}, 
                                status=status.HTTP_400_BAD_REQUEST
                            )

                        # Close the existing tax period
                        end_date = applicable_from - timedelta(days=1)
                        existing_tax.close_tax_period(end_date)

                        # Create a new tax version
                        new_tax = Taxes.objects.create(
                            company=company,
                            tax_type=validated_data.get('tax_type', existing_tax.tax_type),
                            tax_percentage=validated_data.get('tax_percentage', existing_tax.tax_percentage),
                            country=validated_data.get('country', existing_tax.country),
                            state=validated_data.get('state', existing_tax.state),
                            applicable_from=applicable_from,
                            applicable_to=None,
                            is_active=True,
                            user=existing_tax.user
                        )
                        
                        # Link the existing tax to the new version
                        existing_tax.superseded_by = new_tax
                        existing_tax.save()

                        # Return the serialized new tax record
                        new_serializer = TaxesSerializer(new_tax)
                        return Response(new_serializer.data, status=status.HTTP_200_OK)
                    else:
                        # Update the existing tax record without versioning
                        serializer.save()
                        return Response(serializer.data, status=status.HTTP_200_OK)

            except IntegrityError as e:
                # Handle database constraint violations
                logger.error(f"Database integrity error in PUT taxes: {str(e)}")
                return Response(
                    {"detail": "A database constraint was violated. Please check your data."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            except ValidationError as e:
                # Handle validation errors from the model
                logger.error(f"Validation error in PUT taxes: {str(e)}")
                return Response(
                    {"detail": f"Validation error: {str(e)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            # Log unexpected errors for debugging
            logger.error(f"Unexpected error in PUT taxes: {str(e)}")
            return Response(
                {"detail": "An unexpected error occurred while updating the tax record."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, company_id, tax_id):
        """
        Soft delete a tax record by setting is_active to False and updating applicable_to.
        
        Args:
            request: The HTTP request object.
            company_id: The ID of the company associated with the tax record.
            tax_id: The ID of the tax record to deactivate.

        Returns:
            Response: JSON response with success or error details.
        """
        try:
            # Input Validation
            # Ensure company_id and tax_id are valid positive integers
            if not company_id or not str(company_id).isdigit():
                return Response(
                    {"detail": "Invalid company ID provided."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not tax_id or not str(tax_id).isdigit():
                return Response(
                    {"detail": "Invalid tax ID provided."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Database Operations
            # Verify the company exists
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                return Response(
                    {"detail": "Company not found."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Fetch the tax record
            try:
                tax = Taxes.objects.get(id=tax_id, company=company)
            except Taxes.DoesNotExist:
                return Response(
                    {"detail": "Tax record not found."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check if Tax is Already Inactive
            if not tax.is_active:
                return Response(
                    {"detail": "Tax record is already inactive."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Transaction Block
            # Use atomic transaction to ensure database consistency
            try:
                with transaction.atomic():
                    # Soft delete by setting is_active to False and applicable_to to today
                    tax.is_active = False
                    tax.applicable_to = date.today()
                    tax.save()

                    # Return success message
                    return Response(
                        {"detail": "Tax record has been successfully deactivated."}, 
                        status=status.HTTP_200_OK
                    )

            except IntegrityError as e:
                # Handle database constraint violations
                logger.error(f"Database integrity error in DELETE taxes: {str(e)}")
                return Response(
                    {"detail": "A database constraint was violated."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            # Log unexpected errors for debugging
            logger.error(f"Unexpected error in DELETE taxes: {str(e)}")
            return Response(
                {"detail": "An unexpected error occurred while deleting the tax record."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TaxCalculationHelper:
    """
    Helper class for performing tax calculations and retrieving tax change history.
    """

    @staticmethod
    def calculate_tax(company, tax_type, amount, calculation_date=None):
        """
        Calculate the tax amount for a given company, tax type, and date.

        Args:
            company: The Company instance to calculate taxes for.
            tax_type: The type of tax (e.g., 'VAT', 'GST').
            amount: The base amount to apply the tax rate to.
            calculation_date: The date for which to calculate the tax (defaults to today).

        Returns:
            tuple: (tax_amount, tax_record) or (0, None) if no applicable tax record is found.
        """
        if calculation_date is None:
            calculation_date = date.today()
            
        # Retrieve the active tax record for the specified date
        tax_record = Taxes.get_active_tax(company, tax_type, calculation_date)
        if not tax_record:
            return 0, None
            
        # Calculate tax amount based on the tax percentage
        tax_amount = (amount * tax_record.tax_percentage) / 100
        return tax_amount, tax_record
    
    @staticmethod
    def get_tax_changes(company, tax_type, from_date, to_date):
        """
        Retrieve all tax records for a company and tax type within a date range.

        Args:
            company: The Company instance to query tax records for.
            tax_type: The type of tax (e.g., 'VAT', 'GST').
            from_date: The start date of the period.
            to_date: The end date of the period.

        Returns:
            QuerySet: Ordered list of tax records within the specified date range.
        """
        return Taxes.objects.filter(
            company=company,
            tax_type=tax_type,
            applicable_from__gte=from_date,
            applicable_from__lte=to_date
        ).order_by('applicable_from')
        

class TenancyHTMLPDFView(APIView):
    def get(self, request, tenancy_id):
        tenancy = get_object_or_404(Tenancy, pk=tenancy_id)
        template = get_template("company/tenancy_pdf.html")
        html = template.render({'tenancy': tenancy})

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="tenancy_{tenancy.tenancy_code}.pdf"'

        pisa_status = pisa.CreatePDF(html, dest=response)

        if pisa_status.err:
            return HttpResponse("Error generating PDF", status=500)
        return response



class AdditionalChargeCreateView(APIView):
    """Create a new additional charge"""
    # permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            tenancy_id = data.get('tenancy')
            charge_type_id = data.get('charge_type')
            reason = data.get('reason')
            in_date = data.get('in_date')  
            due_date = data.get('due_date')
            amount = data.get('amount')
            tax = data.get('tax', '0.00')
            charge_status = data.get('status', 'pending')  # Rename to avoid conflict

            # Validate required fields
            if not all([tenancy_id, charge_type_id, reason,in_date, due_date, amount, charge_status]):
                return Response({
                    'success': False,
                    'message': 'All required fields (tenancy, charge_type, reason, due_date, amount, status) must be provided'
                }, status=status.HTTP_400_BAD_REQUEST)  # Use status module

            # Fetch related objects
            try:
                tenancy = Tenancy.objects.get(id=tenancy_id)
                charge_type = Charges.objects.get(id=charge_type_id)
            except Tenancy.DoesNotExist:
                return Response({
                    'success': False,
                    'message': f'Tenancy with id {tenancy_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)  # Use status module
            except Charges.DoesNotExist:
                return Response({
                    'success': False,
                    'message': f'Charge type with id {charge_type_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)  # Use status module

            # Calculate total
            amount_decimal = Decimal(str(amount))
            tax_decimal = Decimal(str(tax))
            total = amount_decimal + tax_decimal

            # Create additional charge
            with transaction.atomic():
                additional_charge = AdditionalCharge.objects.create(
                    tenancy=tenancy,
                    charge_type=charge_type,
                    reason=reason,
                    in_date=in_date,  
                    due_date=due_date,
                    status=charge_status,  # Use renamed variable
                    amount=amount_decimal,
                    tax=tax_decimal,
                    total=total
                )

            serializer = AdditionalChargeGetSerializer(additional_charge)
            return Response({
                'success': True,
                'message': 'Additional charge created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)  # Use status module

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error creating additional charge: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)  # Use status module


class AdditionalChargeUpdateView(APIView):
    """Update an existing additional charge"""
    # permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            data = request.data
            tenancy_id = data.get('tenancy')
            charge_type_id = data.get('charge_type')
            reason = data.get('reason')
            in_date = data.get('in_date')  # Added in_date field
            due_date = data.get('due_date')
            amount = data.get('amount')
            tax = data.get('tax', '0.00')
            status_field = data.get('status')  # Renamed to avoid conflict

            # Validate required fields
            if not all([tenancy_id, charge_type_id, reason, due_date, amount, status_field]):
                return Response({
                    'success': False,
                    'message': 'All required fields (tenancy, charge_type, reason, due_date, amount, status) must be provided'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Fetch the additional charge
            try:
                additional_charge = AdditionalCharge.objects.get(pk=pk)
            except AdditionalCharge.DoesNotExist:
                return Response({
                    'success': False,
                    'message': f'Additional charge with id {pk} not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Fetch related objects
            try:
                tenancy = Tenancy.objects.get(id=tenancy_id)
                charge_type = Charges.objects.get(id=charge_type_id)
            except Tenancy.DoesNotExist:
                return Response({
                    'success': False,
                    'message': f'Tenancy with id {tenancy_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)
            except Charges.DoesNotExist:
                return Response({
                    'success': False,
                    'message': f'Charge type with id {charge_type_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Calculate total
            amount_decimal = Decimal(str(amount))
            tax_decimal = Decimal(str(tax))
            total = amount_decimal + tax_decimal

            # Update additional charge
            with transaction.atomic():
                additional_charge.tenancy = tenancy
                additional_charge.charge_type = charge_type
                additional_charge.reason = reason
                additional_charge.in_date = in_date  # Update in_date field
                additional_charge.due_date = due_date
                additional_charge.status = status_field
                additional_charge.amount = amount_decimal
                additional_charge.tax = tax_decimal
                additional_charge.total = total
                additional_charge.save()

            serializer = AdditionalChargeGetSerializer(additional_charge)
            return Response({
                'success': True,
                'message': 'Additional charge updated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error updating additional charge: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdditionalChargeListView(APIView):
    """List all additional charges with pagination, filtering, and search"""
    pagination_class = CustomPagination
    
    def get(self, request):
        try:
            queryset = AdditionalCharge.objects.select_related('tenancy', 'charge_type').order_by('-id')
            
            # Apply filters
            tenancy_id = request.query_params.get('tenancy_id')
            status_filter = request.query_params.get('status')
            
            if tenancy_id:
                queryset = queryset.filter(tenancy__id=tenancy_id)
            
            if status_filter:
                queryset = queryset.filter(status__iexact=status_filter)
            
            # Apply search
            search_term = request.query_params.get('search', '')
            if search_term:
                queryset = queryset.filter(
                    Q(id__icontains=search_term) |
                    Q(charge_type__name__icontains=search_term) |
                    Q(reason__icontains=search_term) |
                    Q(tenancy__tenancy_code__icontains=search_term) |
                    Q(amount__icontains=search_term)
                )
            
            # Paginate the results
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(queryset, request)
            
            if page is not None:
                serializer = AdditionalChargeGetSerializer(page, many=True)
                return paginator.get_paginated_response({
                    'success': True,
                    'message': 'Additional charges retrieved successfully',
                    'data': serializer.data
                })
            
            # If no pagination, return all results
            serializer = AdditionalChargeGetSerializer(queryset, many=True)
            return Response({
                'success': True,
                'message': 'Additional charges retrieved successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving additional charges: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdditionalChargeDeleteView(APIView):
    """Delete an additional charge by ID"""
    # permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            charge = AdditionalCharge.objects.get(pk=pk)
            charge.delete()
            return Response({
                'success': True,
                'message': 'Additional charge deleted successfully'
            }, status=status.HTTP_204_NO_CONTENT)
        except AdditionalCharge.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Additional charge not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error deleting additional charge: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdditionalChargeExportCSVView(APIView):
    """
    Export AdditionalCharge objects as CSV, respecting tenancy, status,
    and free‑text `search` filters.
    """

    def get(self, request):
        try:
            # ------------------------------------------------------------------
            # 1. Build filtered queryset
            # ------------------------------------------------------------------
            qs = (AdditionalCharge.objects
                  .select_related("tenancy", "charge_type")
                  .order_by("-id"))

            tenancy_id   = request.query_params.get("tenancy_id")
            status_param = request.query_params.get("status")
            search_term  = request.query_params.get("search", "")

            if tenancy_id:
                qs = qs.filter(tenancy__id=tenancy_id)

            if status_param and status_param.lower() != "all":
                qs = qs.filter(status__iexact=status_param)

            if search_term:
                qs = qs.filter(
                    Q(id=search_term) |  # exact match avoids AutoField look‑up errors
                    Q(charge_type__name__icontains=search_term) |
                    Q(reason__icontains=search_term) |
                    Q(tenancy__tenancy_code__icontains=search_term) |
                    Q(amount__icontains=search_term)
                )

            # ------------------------------------------------------------------
            # 2. Streaming CSV generator
            # ------------------------------------------------------------------
            def stream_csv():
                buf = io.StringIO()
                writer = csv.writer(buf)

                writer.writerow([
                    "ID", "Charge Type", "Amount", "Reason","In Date", "Due Date",
                    "Status", "Tax", "Total", "Tenancy Code"
                ])

                for ch in qs:
                    writer.writerow([
                        ch.id,
                        ch.charge_type.name if ch.charge_type else "N/A",
                        f"{ch.amount:.2f}" if ch.amount is not None else "0.00",
                        ch.reason or "N/A",
                        ch.in_date.strftime("%d-%b-%Y") if ch.in_date else "N/A",
                        ch.due_date.strftime("%d-%b-%Y") if ch.due_date else "N/A",
                        ch.status.capitalize() if ch.status else "N/A",
                        f"{ch.tax:.2f}"   if ch.tax   is not None else "0.00",
                        f"{ch.total:.2f}" if ch.total is not None else "0.00",
                        ch.tenancy.tenancy_code if ch.tenancy else "N/A",
                    ])

                    # hand back each chunk as UTF‑8 bytes
                    buf.seek(0)
                    data = buf.read()
                    yield data.encode("utf-8")
                    buf.seek(0)
                    buf.truncate(0)

            # ------------------------------------------------------------------
            # 3. Build StreamingHttpResponse (ASCII‑safe headers!)
            # ------------------------------------------------------------------
            response = StreamingHttpResponse(
                streaming_content=stream_csv(),
                content_type="text/csv; charset=utf-8",
            )
            # filename must be ASCII: quote() handles spaces & non‑ASCII safely
            filename = quote("additional_charges.csv")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            return response

        except Exception as exc:
            log.exception("AdditionalCharge CSV export failed")
            return Response(
                {
                    "success": False,
                    "message": f"Error exporting additional charges: {exc}",
                    "data": [],
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
                       

class CreateInvoiceAPIView(APIView):
    def post(self, request):
        print("Request data:", request.data)
        serializer = InvoiceSerializer(data=request.data)
        if serializer.is_valid():
            invoice = serializer.save()
            
            # Send email with PDF attachment
            self.send_invoice_email(invoice)
            
            print("Created invoice:", {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'company': invoice.company_id,
                'user': invoice.user_id,
                'total_amount': str(invoice.total_amount),
                'status': invoice.status
            })
            return Response({
                'success': True,
                'message': 'Invoice created successfully',
                'invoice': {
                    'id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'total_amount': str(invoice.total_amount),
                    'status': invoice.status
                }
            }, status=status.HTTP_201_CREATED)
        print("Serializer errors:", serializer.errors)
        return Response({
            'success': False,
            'message': 'Failed to create invoice',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def send_invoice_email(self, invoice):
        # Render HTML content
        html_content = render_to_string('company/invoice_body.html', {'invoice': invoice})
        
        # Create PDF
        pdf_content = render_to_string('company/invoice_pdf.html', {'invoice': invoice})
        pdf_file = BytesIO()
        pisa.CreatePDF(pdf_content, dest=pdf_file)
        
        # Prepare email
        subject = f"Invoice #{invoice.invoice_number} from {invoice.company.company_name}"
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = invoice.tenancy.tenant.email
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=html_content,
            from_email=from_email,
            to=[to_email]
        )
        email.attach_alternative(html_content, "text/html")
        
        # Attach PDF
        email.attach(
            filename=f"Invoice_{invoice.invoice_number}.pdf",
            content=pdf_file.getvalue(),
            mimetype='application/pdf'
        )
        
        email.send()


class GetInvoicesByCompanyAPIView(APIView):
    def get(self, request, company_id):
        try:
            # Filter invoices by company
            queryset = Invoice.objects.filter(company_id=company_id)

            # Handle search query
            search = request.query_params.get('search', '')
            if search:
                queryset = queryset.filter(
                    Q(invoice_number__icontains=search) |
                    Q(in_date__icontains=search) |
                    Q(tenancy__tenancy_code__icontains=search) |
                    Q(tenancy__tenant__tenant_name__icontains=search) |
                    Q(total_amount__icontains=search)
                )

            # Handle status filter
            status_filter = request.query_params.get('status', '')
            if status_filter:
                queryset = queryset.filter(status=status_filter)

            # Apply pagination
            return paginate_queryset(queryset, request, InvoiceGetSerializer)
        except Exception as e:
            return Response(
                {'success': False, 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            

class DeleteInvoiceAPIView(APIView):
    def delete(self, request, invoice_id):
        try:
            invoice = Invoice.objects.get(id=invoice_id)
            invoice_number = invoice.invoice_number  
            invoice.delete()
            return Response({
                'success': True,
                'message': f'Invoice {invoice_number} deleted successfully'
            }, status=status.HTTP_200_OK)
        except ObjectDoesNotExist:
            return Response({
                'success': False,
                'message': f'Invoice with ID {invoice_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error deleting invoice: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            
            
class InvoiceDetailView(APIView):
    def get_object(self, pk):
        try:
            return Invoice.objects.get(pk=pk)
        except Invoice.DoesNotExist:
            return None

    def get(self, request, pk):
        invoice = self.get_object(pk)
        if not invoice:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = InvoiceGetSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvoiceExportCSVView(APIView):
    """
    Export Invoice objects as CSV, including associated additional charges,
    respecting search, status, and company filters.
    """

    def get(self, request, company_id):
        try:
            # 1. Build filtered queryset
            queryset = Invoice.objects.filter(company_id=company_id).select_related('tenancy', 'tenancy__tenant').prefetch_related('additional_charges')

            # Handle search query
            search = request.query_params.get('search', '')
            if search:
                queryset = queryset.filter(
                    Q(invoice_number__icontains=search) |
                    Q(in_date__icontains=search) |
                    Q(tenancy__tenancy_code__icontains=search) |
                    Q(tenancy__tenant__tenant_name__icontains=search) |
                    Q(total_amount__icontains=search)
                )

            # Handle status filter
            status_filter = request.query_params.get('status', '')
            if status_filter and status_filter.lower() != 'all':
                queryset = queryset.filter(status__iexact=status_filter)

            # 2. Streaming CSV generator
            def stream_csv():
                buf = io.StringIO()
                writer = csv.writer(buf)

                # Write header
                writer.writerow([
                    "Invoice ID", "Invoice Number", "Date", "Tenant Name", "Total Amount",
                    "Status", "Tenancy Code", "Additional Charge ID", "Charge Type",
                    "Charge Amount", "Charge Reason", "Charge Date", "Charge Status"
                ])

                for invoice in queryset:
                    tenant_name = invoice.tenancy.tenant.tenant_name if invoice.tenancy and invoice.tenancy.tenant else "N/A"
                    tenancy_code = invoice.tenancy.tenancy_code if invoice.tenancy else "N/A"
                    additional_charges = invoice.additional_charges.all()

                    if not additional_charges:
                        # Write invoice row without additional charges
                        writer.writerow([
                            invoice.id,
                            invoice.invoice_number or "N/A",
                            invoice.in_date.strftime("%d-%b-%Y") if invoice.in_date else "N/A",
                            tenant_name,
                            f"{invoice.total_amount:.2f}" if invoice.total_amount else "0.00",
                            invoice.status.capitalize() if invoice.status else "N/A",
                            tenancy_code,
                            "", "", "", "", "", ""
                        ])
                    else:
                        # Write one row per additional charge
                        for charge in additional_charges:
                            writer.writerow([
                                invoice.id,
                                invoice.invoice_number or "N/A",
                                invoice.in_date.strftime("%d-%b-%Y") if invoice.in_date else "N/A",
                                tenant_name,
                                f"{invoice.total_amount:.2f}" if invoice.total_amount else "0.00",
                                invoice.status.capitalize() if invoice.status else "N/A",
                                tenancy_code,
                                charge.id,
                                charge.charge_type.name if charge.charge_type else "N/A",
                                f"{charge.amount:.2f}" if charge.amount else "0.00",
                                charge.reason or "N/A",
                                charge.in_date.strftime("%d-%b-%Y") if charge.in_date else "N/A",
                                charge.status.capitalize() if charge.status else "N/A"
                            ])

                    # Hand back each chunk as UTF-8 bytes
                    buf.seek(0)
                    data = buf.read()
                    yield data.encode("utf-8")
                    buf.seek(0)
                    buf.truncate(0)

            # 3. Build StreamingHttpResponse
            response = StreamingHttpResponse(
                streaming_content=stream_csv(),
                content_type="text/csv; charset=utf-8",
            )
            filename = quote(f"invoices_company_{company_id}.csv")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            return response

        except Exception as exc:
            return Response(
                {
                    "success": False,
                    "message": f"Error exporting invoices: {exc}",
                    "data": [],
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )