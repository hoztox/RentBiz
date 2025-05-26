
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
        documents_data = validated_data.pop('build_comp', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()


        instance.build_comp.all().delete()
        for doc_data in documents_data:
            DocumentType.objects.create(Building=instance, **doc_data)

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
        documents_data = validated_data.pop('unit_comp', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
 
        instance.unit_comp.all().delete()
        for doc_data in documents_data:
            UnitDocumentType.objects.create(unit=instance, **doc_data)

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
    charge_code = ChargeCodeSerializer(required=False)
    class Meta:
        model = Charges
        fields = '__all__'
        
        
        
 

class AdditionalChargeSerializer(serializers.Serializer):
    charge_type = serializers.PrimaryKeyRelatedField(queryset=Charges.objects.all())
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(max_length=255, allow_blank=True)
    due_date = serializers.DateField()

class TenancyCreateSerializer(serializers.ModelSerializer):
    additional_charges = AdditionalChargeSerializer(many=True, required=False)

    class Meta:
        model = Tenancy
        fields = '__all__'

    def validate(self, data):
        """Validate the tenancy data"""
        if data.get('rent_per_frequency') and not data.get('no_payments'):
            raise serializers.ValidationError("Number of payments is required when rent frequency is provided")
        
        if data.get('no_payments') and not data.get('rent_per_frequency'):
            raise serializers.ValidationError("Rent per frequency is required when number of payments is provided")
        
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] >= data['end_date']:
                raise serializers.ValidationError("End date must be after start date")

        # Validate additional charges
        additional_charges = data.get('additional_charges', [])
        for charge in additional_charges:
            if charge['amount'] <= 0:
                raise serializers.ValidationError("Additional charge amount must be greater than 0")
            if not charge.get('reason'):
                raise serializers.ValidationError("Reason is required for additional charges")
            if not charge.get('due_date'):
                raise serializers.ValidationError("Due date is required for additional charges")

        return data

    @transaction.atomic
    def create(self, validated_data):
        """Create tenancy and generate payment schedules"""
        # Extract additional charges data
        additional_charges_data = validated_data.pop('additional_charges', [])
        
        # Create the tenancy
        tenancy = super().create(validated_data)
        
        # Generate payment schedules
        self._create_payment_schedules(tenancy, additional_charges_data)
        
        return tenancy
    
    def _create_payment_schedules(self, tenancy, additional_charges_data):
        """Create payment schedules based on tenancy data and additional charges"""
        payment_schedules = []
        
        # Get existing charge types (don't create new ones)
        try:
            rent_charge = Charges.objects.get(name='Rent')
        except Charges.DoesNotExist:
            raise serializers.ValidationError("Rent charge type not found. Please create it first.")
        
        try:
            deposit_charge = Charges.objects.get(name='Deposit')
        except Charges.DoesNotExist:
            deposit_charge = None
        
        try:
            commission_charge = Charges.objects.get(name='Commission')
        except Charges.DoesNotExist:
            commission_charge = None
        
        # Create deposit payment schedule if deposit exists and deposit charge exists
        if tenancy.deposit and tenancy.deposit > 0 and deposit_charge:
            vat_amount = Decimal('0.00')
            if deposit_charge.vat_percentage:
                vat_amount = (tenancy.deposit * Decimal(str(deposit_charge.vat_percentage))) / Decimal('100')
            
            deposit_schedule = PaymentSchedule(
                tenancy=tenancy,
                charge_type=deposit_charge,
                reason='Deposit',
                due_date=tenancy.start_date or tenancy.first_rent_due_on,
                status='pending',
                amount=tenancy.deposit,
                vat=vat_amount
            )
            payment_schedules.append(deposit_schedule)
        
        # Create commission payment schedule if commission exists and commission charge exists
        if tenancy.commision and tenancy.commision > 0 and commission_charge:
            vat_amount = Decimal('0.00')
            if commission_charge.vat_percentage:
                vat_amount = (tenancy.commision * Decimal(str(commission_charge.vat_percentage))) / Decimal('100')
            
            commission_schedule = PaymentSchedule(
                tenancy=tenancy,
                charge_type=commission_charge,
                reason='Commission',
                due_date=tenancy.start_date or tenancy.first_rent_due_on,
                status='pending',
                amount=tenancy.commision,
                vat=vat_amount
            )
            payment_schedules.append(commission_schedule)
        
        # Create monthly rent payment schedules
        if tenancy.rent_per_frequency and tenancy.no_payments:
            base_due_date = tenancy.first_rent_due_on or tenancy.start_date
            rent_vat_amount = Decimal('0.00')
            if rent_charge.vat_percentage:
                rent_vat_amount = (tenancy.rent_per_frequency * Decimal(str(rent_charge.vat_percentage))) / Decimal('100')
            
            for i in range(tenancy.no_payments):
                due_date = base_due_date + timedelta(days=30 * i)
                rent_schedule = PaymentSchedule(
                    tenancy=tenancy,
                    charge_type=rent_charge,
                    reason='Monthly Rent',
                    due_date=due_date,
                    status='pending',
                    amount=tenancy.rent_per_frequency,
                    vat=rent_vat_amount
                )
                payment_schedules.append(rent_schedule)
        
        # Create payment schedules for additional charges
        for charge_data in additional_charges_data:
            charge_type = charge_data['charge_type']
            vat_amount = Decimal('0.00')
            if charge_type.vat_percentage:
                vat_amount = (charge_data['amount'] * Decimal(str(charge_type.vat_percentage))) / Decimal('100')
            
            additional_schedule = PaymentSchedule(
                tenancy=tenancy,
                charge_type=charge_type,
                reason=charge_data['reason'],
                due_date=charge_data['due_date'],
                status='pending',
                amount=charge_data['amount'],
                vat=vat_amount
            )
            payment_schedules.append(additional_schedule)
        
 
        PaymentSchedule.objects.bulk_create(payment_schedules)
    @transaction.atomic
    def update(self, instance, validated_data):
        
            additional_charges_data = validated_data.pop('additional_charges', [])

        
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

        
            PaymentSchedule.objects.filter(tenancy=instance).delete()

    
            self._create_payment_schedules(instance, additional_charges_data)

            return instance

class PaymentScheduleSerializer(serializers.ModelSerializer):
    charge_type_name = serializers.CharField(source='charge_type.name', read_only=True)
    
    class Meta:
        model = PaymentSchedule
        fields = '__all__'


class TenancyDetailSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    building_name = serializers.CharField(source='building.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    payment_schedules = PaymentScheduleSerializer(source='tenanc', many=True, read_only=True)
    
    class Meta:
        model = Tenancy
        fields = '__all__'
        
        
        
class TenancyListSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    payment_schedules = PaymentScheduleSerializer(many=True, read_only=True, source='tenanc')  
 

    class Meta:
        model = Tenancy
        fields = [
            'id',
            'tenant_name',
            'company_name',
            'building',
            'unit',
            'rental_months',
            'start_date',
            'end_date',
            'no_payments',
            'first_rent_due_on',
            'rent_per_frequency',
            'total_rent_receivable',
            'deposit',
            'commision',
            'remarks',
            'payment_schedules',   
        ]


 


 

    
