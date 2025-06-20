# Generated by Django 5.2.1 on 2025-06-13 05:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0045_invoice'),
    ]

    operations = [
        migrations.AlterField(
            model_name='additionalcharge',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('invoice', 'Invoice')], default='pending', max_length=20),
        ),
        migrations.AlterField(
            model_name='paymentschedule',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('invoice', 'Invoice')], default='pending', max_length=20),
        ),
    ]
