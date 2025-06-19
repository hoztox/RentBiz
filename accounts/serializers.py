
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import *



class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        company = Company(**validated_data)
        if password:
            company.set_password(password)
        company.save()
        return company

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        else:
            instance.save()
        return instance


class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = ['id', 'name']

class CountrySerializer(serializers.ModelSerializer):
    states = StateSerializer(many=True, read_only=True)

    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'states']