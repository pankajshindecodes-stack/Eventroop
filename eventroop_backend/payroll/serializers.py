# serializers.py
from rest_framework import serializers
from .models import SalaryStructure, SalaryReport
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
    
class SalaryReportSerializer(serializers.ModelSerializer):
    final_salary = serializers.SerializerMethodField()
    advance_amount = serializers.SerializerMethodField()

    class Meta:
        model = SalaryReport
        fields = [
            "id",
            "user",
            "start_date",
            "end_date",
            "final_salary",
            "advance_amount",
            "total_payable_amount",
            "paid_amount",
            "remaining_payment",
        ]
        read_only_fields = [
            "id",
            "remaining_payment",
            "final_salary",
            "advance_amount",
        ]

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")

        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "End date must be after start date"}
            )

        return attrs
    def get_advance_amount(self, obj):
        return obj.advance_amount
    def get_final_salary(self, obj):
        return obj.final_salary