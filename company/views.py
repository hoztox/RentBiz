from django.shortcuts import render
from .serializers import *
from .models import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.db.models import Q
import logging
from django.shortcuts import get_object_or_404
logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
import jwt
import re
from rest_framework import generics
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from collections import defaultdict
from django.utils import timezone
import json
from datetime import date


 
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
#         unit_count = building.unit_building.count()  

#         data = serializer.data
#         data['unit_count'] = unit_count   

#         return Response(data)

#     def put(self, request, pk):
#         building = self.get_object(pk)
#         if not building:
#             return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        
#         print("Request data:", request.data)
        
     
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
        
      
#         building_data = {
#             'company': request.data.get('company'),
#             'building_name': request.data.get('building_name'),
#             'building_no': request.data.get('building_no'),
#             'plot_no': request.data.get('plot_no'),
#             'description': get_value_or_none('description'),
#             'remarks': get_value_or_none('remarks'),
#             'latitude': get_value_or_none('latitude', float),
#             'longitude': get_value_or_none('longitude', float),
#             'status': get_value_or_none('status') or building.status,

#             'land_mark': get_value_or_none('land_mark'),
#             'building_address': get_value_or_none('building_address'),
#         }
        
     
#         documents_data = []
#         documents_provided = False   
        
        
#         if 'build_comp' in request.data:
#             documents_provided = True
            
   
#             if isinstance(request.data['build_comp'], list):
#                 documents_data = request.data['build_comp']
#             else:
 
#                 document_groups = defaultdict(dict)
                
#                 for key, value in request.data.items():
#                     if key.startswith('build_comp['):
#                         match = re.match(r'build_comp\[(\d+)\]\[(\w+)\]', key)
#                         if match:
#                             index = int(match.group(1))
#                             field_name = match.group(2)
#                             document_groups[index][field_name] = value
                
#                 for index in sorted(document_groups.keys()):
#                     doc_data = document_groups[index]
                  
#                     if any(key in doc_data for key in ['doc_type', 'number', 'issued_date', 'expiry_date', 'upload_file']):
              
#                         if 'id' in doc_data and doc_data['id']:
#                             try:
#                                 doc_data['id'] = int(doc_data['id'])
#                             except (ValueError, TypeError):
#                                 doc_data.pop('id')  
#                         documents_data.append(doc_data)
        
  
#         elif any(key.startswith('build_comp[') for key in request.data.keys()):
#             documents_provided = True
        
#             document_groups = defaultdict(dict)
            
#             for key, value in request.data.items():
#                 if key.startswith('build_comp['):
#                     match = re.match(r'build_comp\[(\d+)\]\[(\w+)\]', key)
#                     if match:
#                         index = int(match.group(1))
#                         field_name = match.group(2)
#                         document_groups[index][field_name] = value
            
#             for index in sorted(document_groups.keys()):
#                 doc_data = document_groups[index]
               
#                 if any(key in doc_data for key in ['doc_type', 'number', 'issued_date', 'expiry_date', 'upload_file']):
          
#                     if 'id' in doc_data and doc_data['id']:
#                         try:
#                             doc_data['id'] = int(doc_data['id'])
#                         except (ValueError, TypeError):
#                             doc_data.pop('id')   
#                     documents_data.append(doc_data)
        
       
#         final_data = building_data.copy()
        
      
#         if documents_provided:
#             final_data['build_comp'] = documents_data
#             print("Documents data included:", documents_data)
#         else:
#             print("No document data provided - preserving existing documents")
        
#         print("Processed data:", final_data)
        
   
#         serializer = BuildingSerializer(building, data=final_data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data)
        
#         print("Serializer errors:", serializer.errors)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def delete(self, request, pk):
#         building = self.get_object(pk)
#         if not building:
#             return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
#         building.delete()
#         return Response({'message': 'Building deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

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
            'country': request.data.get('country',int),
            'state': request.data.get('state',int),
        }
        # Process document data
        documents_data = []
        document_files = []
        # Handle both form-data and JSON formats
        if 'build_comp' in request.data:
            # JSON format
            if isinstance(request.data['build_comp'], list):
                documents_data = request.data['build_comp']
            else:
                # Form-data format
                document_groups = defaultdict(dict)
                for key, value in request.data.items():
                    if key.startswith('build_comp['):
                        match = re.match(r'build_comp\[(\d+)\]\[(\w+)\]', key)
                        if match:
                            index = int(match.group(1))
                            field_name = match.group(2)
                            document_groups[index][field_name] = value
                for index in sorted(document_groups.keys()):
                    documents_data.append(document_groups[index])
        # Handle file uploads separately
        for file_key, file_obj in request.FILES.items():
            if file_key.startswith('build_comp['):
                match = re.match(r'build_comp\[(\d+)\]\[upload_file\]', file_key)
                if match:
                    index = int(match.group(1))
                    if index < len(documents_data):
                        documents_data[index]['upload_file'] = file_obj
        try:
            with transaction.atomic():
                # Update building data
                building_serializer = BuildingSerializer(building, data=building_data, partial=True)
                if not building_serializer.is_valid():
                    return Response(building_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                updated_building = building_serializer.save()
                # Handle documents
                if documents_data:
                    # First delete existing documents if we're replacing them
                    DocumentType.objects.filter(building=updated_building).delete()
                    # Create new documents
                    for doc_data in documents_data:
                        doc_serializer = DocumentTypeSerializer(data={
                            'building': updated_building.id,
                            'doc_type': doc_data.get('doc_type'),
                            'number': doc_data.get('number'),
                            'issued_date': doc_data.get('issued_date'),
                            'expiry_date': doc_data.get('expiry_date'),
                            'upload_file': doc_data.get('upload_file'),
                        })
                        if not doc_serializer.is_valid():
                            return Response(doc_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                        doc_serializer.save()
                return Response(building_serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        building = self.get_object(pk)
        if not building:
            return Response({'error': 'Building not found'}, status=status.HTTP_404_NOT_FOUND)
        building.delete()
        return Response({'message': 'Building deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


class BuildingByCompanyView(APIView):
    def get(self, request, company_id):
        
        search_query = request.query_params.get('search', '').strip()
        status_filter = request.query_params.get('status', '').strip().lower()
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
            
        return paginate_queryset(buildings, request, BuildingSerializer)
        
        




class UnitCreateView(APIView):
    def post(self, request):
        print("Raw request data:", request.data)
        
   
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
        print("Raw request data:", request.data)
        print("Files keys received:", request.FILES.keys())

        try:
            unit = Units.objects.get(pk=pk)
        except Units.DoesNotExist:
            return Response({'error': 'Unit not found'}, status=status.HTTP_404_NOT_FOUND)

     
        if 'upload_file' in request.FILES:
            uploaded_file = request.FILES['upload_file']
            print(f"Processing file: {uploaded_file.name}")
            
            
            existing_doc = unit.unit_comp.first()  
            
            if existing_doc:
       
                existing_doc.upload_file = uploaded_file
                existing_doc.save()
                print(f"Updated existing document {existing_doc.id} with file: {existing_doc.upload_file}")
            else:
        
                new_doc = UnitDocumentType.objects.create(
                    unit=unit,
                    upload_file=uploaded_file,
                    number='AUTO-' + str(unit.id),
                    doc_type_id=1   
                )
                print(f"Created new document {new_doc.id} with file: {new_doc.upload_file}")

     
        unit_data = {}
        for key, value in request.data.items():
            if key not in ['upload_file', 'unit_comp_json'] and not key.startswith('document_file_'):
                unit_data[key] = value

   
        if unit_data:
            serializer = UnitSerializer(unit, data=unit_data, partial=True)
            if serializer.is_valid():
                serializer.save()
                print("Unit data updated successfully")
            else:
                print("Serializer errors:", serializer.errors)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

     
        response_serializer = UnitSerializer(unit)
        print("Final response:", response_serializer.data)
        
        return Response(response_serializer.data, status=status.HTTP_200_OK)


 
    
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
        tenant = self.get_object(pk)
        if not tenant:
            return Response({'error': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = TenantGetSerializer(tenant)
        return Response(serializer.data)

    def put(self, request, pk):
        tenant = self.get_object(pk)
        if not tenant:
            return Response({'error': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        tenant_data = {}
        for key, value in request.data.items():
            if key != 'tenant_comp_json' and not key.startswith('document_file_'):
                tenant_data[key] = value

        tenant_comp_json = request.data.get('tenant_comp_json')
        if tenant_comp_json:
            try:
                tenant_comp_data = json.loads(tenant_comp_json)

                for doc_data in tenant_comp_data:
                    file_index = doc_data.pop('file_index', None)
                    if file_index is not None:
                        file_key = f'document_file_{file_index}'
                        if file_key in request.FILES:
                            doc_data['upload_file'] = request.FILES[file_key]
              
                tenant_data['tenant_comp'] = tenant_comp_data

            except json.JSONDecodeError:
                return Response({'error': 'Invalid JSON in tenant_comp_json'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TenantSerializer(tenant, data=tenant_data, partial=True)
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
        print("rrrrr",request.data)
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
    Enhanced API View with tax versioning support
    """

    def get(self, request, company_id, tax_id=None):
        """
        Enhanced GET method with optional query parameters:
        - ?history=true : Get complete tax history
        - ?active_only=true : Get only active taxes
        - ?effective_date=YYYY-MM-DD : Get taxes effective on specific date
        """
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response(
                {"detail": "Company not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Handle single tax record request
        if tax_id:
            try:
                tax = Taxes.objects.get(id=tax_id, company=company)
                serializer = TaxesSerializer(tax)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Taxes.DoesNotExist:
                return Response(
                    {"detail": "Tax record not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Handle query parameters
        show_history = request.query_params.get('history', 'false').lower() == 'true'
        active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        effective_date_str = request.query_params.get('effective_date')
        
        # Base queryset
        taxes = Taxes.objects.filter(company=company)
        
        if effective_date_str:
            try:
                effective_date = date.fromisoformat(effective_date_str)
                taxes = taxes.filter(
                    applicable_from__lte=effective_date
                ).filter(
                    models.Q(applicable_to__isnull=True) | models.Q(applicable_to__gte=effective_date)
                )
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif active_only:
            taxes = taxes.filter(is_active=True)
        elif not show_history:
            # Default: show only current active taxes
            taxes = taxes.filter(is_active=True)

        serializer = TaxesSerializer(taxes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, company_id):
        """
        POST method that handles tax versioning automatically
        """
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response(
                {"detail": "Company not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TaxesSerializer(data=request.data)
        if serializer.is_valid():
            tax_type = serializer.validated_data['tax_type']
            applicable_from = serializer.validated_data.get('applicable_from', date.today())
            
            # Check if there's an existing active tax of the same type
            existing_tax = Taxes.objects.filter(
                company=company,
                tax_type=tax_type,
                is_active=True,
                applicable_to__isnull=True
            ).first()
            
            if existing_tax:
                # Close the existing tax period
                end_date = applicable_from - timedelta(days=1)
                existing_tax.close_tax_period(end_date)
                
                # Link the new tax to the old one
                new_tax = serializer.save(
                    company=company,
                    applicable_from=applicable_from,
                    superseded_by=None
                )
                existing_tax.superseded_by = new_tax
                existing_tax.save()
            else:
                # No existing tax, create new one normally
                new_tax = serializer.save(
                    company=company,
                    applicable_from=applicable_from
                )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, company_id, tax_id):
        """
        Enhanced PUT method - creates new version only if tax_percentage, applicable_from, or applicable_to changes,
        otherwise updates the existing record
        """
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response(
                {"detail": "Company not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            existing_tax = Taxes.objects.get(id=tax_id, company=company)
        except Taxes.DoesNotExist:
            return Response(
                {"detail": "Tax record not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate incoming data
        serializer = TaxesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        applicable_from = validated_data.get('applicable_from', date.today())
        if isinstance(applicable_from, str):
            applicable_from = date.fromisoformat(applicable_from)

        # Check if critical fields have changed
        critical_fields_changed = (
            validated_data.get('tax_percentage') != existing_tax.tax_percentage or
            validated_data.get('applicable_from') != existing_tax.applicable_from or
            validated_data.get('applicable_to') != existing_tax.applicable_to
        )

        if critical_fields_changed:
            # Create new version
            end_date = applicable_from - timedelta(days=1)
            existing_tax.close_tax_period(end_date)
            
            new_tax = serializer.save(
                company=company,
                applicable_from=applicable_from
            )
            
            # Link old tax to new one
            existing_tax.superseded_by = new_tax
            existing_tax.save()
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            # Update existing record (non-critical fields like tax_type, country, state)
            serializer = TaxesSerializer(existing_tax, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TaxCalculationHelper:
    """Helper class for tax calculations with historical support"""
    
    @staticmethod
    def calculate_tax(company, tax_type, amount, calculation_date=None):
        """Calculate tax amount for a specific date"""
        if calculation_date is None:
            calculation_date = date.today()
            
        tax_record = Taxes.get_active_tax(company, tax_type, calculation_date)
        if not tax_record:
            return 0, None
            
        tax_amount = (amount * tax_record.tax_percentage) / 100
        return tax_amount, tax_record
    
    @staticmethod
    def get_tax_changes(company, tax_type, from_date, to_date):
        """Get all tax changes for a period"""
        return Taxes.objects.filter(
            company=company,
            tax_type=tax_type,
            applicable_from__gte=from_date,
            applicable_from__lte=to_date
        ).order_by('applicable_from')