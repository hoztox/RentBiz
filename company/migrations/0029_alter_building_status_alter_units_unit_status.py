# Generated by Django 5.2.1 on 2025-05-27 03:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0028_alter_charges_charge_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='building',
            name='status',
            field=models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active', max_length=20),
        ),
        migrations.AlterField(
            model_name='units',
            name='unit_status',
            field=models.CharField(choices=[('occupied', 'Occupied'), ('renovation', 'Renovation'), ('vacant', 'Vacant'), ('disputed', 'Disputed')], default='active', max_length=20),
        ),
    ]
