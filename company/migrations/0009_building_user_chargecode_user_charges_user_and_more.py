# Generated by Django 5.2.1 on 2025-05-15 04:42

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0008_charges'),
    ]

    operations = [
        migrations.AddField(
            model_name='building',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='buil_comp', to='company.users'),
        ),
        migrations.AddField(
            model_name='chargecode',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='charge_comp', to='company.users'),
        ),
        migrations.AddField(
            model_name='charges',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ch_comp', to='company.users'),
        ),
        migrations.AddField(
            model_name='currency',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='id_type_comp', to='company.users'),
        ),
        migrations.AddField(
            model_name='idtype',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='id_comp', to='company.users'),
        ),
        migrations.AddField(
            model_name='masterdocumenttype',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='user_comp', to='company.users'),
        ),
        migrations.AddField(
            model_name='tenant',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tene_comp', to='company.users'),
        ),
        migrations.AddField(
            model_name='units',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='uni_comp', to='company.users'),
        ),
        migrations.AddField(
            model_name='unittype',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='unit_type_comp', to='company.users'),
        ),
    ]
