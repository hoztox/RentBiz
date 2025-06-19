from django.db import models
from django.utils import timezone
from company.models import Invoice, PaymentSchedule, AdditionalCharge

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
