from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from accounts.models import *


class Users(models.Model):   
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='user_comp', null=True, blank=True) 
    name = models.CharField(max_length=100,null=True, blank=True)
    username = models.CharField(max_length=100, unique=True,null=True, blank=True)
    email = models.EmailField(unique=True,null=True, blank=True)
    password = models.CharField(max_length=100,null=True, blank=True)
   
    company_logo = models.ImageField(upload_to='user_logo/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user_role = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=[
            ('Admin', 'Admin'),
            ('Sales', 'Sales') ,
            ('Store', 'Store') 
        ]
    )
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('blocked', 'Blocked'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    def set_password(self, raw_password):
        """Hash password before saving"""
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        """Check if a raw password matches the stored hashed password"""
        return check_password(raw_password, self.password)

    
    def __str__(self):
        return self.name

class MasterDocumentType(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='user_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='mas_type_comp', null=True, blank=True) 
    title = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title

class Building(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='buil_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='building_comp', null=True, blank=True) 
    building_name = models.CharField(max_length=100,null=True, blank=True)
    building_no = models.CharField(max_length=100,null=True, blank=True)
    plot_no = models.CharField(max_length=100,null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    land_mark = models.CharField(max_length=255,null=True, blank=True)    
    building_address = models.CharField(max_length=255,null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending','Pending'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    
    def __str__(self):
        return self.building_name
    
class DocumentType(models.Model):  
    Building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='build_comp', null=True, blank=True) 
    doc_type =  models.ForeignKey(MasterDocumentType, on_delete=models.CASCADE, related_name='ams_comp', null=True, blank=True) 
    number = models.CharField(max_length=100, null=True, blank=True)
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    upload_file = models.FileField(upload_to='document_files/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.Building.building_name


class UnitType(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='unit_type_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='unit_type_comp', null=True, blank=True) 
    title = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title

class Units(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='uni_comp', null=True, blank=True)    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='unit_comp', null=True, blank=True) 
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='unit_building', null=True, blank=True) 
    address = models.CharField(max_length=255,null=True, blank=True)    
    unit_name = models.CharField(max_length=100,null=True, blank=True)    
    unit_type = models.ForeignKey(UnitType, on_delete=models.CASCADE, related_name='unit_typ_comp', null=True, blank=True) 
    description = models.TextField(blank=True, null=True) 
    remarks = models.TextField(blank=True, null=True)
    no_of_bedrooms = models.IntegerField(null=True, blank=True)
    no_of_bathrooms = models.IntegerField(null=True, blank=True)
    premise_no = models.CharField(max_length=100,null=True, blank=True)   
    STATUS_CHOICES = [
        ('inactive', 'inactive'),
        ('pending', 'pending'),
    ]
    unit_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.unit_name
    
class UnitDocumentType(models.Model):    
    unit = models.ForeignKey(Units, on_delete=models.CASCADE, related_name='unit_comp', null=True, blank=True) 
    doc_type = models.ForeignKey(MasterDocumentType, on_delete=models.CASCADE, related_name='ams_doc_comp', null=True, blank=True)
    number = models.CharField(max_length=100, null=True, blank=True)
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    upload_file = models.FileField(upload_to='document_files/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.unit.unit_name
    


class IDType(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='id_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='id_comp', null=True, blank=True) 
    title = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    
class Currency(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='id_type_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='currency_comp', null=True, blank=True) 
    country = models.CharField(max_length=100, null=True, blank=True)
    currency = models.CharField(max_length=100, null=True, blank=True)
    currency_code= models.CharField(max_length=100, null=True, blank=True)
    minor_unit = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.country
    
    
class Tenant(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='tene_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tenant_comp', null=True, blank=True) 
    tenant_name = models.CharField(max_length=100,null=True, blank=True)
    nationality = models.CharField(max_length=100,null=True, blank=True)
    phone = models.CharField(max_length=15,null=True, blank=True)  
    alternative_phone = models.CharField(max_length=15,null=True, blank=True)  
    email = models.EmailField(unique=True,null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    address = models.CharField(max_length=255,null=True, blank=True)
    tenant_type = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=[
            ('Individual', 'Individual'),
            ('Organization', 'Organization') 
        ]
    )
    license_no = models.CharField(max_length=100,null=True, blank=True)
    id_type = models.ForeignKey(IDType, on_delete=models.CASCADE, related_name='id_comp', null=True, blank=True)
    id_number = models.CharField(max_length=100,null=True, blank=True)
    id_validity_date = models.DateField(null=True, blank=True)
    sponser_name = models.CharField(max_length=100,null=True, blank=True)
    sponser_id_type = models.ForeignKey(IDType, on_delete=models.CASCADE, related_name='sponser_id_comp', null=True, blank=True)
    sponser_id_number = models.CharField(max_length=100,null=True, blank=True)
    sponser_id_validity_date = models.DateField(null=True, blank=True)
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    remarks = models.TextField(blank=True, null=True)   
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.tenant_name if self.tenant_name else "Untitled Tenant"
    
    
class TenantDocumentType(models.Model):   
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='tenant_comp', null=True, blank=True) 
    doc_type =  models.ForeignKey(MasterDocumentType, on_delete=models.CASCADE, related_name='tenant_comp', null=True, blank=True) 
    number = models.CharField(max_length=100, null=True, blank=True)
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    upload_file = models.FileField(upload_to='document_files/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.tenant.tenant_name if self.tenant.tenant_name else "Untitled Tenant"


class ChargeCode(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='charge_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='charge_comp', null=True, blank=True) 
    title = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    
class Charges(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='ch_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='charges_comp', null=True, blank=True) 
    name = models.CharField(max_length=100, null=True, blank=True)
    charge_code = models.ForeignKey(ChargeCode, on_delete=models.CASCADE, related_name='charge_code_comp', null=True, blank=True) 
    vat_percentage = models.FloatField(null=True, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name if self.name else "Untitled Unit"
    


    