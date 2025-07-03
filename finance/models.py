from django.db import models
from django.utils import timezone
from company.models import Invoice, PaymentSchedule, AdditionalCharge
from company.models import *
# Create your models here.


class Collection(models.Model):
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='collections', 
        help_text="The invoice this collection applies to"
    )
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        help_text="Amount collected in this transaction"
    )
    collection_date = models.DateField(
        default=timezone.now, 
        help_text="Date the collection was made"
    )
    collection_mode_choices = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('cheque', 'Cheque'),
        ('online_payment', 'Online Payment'),
    ]
    collection_mode = models.CharField(
        max_length=20, 
        choices=collection_mode_choices, 
        default='cash',
        help_text="Mode of payment"
    )
    status_choices = [
        ('completed', 'Completed'),
        ('partially_collected', 'Partially Collected'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(
        max_length=20, 
        choices=status_choices, 
        default='completed',
        help_text="Status of the collection"
    )
    reference_number = models.CharField(
        max_length=100, 
        null=True, 
        blank=True, 
        help_text="Reference number for the payment (e.g., transaction ID)"
    )
    account_holder_name = models.CharField(
        max_length=200, 
        null=True, 
        blank=True, 
        help_text="Name of the account holder for bank transfer or cheque"
    )
    account_number = models.CharField(
        max_length=100, 
        null=True, 
        blank=True, 
        help_text="Account number for bank transfer or cheque"
    )
    cheque_number = models.CharField(
        max_length=100, 
        null=True, 
        blank=True, 
        help_text="Cheque number for cheque payments"
    )
    cheque_date = models.DateField(
        null=True, 
        blank=True, 
        help_text="Date on the cheque"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Expense(models.Model):
    
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='expense_user', null=True, blank=True) 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='expense_comp', null=True, blank=True)
    EXPENSE_TYPE_CHOICES = [
        ('general', 'General'),
        ('tenancy', 'Tenancy'),
    ]

    expense_type = models.CharField(
        max_length=20,
        choices=EXPENSE_TYPE_CHOICES,
        default='general'
    )
    status_choices = [
        ('pending', 'pending'),
        ('paid', 'Paid'),
    ]
    status = models.CharField(max_length=20, choices=status_choices, default='pending')
    tenancy = models.ForeignKey(Tenancy, on_delete=models.CASCADE, related_name='tenancy_exp', null=True, blank=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='tenant_exp', null=True, blank=True)
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='building_exp', null=True, blank=True)
    unit = models.ForeignKey(Units, on_delete=models.CASCADE, related_name='unit_exp', null=True, blank=True)
    charge_type = models.ForeignKey(Charges, on_delete=models.CASCADE, related_name='charge_exp', null=True, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    tax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.expense_type if self.expense_type else "Untitled Expense"


class Refund(models.Model):
    REFUND_TYPES = [
        ('deposit', 'Deposit Refund'),
        ('excess', 'Excess Payment Refund'),
        ('other', 'Other Refund'),
    ]
    
    REFUND_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('credit_note', 'Credit Note'),
    ]
    
    tenancy = models.ForeignKey(Tenancy, on_delete=models.CASCADE, related_name='refunds')
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    refund_type = models.CharField(max_length=20, choices=REFUND_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    refund_method = models.CharField(max_length=20, choices=REFUND_METHODS)
    reference_number = models.CharField(max_length=100, null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    processed_date = models.DateField(default=timezone.now)
    processed_by = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Refund #{self.id} - {self.get_refund_type_display()} - {self.amount}"


class PaymentDistribution(models.Model):
    """
    Tracks how collection amounts are distributed across payment schedules and additional charges
    """
    collection = models.ForeignKey(Collection ,on_delete=models.CASCADE, related_name='distributions')
    payment_schedule = models.ForeignKey(PaymentSchedule, on_delete=models.CASCADE, null=True, blank=True)
    additional_charge = models.ForeignKey(AdditionalCharge, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(payment_schedule__isnull=False) | models.Q(additional_charge__isnull=False),
                name='either_payment_schedule_or_additional_charge'
            )
        ]
    
    def __str__(self):
        if self.payment_schedule:
            return f"Distribution: {self.amount} to PaymentSchedule {self.payment_schedule.id}"
        return f"Distribution: {self.amount} to AdditionalCharge {self.additional_charge.id}"


class Overpayment(models.Model):
    """
    Stores overpayment amounts that exceed the invoice total
    """
    tenancy = models.ForeignKey(Tenancy, on_delete=models.CASCADE, related_name='overpayments')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='overpayments')
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='overpayment')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status_choices = [
        ('available', 'Available'),
        ('refunded', 'Refunded'),
        ('adjusted', 'Adjusted'),
    ]
    status = models.CharField(max_length=20, choices=status_choices, default='available')
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Overpayment: {self.amount} for Invoice {self.invoice.invoice_number}"
