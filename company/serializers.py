
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import *
from decimal import Decimal
from datetime import datetime, timedelta,date
from django.db import transaction

class UserSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)    
    company_id = serializers.IntegerField(write_only=True, required=True)
   
    

    class Meta:
        model = Users
        fields = '__all__'  

    def validate(self, data):
        
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError({"password": "Passwords do not match."})
   

        email = data.get('email')
        username = data.get('username')

        
        if Users.objects.filter(email=email).exists() or Company.objects.filter(email_address=email).exists():
            raise serializers.ValidationError({"email": "This email is already in use."})

         
        if Users.objects.filter(username=username).exists() or Company.objects.filter(user_id=username).exists():
            raise serializers.ValidationError({"username": "This username is already in use."})

       
        data['password'] = make_password(data['password'])

        
        data.pop('confirm_password', None)
         

        return data

    def create(self, validated_data):
        company_id = validated_data.pop('company_id')
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise serializers.ValidationError({"company_id": "Company does not exist."})

        validated_data['company'] = company
        user = Users.objects.create(**validated_data)
        return user
    
class UserUpdateSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True, required=False)
    company_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Users
        fields = '__all__'  

    def validate(self, data):
        
        if data.get('password') and data.get('confirm_password') and data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError({"password": "Passwords do not match."})

      
        user = self.instance

        email = data.get('email')
        username = data.get('username')

      
        if email and Users.objects.filter(email=email).exclude(id=user.id).exists():
            raise serializers.ValidationError({"email": "This email is already in use."})

        
        if username and Users.objects.filter(username=username).exclude(id=user.id).exists():
            raise serializers.ValidationError({"username": "This username is already in use."})

        
        if data.get('password'):
            data['password'] = make_password(data['password'])

       
        data.pop('confirm_password', None)

        return data

    def update(self, instance, validated_data):
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = '__all__'  
        
class BuildingSerializer(serializers.ModelSerializer):
    build_comp = DocumentTypeSerializer(many=True, required=False) 
    unit_count = serializers.SerializerMethodField()

    class Meta:
        model = Building
        fields = '__all__'  


    def get_unit_count(self, obj):
        return obj.unit_building.count()


    def create(self, validated_data):
        documents_data = validated_data.pop('build_comp', [])
        building = Building.objects.create(**validated_data)
        for doc_data in documents_data:
            DocumentType.objects.create(building=building, **doc_data)
        return building

    def update(self, instance, validated_data):
        documents_data = validated_data.pop('build_comp', None)

        # Update building fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if documents_data is not None:
            existing_ids = []
            for doc_data in documents_data:
                doc_id = doc_data.get('id', None)
                if doc_id:
                    try:
                        doc_instance = instance.build_comp.get(id=doc_id)
                        for attr, value in doc_data.items():
                            if attr != 'id':
                                setattr(doc_instance, attr, value)
                        doc_instance.save()
                        existing_ids.append(doc_instance.id)
                    except DocumentType.DoesNotExist:
                
                        doc_data.pop('id', None)
                        new_doc = DocumentType.objects.create(building=instance, **doc_data)
                        existing_ids.append(new_doc.id)
                else:
                    new_doc = DocumentType.objects.create(building=instance, **doc_data)
                    existing_ids.append(new_doc.id)

        
            instance.build_comp.exclude(id__in=existing_ids).delete()

        return instance


     
    
    
class UnitTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitType
        fields = '__all__'
           
    
class UnitDocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitDocumentType
        fields = '__all__'

class UnitGetSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    unit_comp = UnitDocumentTypeSerializer(many=True, required=False)
    unit_type = UnitTypeSerializer(required=False)
    building = BuildingSerializer()
    class Meta:
        model = Units
        fields = '__all__'

class UnitSerializer(serializers.ModelSerializer):
    unit_comp = UnitDocumentTypeSerializer(many=True, required=False)

    class Meta:
        model = Units
        fields = '__all__'

    def create(self, validated_data):
        documents_data = validated_data.pop('unit_comp', [])
        unit = Units.objects.create(**validated_data)
        for doc_data in documents_data:
            UnitDocumentType.objects.create(unit=unit, **doc_data)
        return unit
        
    def update(self, instance, validated_data):
        print(f"Serializer update called with validated_data: {validated_data}")
        
        documents_data = validated_data.pop('unit_comp', None)
        print(f"Documents data extracted: {documents_data}")

        # Update main unit fields
        for attr, value in validated_data.items():
            print(f"Setting {attr} = {value}")
            setattr(instance, attr, value)
        instance.save()
        print("Main unit instance saved")

        if documents_data is not None:
            existing_docs = {doc.id: doc for doc in instance.unit_comp.all()}
            print(f"Existing documents: {list(existing_docs.keys())}")
            updated_ids = []

            for doc_data in documents_data:
                print(f"Processing document data: {doc_data}")
                doc_id = doc_data.get('id')
                
                if doc_id and doc_id in existing_docs:
                    doc_instance = existing_docs[doc_id]
                    print(f"Updating existing document {doc_id}")
                    
                    for attr, value in doc_data.items():
                        if attr == 'upload_file':
                            if value and hasattr(value, 'read'):
                                print(f"Setting file {value.name} on document {doc_id}")
                                setattr(doc_instance, attr, value)
                            else:
                                print(f"No valid file found for document {doc_id}, value: {value}")
                        else:
                            setattr(doc_instance, attr, value)
                    
                    doc_instance.save()
                    print(f"Document {doc_id} saved with file: {doc_instance.upload_file}")
                    updated_ids.append(doc_id)
                else:
                    print(f"Creating new document with data: {doc_data}")
                    new_doc = UnitDocumentType.objects.create(unit=instance, **doc_data)
                    print(f"New document created with ID: {new_doc.id}, file: {new_doc.upload_file}")

            # Delete documents not in the update
            for doc_id in existing_docs:
                if doc_id not in updated_ids:
                    print(f"Deleting document {doc_id}")
                    existing_docs[doc_id].delete()

        print("Serializer update completed")
        return instance

    

class MasterDocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterDocumentType
        fields = '__all__'
        
        
class IDTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IDType
        fields = '__all__'
        
        
class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = '__all__'
 

class TenantDocumentTypeSerializer(serializers.ModelSerializer):
    doc_type = serializers.PrimaryKeyRelatedField(queryset=MasterDocumentType.objects.all(), required=True)
    number = serializers.CharField(allow_blank=True, required=False)
    issued_date = serializers.DateField(allow_null=True, required=False)
    expiry_date = serializers.DateField(allow_null=True, required=False)
    upload_file = serializers.FileField(allow_null=True, required=False)
    

    existing_file_url = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = TenantDocumentType
        fields = [
            'id',
            'doc_type',
            'number',
            'issued_date',
            'expiry_date',
            'upload_file',
            'existing_file_url',  # ✅ Include this field in Meta.fields
        ]


class TenantGetSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    id_type = IDTypeSerializer()
    sponser_id_type = IDTypeSerializer()
    tenant_comp = TenantDocumentTypeSerializer(many=True, required=False) 
    
    class Meta:
        model = Tenant
        fields = '__all__'  
 

class TenantSerializer(serializers.ModelSerializer):
    tenant_comp = TenantDocumentTypeSerializer(many=True, required=False)

    class Meta:
        model = Tenant
        fields = '__all__'

    def create(self, validated_data):
        documents_data = validated_data.pop('tenant_comp', [])
        tenant = Tenant.objects.create(**validated_data)
        for doc_data in documents_data:
            existing_file_url = doc_data.pop('existing_file_url', None)
            if existing_file_url and not doc_data.get('upload_file'):
                doc_data['upload_file'] = existing_file_url
            TenantDocumentType.objects.create(tenant=tenant, **doc_data)
        return tenant

    def update(self, instance, validated_data):
        documents_data = validated_data.pop('tenant_comp', None)

        # Update tenant fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if documents_data is not None:
            existing_docs = {doc.id: doc for doc in instance.tenant_comp.all()}
            processed_doc_ids = []

            for doc_data in documents_data:
                doc_id = doc_data.get('id')
                existing_file_url = doc_data.pop('existing_file_url', None)

                if doc_id and doc_id in existing_docs:
                    doc_instance = existing_docs[doc_id]

                    for attr, value in doc_data.items():
                        if attr != 'id':
                            if attr == 'upload_file':
                                # If no new file uploaded, but existing file URL is provided
                                if not value and existing_file_url:
                                    # ✅ Normalize path to avoid media/media issue
                                    cleaned_path = existing_file_url
                                    if cleaned_path.startswith('/media/'):
                                        cleaned_path = cleaned_path[len('/media/'):]
                                    elif cleaned_path.startswith('media/'):
                                        cleaned_path = cleaned_path[len('media/'):]
                                    doc_instance.upload_file.name = cleaned_path
                                    continue  # Skip normal set
                            setattr(doc_instance, attr, value)

                    doc_instance.save()
                    processed_doc_ids.append(doc_id)
                else:
                    # Create new document
                    doc_data_copy = doc_data.copy()
                    doc_data_copy.pop('id', None)
                    if existing_file_url and not doc_data_copy.get('upload_file'):
                        cleaned_path = existing_file_url
                        if cleaned_path.startswith('/media/'):
                            cleaned_path = cleaned_path[len('/media/'):]
                        elif cleaned_path.startswith('media/'):
                            cleaned_path = cleaned_path[len('media/'):]
                        doc_data_copy['upload_file'] = cleaned_path
                    new_doc = TenantDocumentType.objects.create(tenant=instance, **doc_data_copy)
                    processed_doc_ids.append(new_doc.id)

            # Delete unprocessed documents
            for doc_id, doc_instance in existing_docs.items():
                if doc_id not in processed_doc_ids:
                    doc_instance.delete()

        return instance


class ChargeCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChargeCode
        fields = '__all__'
        
        
class ChargesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Charges
        fields = '__all__'
        
        
class ChargesGetSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    charge_code = ChargeCodeSerializer()
    class Meta:
        model = Charges
        fields = '__all__'


class AdditionalChargeSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    charge_type = serializers.IntegerField()
    charge_type_name = serializers.CharField(read_only=True)
    reason = serializers.CharField(max_length=255)
    due_date = serializers.DateField()
    status = serializers.CharField(read_only=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    tax = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    tax_details = serializers.ListField(child=serializers.DictField(), read_only=True)

    def validate(self, data):
        try:
            charge_type_id = data.get('charge_type')
            amount = data.get('amount')
            due_date = data.get('due_date')
            reason = data.get('reason')

            if not charge_type_id:
                raise serializers.ValidationError("Charge type is required.")
            if not reason:
                raise serializers.ValidationError("Reason is required.")
            if not due_date:
                raise serializers.ValidationError("Due date is required.")
            if not amount or amount < 0:
                raise serializers.ValidationError("Amount is required and must be non-negative.")

            charge_type = Charges.objects.filter(id=charge_type_id).first()
            if not charge_type:
                raise serializers.ValidationError(f"Charge type with id {charge_type_id} not found.")

            # Set charge_type_name
            data['charge_type_name'] = charge_type.name

            # Calculate taxes
            tax_amount = Decimal('0.00')
            tax_details = []
            reference_date = due_date if isinstance(due_date, date) else datetime.strptime(due_date, '%Y-%m-%d').date()
            taxes = charge_type.taxes.filter(
                company=charge_type.company,
                is_active=True,
                applicable_from__lte=reference_date,
                applicable_to__gte=reference_date
            ) | charge_type.taxes.filter(
                company=charge_type.company,
                is_active=True,
                applicable_from__lte=reference_date,
                applicable_to__isnull=True
            )
            for tax in taxes:
                tax_percentage = Decimal(str(tax.tax_percentage))
                tax_contribution = (Decimal(str(amount)) * tax_percentage) / Decimal('100')
                tax_amount += tax_contribution
                tax_details.append({
                    'tax_type': tax.tax_type,
                    'tax_percentage': tax_percentage,
                    'tax_amount': tax_contribution.quantize(Decimal('0.01'))
                })

            data['tax'] = tax_amount.quantize(Decimal('0.01'))
            data['total'] = (Decimal(str(amount)) + tax_amount).quantize(Decimal('0.01'))
            data['tax_details'] = tax_details

            return data

        except Exception as e:
            raise serializers.ValidationError(f"Validation error: {str(e)}")

    def to_representation(self, instance):
        if isinstance(instance, dict):
            # Handle dictionary input for preview
            return {
                'id': instance.get('id'),
                'charge_type': instance.get('charge_type'),
                'charge_type_name': instance.get('charge_type_name'),
                'reason': instance.get('reason'),
                'due_date': instance.get('due_date'),
                'status': instance.get('status'),
                'amount': instance.get('amount'),
                'tax': instance.get('tax'),
                'total': instance.get('total'),
                'tax_details': instance.get('tax_details')
            }
        return super().to_representation(instance)


class PaymentSchedulePreviewSerializer(serializers.Serializer):
    id = serializers.CharField()
    charge_type = serializers.IntegerField(source='charge_type.id', allow_null=True)
    charge_type_name = serializers.CharField()
    reason = serializers.CharField()
    due_date = serializers.DateField(format='%Y-%m-%d')
    status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax = serializers.DecimalField(max_digits=10, decimal_places=2)
    total = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax_details = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()  # Allows for tax_type, tax_percentage, tax_amount
        )
    )


class PaymentScheduleSerializer(serializers.ModelSerializer):
    charge_type_name = serializers.CharField(source='charge_type.name', read_only=True)
    tax_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PaymentSchedule
        fields = ['id', 'charge_type', 'charge_type_name', 'reason', 'due_date', 'status', 'amount', 'tax', 'total', 'tax_details']
        extra_kwargs = {
            'tenancy': {'required': False, 'allow_null': True},
            'charge_type': {'required': False, 'allow_null': True},
            'reason': {'required': False, 'allow_null': True},
            'due_date': {'required': False, 'allow_null': True},
            'amount': {'required': False, 'allow_null': True},
            'tax': {'required': False, 'allow_null': True},
            'total': {'required': False, 'allow_null': True},
            'status': {'read_only': True},
        }

    def get_tax_details(self, obj):
        if isinstance(obj, dict):
            return obj.get('tax_details', [])
        return obj.tax_details if hasattr(obj, 'tax_details') else []



class TenancyCreateSerializer(serializers.ModelSerializer):
    additional_charges = AdditionalChargeSerializer(many=True, required=False)
    payment_schedules = PaymentScheduleSerializer(many=True, read_only=True)

    class Meta:
        model = Tenancy
        fields = '__all__'

    def validate(self, data):
        required_fields = [
            'tenant', 'building', 'unit', 'rental_months', 'start_date',
            'no_payments', 'first_rent_due_on', 'remarks'
        ]
        for field in required_fields:
            if field not in data or not data[field]:
                raise serializers.ValidationError(f"{field.replace('_', ' ')} is required.")
        return data

    @transaction.atomic
    def create(self, validated_data):
        additional_charges_data = validated_data.pop('additional_charges', [])
        tenancy = super().create(validated_data)

        for charge_data in additional_charges_data:
            charge_type_id = charge_data.get('charge_type')
            charge_type = Charges.objects.filter(id=charge_type_id).first()
            if not charge_type:
                raise serializers.ValidationError(f"Charge type with id {charge_type_id} not found.")
            
            amount = charge_data.get('amount')
            due_date = charge_data.get('due_date')
            reason = charge_data.get('reason')
            tax_amount = charge_data.get('tax', Decimal('0.00'))
            total = charge_data.get('total', Decimal(str(amount)) + tax_amount)

            AdditionalCharge.objects.create(
                tenancy=tenancy,
                charge_type=charge_type,
                reason=reason,
                due_date=due_date,
                status='pending',
                amount=amount,
                tax=tax_amount,
                total=total
            )

        self._create_payment_schedules(tenancy)
        return tenancy

    @transaction.atomic
    def update(self, instance, validated_data):
        # Pop additional_charges data to handle separately
        additional_charges_data = validated_data.pop('additional_charges', None)

        # Update tenancy fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Handle additional charges if provided
        if additional_charges_data is not None:
            # Delete existing additional charges
            AdditionalCharge.objects.filter(tenancy=instance).delete()

            # Create new additional charges
            for charge_data in additional_charges_data:
                charge_type_id = charge_data.get('charge_type')
                charge_type = Charges.objects.filter(id=charge_type_id).first()
                if not charge_type:
                    raise serializers.ValidationError(f"Charge type with id {charge_type_id} not found.")
                
                amount = charge_data.get('amount')
                due_date = charge_data.get('due_date')
                reason = charge_data.get('reason')
                tax_amount = charge_data.get('tax', Decimal('0.00'))
                total = charge_data.get('total', Decimal(str(amount)) + tax_amount)

                AdditionalCharge.objects.create(
                    tenancy=instance,
                    charge_type=charge_type,
                    reason=reason,
                    due_date=due_date,
                    status='pending',
                    amount=amount,
                    tax=tax_amount,
                    total=total
                )

        # Delete only pending payment schedules
        PaymentSchedule.objects.filter(tenancy=instance, status='pending').delete()
        # Regenerate payment schedules for pending items
        self._create_payment_schedules(instance)

        return instance

    def _create_payment_schedules(self, tenancy):
        payment_schedules = []

        rent_charge = Charges.objects.filter(name='Rent').first()
        deposit_charge = Charges.objects.filter(name='Deposit').first()
        commission_charge = Charges.objects.filter(name='Commission').first()

        if tenancy.deposit and deposit_charge:
            tax_amount, tax_details = self._calculate_tax(tenancy.deposit, deposit_charge, tenancy.start_date)
            total = tenancy.deposit + tax_amount
            payment_schedules.append(PaymentSchedule(
                tenancy=tenancy,
                charge_type=deposit_charge,
                reason='Deposit',
                due_date=tenancy.start_date,
                status='pending',
                amount=tenancy.deposit,
                tax=tax_amount,
                total=total
            ))

        if tenancy.commission and commission_charge:
            tax_amount, tax_details = self._calculate_tax(tenancy.commission, commission_charge, tenancy.start_date)
            total = tenancy.commission + tax_amount
            payment_schedules.append(PaymentSchedule(
                tenancy=tenancy,
                charge_type=commission_charge,
                reason='Commission',
                due_date=tenancy.start_date,
                status='pending',
                amount=tenancy.commission,
                tax=tax_amount,
                total=total
            ))

        if tenancy.rent_per_frequency and tenancy.no_payments and rent_charge:
            rent_tax, tax_details = self._calculate_tax(tenancy.rent_per_frequency, rent_charge, tenancy.first_rent_due_on)
            rental_months = tenancy.rental_months or 12
            payment_frequency_months = rental_months // tenancy.no_payments if tenancy.no_payments > 0 else 1

            reason_map = {
                1: 'Monthly Rent',
                2: 'Bi-Monthly Rent',
                3: 'Quarterly Rent',
                6: 'Semi-Annual Rent',
                12: 'Annual Rent'
            }
            reason = reason_map.get(payment_frequency_months, f'{payment_frequency_months}-Monthly Rent')

            for i in range(tenancy.no_payments):
                due_date = tenancy.first_rent_due_on
                if i > 0:
                    year = due_date.year
                    month = due_date.month + (i * payment_frequency_months)
                    while month > 12:
                        year += 1
                        month -= 12
                    due_date = due_date.replace(year=year, month=month)

                total = tenancy.rent_per_frequency + rent_tax
                payment_schedules.append(PaymentSchedule(
                    tenancy=tenancy,
                    charge_type=rent_charge,
                    reason=reason,
                    due_date=due_date,
                    status='pending',
                    amount=tenancy.rent_per_frequency,
                    tax=rent_tax,
                    total=total
                ))

        if payment_schedules:
            PaymentSchedule.objects.bulk_create(payment_schedules)

    def _calculate_tax(self, amount, charge, reference_date):
        tax_amount = Decimal('0.00')
        tax_details = []
        reference_date_obj = reference_date if isinstance(reference_date, date) else datetime.strptime(reference_date, '%Y-%m-%d').date()

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


class PaymentScheduleGetSerializer(serializers.ModelSerializer):
    charge_type = ChargesSerializer()

    class Meta:
        model = PaymentSchedule
        fields = '__all__'
        

class AdditionalChargeGetSerializer(serializers.ModelSerializer):
    charge_type = ChargesSerializer()


    class Meta:
        model = AdditionalCharge
        fields = '__all__'
         

class TenancyDetailSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    building_name = serializers.CharField(source='building.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    payment_schedules = PaymentScheduleGetSerializer(many=True, read_only=True)
    additional_charges = AdditionalChargeGetSerializer(many=True, read_only=True)
    class Meta:
        model = Tenancy
        fields = '__all__'
        
        
        
class TenancyListSerializer(serializers.ModelSerializer):
    tenant = TenantSerializer()
    company_name = serializers.CharField(source='company.name', read_only=True)
    building = BuildingSerializer()
    unit = UnitGetSerializer()
    payment_schedules = PaymentScheduleGetSerializer(many=True, read_only=True) 
    additional_charges = AdditionalChargeGetSerializer(many=True, read_only=True)

    class Meta:
        model = Tenancy
        fields = '__all__'


 

class TenancyRenewalSerializer(serializers.ModelSerializer):
    additional_charges = AdditionalChargeSerializer(many=True, required=False)
    
    class Meta:
        model = Tenancy
        fields = [
            'rental_months', 'start_date', 'end_date', 'no_payments', 
            'first_rent_due_on', 'rent_per_frequency', 'deposit', 
            'commision', 'remarks', 'additional_charges'
        ]
        extra_kwargs = {
            'rental_months': {'required': True},
            'start_date': {'required': True},
            'end_date': {'required': True},
            'no_payments': {'required': True},
            'first_rent_due_on': {'required': True},
            'rent_per_frequency': {'required': True},
        }

    def validate(self, data):
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] >= data['end_date']:
                raise serializers.ValidationError("End date must be after start date")
        return data

    @transaction.atomic
    def create(self, validated_data):
     
        original_tenancy_id = self.context.get('original_tenancy_id')
        original_tenancy = Tenancy.objects.get(id=original_tenancy_id)
        
 
        additional_charges_data = self.initial_data.get('additional_charges', [])
        validated_data.pop('additional_charges', None)
        
     
        renewed_tenancy = Tenancy.objects.create(
            user=original_tenancy.user,
            company=original_tenancy.company,
            tenant=original_tenancy.tenant,
            building=original_tenancy.building,
            unit=original_tenancy.unit,
            previous_tenancy=original_tenancy,
            is_reniew=True,
            status='pending',  
            **validated_data
        )
        
    
        original_tenancy.status = 'renewed'
        original_tenancy.is_close = True
        original_tenancy.save()
        
 
        self._create_payment_schedules(renewed_tenancy)
        
         
        for charge_data in additional_charges_data:
            try:
                charge_type = Charges.objects.filter(id=charge_data['charge_type']).first()
                if charge_type:
                    AdditionalCharge.objects.create(
                        tenancy=renewed_tenancy,
                        charge_type=charge_type,
                        amount=charge_data.get('amount'),
                        reason=charge_data.get('reason'),
                        due_date=charge_data.get('due_date'),
                        vat=charge_data.get('vat'),
                        total=charge_data.get('total'),
                    )
            except Exception as e:
                print(f"Error creating additional charge: {e}")
                continue
        
        return renewed_tenancy

    def _create_payment_schedules(self, tenancy):
        """Create payment schedules for the renewed tenancy"""

        payment_schedules = []

        rent_charge = Charges.objects.filter(name='Rent').first()
        deposit_charge = Charges.objects.filter(name='Deposit').first()
        commission_charge = Charges.objects.filter(name='Commission').first()

 
        if tenancy.deposit and deposit_charge:
            vat_amount = Decimal('0.00')
            if deposit_charge.vat_percentage:
                vat_amount = (tenancy.deposit * Decimal(str(deposit_charge.vat_percentage))) / Decimal('100')
            total = tenancy.deposit + vat_amount
            payment_schedules.append(PaymentSchedule(
                tenancy=tenancy,
                charge_type=deposit_charge,
                reason='Deposit',
                due_date=tenancy.start_date,
                status='pending',
                amount=tenancy.deposit,
                vat=vat_amount,
                total=total
            ))

 
        if tenancy.commision and commission_charge:
            vat_amount = Decimal('0.00')
            if commission_charge.vat_percentage:
                vat_amount = (tenancy.commision * Decimal(str(commission_charge.vat_percentage))) / Decimal('100')
            total = tenancy.commision + vat_amount
            payment_schedules.append(PaymentSchedule(
                tenancy=tenancy,
                charge_type=commission_charge,
                reason='Commission',
                due_date=tenancy.start_date,
                status='pending',
                amount=tenancy.commision,
                vat=vat_amount,
                total=total
            ))

      
        if tenancy.rent_per_frequency and tenancy.no_payments and rent_charge:
            rent_vat = Decimal('0.00')
            if rent_charge.vat_percentage:
                rent_vat = (tenancy.rent_per_frequency * Decimal(str(rent_charge.vat_percentage))) / Decimal('100')

            rental_months = tenancy.rental_months or 12
            payment_frequency_months = rental_months // tenancy.no_payments if tenancy.no_payments > 0 else 1

            for i in range(tenancy.no_payments):
                due_date = tenancy.first_rent_due_on
                if i > 0:
                    year = due_date.year
                    month = due_date.month + (i * payment_frequency_months)
                    while month > 12:
                        year += 1
                        month -= 12
                    due_date = due_date.replace(year=year, month=month)

                reason = f'{payment_frequency_months}-Monthly Rent'
                total = tenancy.rent_per_frequency + rent_vat
                payment_schedules.append(PaymentSchedule(
                    tenancy=tenancy,
                    charge_type=rent_charge,
                    reason=reason,
                    due_date=due_date,
                    status='pending',
                    amount=tenancy.rent_per_frequency,
                    vat=rent_vat,
                    total=total
                ))

        if payment_schedules:
            PaymentSchedule.objects.bulk_create(payment_schedules)


class TaxesSerializer(serializers.ModelSerializer):
    country_name = serializers.SerializerMethodField()
    state_name = serializers.SerializerMethodField()

    class Meta:
        model = Taxes
        fields = '__all__'
        extra_kwargs = {
            'is_active': {'required': False},
            'applicable_to': {'required': False, 'allow_null': True}
        }

    def get_country_name(self, obj):
        return obj.country.name if obj.country else None

    def get_state_name(self, obj):
        return obj.state.name if obj.state else None
