# Generated by Django 5.2.1 on 2025-05-26 09:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0025_building_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='units',
            name='code',
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
    ]
