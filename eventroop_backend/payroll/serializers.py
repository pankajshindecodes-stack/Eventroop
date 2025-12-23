# serializers.py
from rest_framework import serializers
from .models import SalaryStructure, CustomUser
from django.utils import timezone
from decimal import Decimal


class SalaryStructureSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = SalaryStructure
        fields = [
            'id', 'user', 'user_name', 'user_email', 'salary_type', 
            'rate', 'total_salary', 'advance_amount', 'is_increment',
            'effective_from', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_effective_from(self, value):
        """Ensure effective_from is not in the past for new entries"""
        if not self.instance and value < timezone.now().date():
            raise serializers.ValidationError("Effective date cannot be in the past.")
        return value
    
    def validate(self, data):
        """Validate salary structure data"""
        # Check for overlapping salary structures
        user = data.get('user', getattr(self.instance, 'user', None))
        effective_from = data.get('effective_from', getattr(self.instance, 'effective_from', None))
        
        if user and effective_from:
            existing = SalaryStructure.objects.filter(
                user=user,
                effective_from=effective_from
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "A salary structure already exists for this user on this date."
                )
        
        # Validate rate for non-monthly salary types
        salary_type = data.get('salary_type', getattr(self.instance, 'salary_type', None))
        rate = data.get('rate')
        
        if salary_type != 'MONTHLY' and not rate:
            raise serializers.ValidationError({
                'rate': f"Rate is required for {salary_type} salary type."
            })
        
        return data


class SalaryIncrementSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())
    increment_amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        required=False,
        min_value=Decimal('0.01')
    )
    increment_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        min_value=Decimal('0.01'),
        max_value=Decimal('100.00')
    )
    effective_from = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate_effective_from(self, value):
        """Ensure effective_from is not in the past"""
        if value < timezone.now().date():
            raise serializers.ValidationError("Effective date cannot be in the past.")
        return value
    
    def validate(self, data):
        """Ensure either increment_amount or increment_percentage is provided, not both"""
        has_amount = 'increment_amount' in data and data['increment_amount']
        has_percentage = 'increment_percentage' in data and data['increment_percentage']
        
        if has_amount and has_percentage:
            raise serializers.ValidationError(
                "Provide either increment_amount or increment_percentage, not both."
            )
        
        if not has_amount and not has_percentage:
            raise serializers.ValidationError(
                "Either increment_amount or increment_percentage is required."
            )
        
        # Check if user has existing salary structure
        user = data['user']
        if not SalaryStructure.objects.filter(user=user).exists():
            raise serializers.ValidationError({
                'user': "User must have an existing salary structure before applying increment."
            })
        
        return data

