# serializers.py
from rest_framework import serializers
from .models import SalaryStructure, CustomUser
from django.utils import timezone
from decimal import Decimal

from rest_framework import serializers
from decimal import Decimal
from .models import SalaryStructure, CustomUser


class SalaryStructureSerializer(serializers.ModelSerializer):
    """
    Serializer for SalaryStructure model with nested user data
    """
    class Meta:
        model = SalaryStructure
        fields = [
            'id',
            'user',
            'salary_type',
            'base_salary',
            'advance_amount',
            'is_increment',
            'effective_from',
        ]
        read_only_fields = ['id','total_salary', 'created_at', 'updated_at']
