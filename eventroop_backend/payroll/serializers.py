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
    


class SalaryTransactionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(
        source="user.get_full_name",
        read_only=True
    )

    class Meta:
        model = SalaryTransaction
        fields = [
            "id",
            "transaction_id",
            "user",
            "user_name",
            "total_payable_amount",
            "paid_amount",
            "remaining_payment",
            "daily_rate",
            "payment_period_start",
            "payment_period_end",
            "payment_method",
            "payment_reference",
            "status",
            "note",
            "processed_at",
        ]
        read_only_fields = [
            "transaction_id",
            "remaining_payment",
            "processed_at",
            "status",
        ]

    def validate(self, attrs):
        start = attrs.get("payment_period_start")
        end = attrs.get("payment_period_end")

        if start and end and end < start:
            raise serializers.ValidationError("End date must be after start date")

        return attrs
