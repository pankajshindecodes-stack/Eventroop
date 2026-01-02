# serializers.py
from rest_framework import serializers
from .models import SalaryStructure, SalaryTransaction
from accounts.models import CustomUser


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
            'change_type',
            'amount',
            'final_salary',
            'effective_from',
        ]
        read_only_fields = ['id','final_salary','created_at', 'updated_at']
    
    def validate(self, attrs):
        user = attrs.get("user")
        change_type = attrs.get("change_type")

        # Only check when creating base salary
        if change_type == "BASE_SALARY":
            qs = SalaryStructure.objects.filter(
                user=user,
                change_type="BASE_SALARY"
            )

            # If this is update, exclude current instance
            if self.instance:
                qs = qs.exclude(id=self.instance.id)

            if qs.exists():
                raise serializers.ValidationError({
                    "change_type": "Base salary already exists for this user."
                })

        return attrs
    
