
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import *



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
            DocumentType.objects.create(Building=building, **doc_data)
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