
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import *
from decimal import Decimal
from datetime import datetime, timedelta
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

    class Meta:
        model = Building
        fields = '__all__'  

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
 
        documents_data = validated_data.pop('unit_comp', None)
 
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

     
        if documents_data is not None:
            existing_docs = {doc.id: doc for doc in instance.unit_comp.all()}
            updated_ids = []

            for doc_data in documents_data:
                doc_id = doc_data.get('id', None)
                if doc_id and doc_id in existing_docs:
            
                    doc_instance = existing_docs[doc_id]
                    for attr, value in doc_data.items():
                        setattr(doc_instance, attr, value)
                    doc_instance.save()
                    updated_ids.append(doc_id)
                else:
       
                    UnitDocumentType.objects.create(unit=instance, **doc_data)
 
            for doc_id in existing_docs:
                if doc_id not in updated_ids:
                    existing_docs[doc_id].delete()

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
    class Meta:
        model = TenantDocumentType
        fields = '__all__'  


class TenantGetSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    id_type = IDTypeSerializer( required=False)
    sponser_id_type = IDTypeSerializer( required=False)
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
        building = Tenant.objects.create(**validated_data)
        for doc_data in documents_data:
            TenantDocumentType.objects.create(tenant=building, **doc_data)
        return building
    def update(self, instance, validated_data):
        documents_data = validated_data.pop('tenant_comp', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()


        instance.tenant_comp.all().delete()
        for doc_data in documents_data:
            TenantDocumentType.objects.create(tenant=instance, **doc_data)

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
        
        
        
 

 

class PaymentScheduleSerializer(serializers.ModelSerializer):
    charge_type_name = serializers.CharField(source='charge_type.name', read_only=True)

    class Meta:
        model = PaymentSchedule
        fields = '__all__'


class AdditionalChargeSerializer(serializers.ModelSerializer):
    charge_type_name = serializers.CharField(source='charge_type.name', read_only=True)

    class Meta:
        model = AdditionalCharge
        fields = '__all__'


class TenancyCreateSerializer(serializers.ModelSerializer):
    additional_charges = AdditionalChargeSerializer(many=True, required=False)
    payment_schedules = PaymentScheduleSerializer(many=True, read_only=True)

    class Meta:
        model = Tenancy
        fields = '__all__'

    def validate(self, data):
        # ... keep your validation as is ...
        return data

    @transaction.atomic
    def create(self, validated_data):
        additional_charges_data = self.initial_data.get('additional_charges', [])
        validated_data.pop('additional_charges', None)

        tenancy = super().create(validated_data)

        # Create payment schedules WITHOUT additional charges here
        self._create_payment_schedules(tenancy)

        # Create additional charges separately
        for charge_data in additional_charges_data:
            charge_type = Charges.objects.get(id=charge_data['charge_type'])
            AdditionalCharge.objects.create(
                tenancy=tenancy,
                charge_type=charge_type,
                amount=charge_data['amount'],
                reason=charge_data['reason'],
                due_date=charge_data['due_date']
            )
        return tenancy

    def _create_payment_schedules(self, tenancy):
        from decimal import Decimal
        from datetime import timedelta

        payment_schedules = []

        rent_charge = Charges.objects.get(name='Rent')
        deposit_charge = Charges.objects.filter(name='Deposit').first()
        commission_charge = Charges.objects.filter(name='Commission').first()

        # Deposit schedule
        if tenancy.deposit and deposit_charge:
            vat_amount = Decimal('0.00')
            if deposit_charge.vat_percentage:
                vat_amount = (tenancy.deposit * Decimal(str(deposit_charge.vat_percentage))) / Decimal('100')

            payment_schedules.append(PaymentSchedule(
                tenancy=tenancy,
                charge_type=deposit_charge,
                reason='Deposit',
                due_date=tenancy.start_date,
                status='pending',
                amount=tenancy.deposit,
                vat=vat_amount
            ))

        # Commission schedule
        if tenancy.commision and commission_charge:
            vat_amount = Decimal('0.00')
            if commission_charge.vat_percentage:
                vat_amount = (tenancy.commision * Decimal(str(commission_charge.vat_percentage))) / Decimal('100')

            payment_schedules.append(PaymentSchedule(
                tenancy=tenancy,
                charge_type=commission_charge,
                reason='Commission',
                due_date=tenancy.start_date,
                status='pending',
                amount=tenancy.commision,
                vat=vat_amount
            ))

        # Rent schedules
        if tenancy.rent_per_frequency and tenancy.no_payments:
            rent_vat = Decimal('0.00')
            if rent_charge.vat_percentage:
                rent_vat = (tenancy.rent_per_frequency * Decimal(str(rent_charge.vat_percentage))) / Decimal('100')

            for i in range(tenancy.no_payments):
                due_date = tenancy.first_rent_due_on + timedelta(days=30 * i)
                payment_schedules.append(PaymentSchedule(
                    tenancy=tenancy,
                    charge_type=rent_charge,
                    reason='Monthly Rent',
                    due_date=due_date,
                    status='pending',
                    amount=tenancy.rent_per_frequency,
                    vat=rent_vat
                ))

        # <-- REMOVE additional charges payment schedules here! -->

        PaymentSchedule.objects.bulk_create(payment_schedules)

    @transaction.atomic
    def update(self, instance, validated_data):
        additional_charges_data = self.initial_data.get('additional_charges', None)  

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

   
        if additional_charges_data is not None:
            
            PaymentSchedule.objects.filter(tenancy=instance).delete()

  
            AdditionalCharge.objects.filter(tenancy=instance).delete()
            for charge_data in additional_charges_data:
                charge_type = Charges.objects.get(id=charge_data['charge_type'])
                AdditionalCharge.objects.create(
                    tenancy=instance,
                    charge_type=charge_type,
                    amount=charge_data['amount'],
                    reason=charge_data['reason'],
                    due_date=charge_data['due_date']
                )

      
            self._create_payment_schedules(instance, additional_charges_data)

        return instance



class TenancyDetailSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    building_name = serializers.CharField(source='building.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    payment_schedules = PaymentScheduleSerializer(many=True, read_only=True)
    additional_charges = AdditionalChargeSerializer(many=True, read_only=True)
    class Meta:
        model = Tenancy
        fields = '__all__'
        
        
        
class TenancyListSerializer(serializers.ModelSerializer):
    tenant = TenantSerializer()
    company_name = serializers.CharField(source='company.name', read_only=True)
    building = BuildingSerializer()
    unit = UnitGetSerializer()
    payment_schedules = PaymentScheduleSerializer(many=True, read_only=True) 
    additional_charges = AdditionalChargeSerializer(many=True, read_only=True)

    class Meta:
        model = Tenancy
        fields = '__all__'




 

    
