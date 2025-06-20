from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from accounts.models import *
from decimal import Decimal



    
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
        return self.name if self.name else "Unnamed User"

class Taxes(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='user_taxes', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='company_taxes', null=True, blank=True) 
    tax_type = models.CharField(max_length=100)  
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='taxes_c')
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='taxes_state', null=True, blank=True)
    applicable_from = models.DateField(null=True, blank=True)
    applicable_to = models.DateField(null=True, blank=True)
    
    # New fields for versioning
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Ensure uniqueness per company for active tax types
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'tax_type'],
                condition=models.Q(is_active=True, applicable_to__isnull=True),
                name='unique_active_tax_per_company'
            )
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tax_type} ({self.tax_percentage}%) - {self.applicable_from} to {self.applicable_to or 'Current'}"

    def close_tax_period(self, end_date=None):
        """Close the current tax period by setting applicable_to date"""
        if end_date is None:
            end_date = date.today()
        self.applicable_to = end_date
        self.is_active = False
        self.save()

    @classmethod
    def get_active_tax(cls, company, tax_type, effective_date=None):
        """Get the active tax rate for a specific date"""
        if effective_date is None:
            effective_date = date.today()
        
        return cls.objects.filter(
            company=company,
            tax_type=tax_type,
            applicable_from__lte=effective_date
        ).filter(
            models.Q(applicable_to__isnull=True) | models.Q(applicable_to__gte=effective_date)
        ).first()

    @classmethod
    def get_tax_history(cls, company, tax_type):
        """Get complete history of a tax type for a company"""
        return cls.objects.filter(
            company=company,
            tax_type=tax_type
        ).order_by('applicable_from')


class MasterDocumentType(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='user_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='mas_type_comp', null=True, blank=True) 
    title = models.CharField(max_length=100, null=True, blank=True)
    number = models.BooleanField(default=False)
    issue_date = models.BooleanField(default=False)
    expiry_date = models.BooleanField(default=False)
    upload_file =models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title if self.title else "Unnamed title"

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
    
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, related_name='buildings_country')
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True, related_name='buildings_state')

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive')
       
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    
    def __str__(self):
        return self.building_name if self.building_name else "Unnamed Building"
    
    def save(self, *args, **kwargs):
        if not self.code:
            last_building = Building.objects.filter(code__startswith='B24').order_by('-code').first()
            if last_building and last_building.code:
                last_num_str = last_building.code[1:]  
                last_num = int(last_num_str)
                new_num = last_num + 1
            else:
                new_num = 24090001   
            
            self.code = f"B{new_num:08d}"  
        
        super().save(*args, **kwargs)
        
    
class DocumentType(models.Model):  
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='build_comp', null=True, blank=True) 
    doc_type =  models.ForeignKey(MasterDocumentType, on_delete=models.CASCADE, related_name='ams_comp', null=True, blank=True) 
    number = models.CharField(max_length=100, null=True, blank=True)
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    upload_file = models.FileField(upload_to='document_files/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.building.building_name if self.building else "No Building"



class UnitType(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='unit_type_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='unit_type_comp', null=True, blank=True) 
    title = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title if self.title else "No title"

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
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)  
    STATUS_CHOICES = [
        ('occupied', 'Occupied'),
        ('renovation', 'Renovation'),
        ('vacant', 'Vacant'),
        ('disputed', 'Disputed'),
    ]
    unit_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            last_unit = Units.objects.filter(code__startswith='U24').order_by('-code').first()
            if last_unit and last_unit.code:
                last_num_str = last_unit.code[1:]   
                last_num = int(last_num_str)
                new_num = last_num + 1
            else:
                new_num = 24090001   
            
            self.code = f"U{new_num:08d}"  

        super().save(*args, **kwargs)
        
    def __str__(self):
        return self.unit_name if self.unit_name else "Untitled Unit"
    
class UnitDocumentType(models.Model):    
    unit = models.ForeignKey(Units, on_delete=models.CASCADE, related_name='unit_comp', null=True, blank=True) 
    doc_type = models.ForeignKey(MasterDocumentType, on_delete=models.CASCADE, related_name='ams_doc_comp', null=True, blank=True)
    number = models.CharField(max_length=100, null=True, blank=True)
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    upload_file = models.FileField(upload_to='document_files/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
      return self.unit.unit_name if self.unit and self.unit.unit_name else "Untitled Unit"


    
class IDType(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='id_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='id_comp', null=True, blank=True) 
    title = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title if self.title else "No title"
    
    
class Currency(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='id_type_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='currency_comp', null=True, blank=True) 
    country = models.CharField(max_length=100, null=True, blank=True)
    currency = models.CharField(max_length=100, null=True, blank=True)
    currency_code= models.CharField(max_length=100, null=True, blank=True)
    minor_unit = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.country if self.country else "No country"
    
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
    code = models.CharField(max_length=20, unique=True, blank=True, null=True) 
    
    
    def __str__(self):
        return self.tenant_name if self.tenant_name else "Untitled Tenant"
    
    def save(self, *args, **kwargs):
            if not self.code:
                last_tenant = Tenant.objects.filter(code__startswith='U24').order_by('-code').first()
                
                if last_tenant and last_tenant.code:
              
                    last_num_str = last_tenant.code[1:]  
                    last_num = int(last_num_str)
                    new_num = last_num + 1
                else:
                    new_num = 24090001  
                
                self.code = f"U{new_num:08d}"  
            
            super().save(*args, **kwargs)
        

    
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
        return self.title if self.title else "No title"
       
class Charges(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='ch_comp', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='charges_comp', null=True, blank=True) 
    name = models.CharField(max_length=100, null=True, blank=True)
    charge_code = models.ForeignKey(ChargeCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='charge_code_comp') 
    taxes = models.ManyToManyField(Taxes, related_name='charges_taxes',blank=True)
    vat_percentage = models.FloatField(null=True, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name if self.name else "Untitled Unit"
    

class Tenancy(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='tnnt', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tnn_comp', null=True, blank=True) 
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='tenancies', null=True, blank=True)
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='tenancies', null=True, blank=True)
    unit = models.ForeignKey(Units, on_delete=models.CASCADE, related_name='tenancies', null=True, blank=True)
    
    rental_months = models.PositiveIntegerField(null=True, blank=True, help_text="Duration in months")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    no_payments = models.IntegerField(null=True, blank=True)
    first_rent_due_on = models.DateField(null=True, blank=True)
    
    rent_per_frequency = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_rent_receivable = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    status_choices = [
        ('pending', 'Pending'),
        ('active', 'Active') ,
        ('terminated', 'Terminated'),
        ('closed', 'Closed') ,
        ('renewed', 'Renewed') 
    ]
    status = models.CharField(max_length=20, choices=status_choices, default='pending')
    
    deposit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    commission = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    
    is_termination = models.BooleanField(default=False)
    is_close = models.BooleanField(default=False)
    is_reniew = models.BooleanField(default=False)
    previous_tenancy = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='renewed_tenancies'
    )
    
    tenancy_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    def get_renewal_number(self):
        """Return how deep the renewal chain is (1 for first renewal, 2 for second, etc)."""
        renewal_number = 1
        current = self.previous_tenancy
        while current:
            if current.previous_tenancy:
                renewal_number += 1
            current = current.previous_tenancy
        return renewal_number


    def generate_tenancy_code(self):
        if self.previous_tenancy:
            # Go back to the original tenancy
            original = self.previous_tenancy
            while original.previous_tenancy:
                original = original.previous_tenancy

            base_code = original.tenancy_code

            # Count existing renewals of this base
            renewal_count = Tenancy.objects.filter(
                previous_tenancy__tenancy_code__startswith=base_code
            ).count()

            return f"{base_code}-{renewal_count + 1}"  # Start from 1
        else:
            # Generate a new base code like TC001
            existing_codes = Tenancy.objects.filter(
                tenancy_code__isnull=False,
                previous_tenancy__isnull=True
            )
            base_numbers = []

            for code in existing_codes.values_list('tenancy_code', flat=True):
                base_part = code.split('-')[0]
                try:
                    number = int(base_part.replace('TC', '').replace('#TC', ''))
                    base_numbers.append(number)
                except ValueError:
                    pass

            next_base_number = (max(base_numbers) + 1) if base_numbers else 1
            base_code = f"TC{next_base_number:03d}"
            return base_code




    def save(self, *args, **kwargs):
        
        if not self.tenancy_code:
            self.tenancy_code = self.generate_tenancy_code()

  
        if self.rent_per_frequency and self.no_payments:
            self.total_rent_receivable = self.rent_per_frequency * Decimal(self.no_payments)
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tenancy_code} | {self.tenant} - {self.unit}"



class PaymentSchedule(models.Model):
    tenancy = models.ForeignKey('Tenancy', on_delete=models.CASCADE, related_name='payment_schedules', null=True, blank=True)
    charge_type = models.ForeignKey('Charges', on_delete=models.CASCADE, related_name='char', null=True, blank=True)   
    reason = models.CharField(max_length=255, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)   
    status_choices = [
        ('pending', 'Pending'),
        ('paid', 'Paid') ,
        ('invoice', 'Invoice')
       
    ]
    status = models.CharField(max_length=20, choices=status_choices, default='pending')   
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # VAT will remove after testing
    vat = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        return f"{self.tenancy} - {self.charge_type} - Due: {self.due_date}"
    
 

class AdditionalCharge(models.Model):
    tenancy = models.ForeignKey(Tenancy, on_delete=models.CASCADE, related_name='additional_charges', null=True, blank=True)
    charge_type = models.ForeignKey(Charges, on_delete=models.CASCADE, related_name='chvcar', null=True, blank=True)   
    reason = models.CharField(max_length=255, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    in_date  = models.DateField(null=True, blank=True)
    status_choices = [
        ('pending', 'Pending'),
        ('paid', 'Paid') ,
        ('invoice', 'Invoice') 
    ]
    status = models.CharField(max_length=20, choices=status_choices, default='pending')   
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # VAT will remove after testing
    vat = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

   
    def __str__(self):
        return f"{self.tenancy} - {self.charge_type} - Due: {self.due_date}"



class Invoice(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='invoice_user', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='invoice_comp', null=True, blank=True)
    tenancy = models.ForeignKey(Tenancy, on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    invoice_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    in_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

  
    status_choices = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]
    status = models.CharField(max_length=20, choices=status_choices, default='unpaid')
    is_automated = models.BooleanField(default=False, help_text="Indicates if this invoice was generated automatically")

    payment_schedules = models.ManyToManyField(PaymentSchedule, blank=True, related_name='invoices')
    additional_charges = models.ManyToManyField(AdditionalCharge, blank=True, related_name='invoices')

    def __str__(self):
        return f"Invoice {self.invoice_number} for {self.tenancy}"


class InvoiceAutomationConfig(models.Model):
    tenancy = models.ForeignKey('Tenancy', on_delete=models.CASCADE, related_name='invoice_configs')
    days_before_due = models.PositiveIntegerField(
        default=7,
        help_text="Number of days before due date to generate and send invoice"
    )
    combine_charges = models.BooleanField(
        default=False,
        help_text="If True, combine PaymentSchedule and AdditionalCharge in one invoice. If False, send separate invoices."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenancy',)

    def __str__(self):
        return f"Invoice Config for {self.tenancy} - {'Combined' if self.combine_charges else 'Separate'}"
