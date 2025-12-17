# serializers.py
from rest_framework import serializers
from .models import Attendance, AttendanceStatus,TotalAttendance


class AttendanceStatusSerializer(serializers.ModelSerializer):    
    class Meta:
        model = AttendanceStatus
        fields = "__all__"
        read_only_fields = ['owner']


class AttendanceSerializer(serializers.ModelSerializer):
    # Quick access fields
    status_label = serializers.CharField(source='status.label', read_only=True)
    status_code = serializers.CharField(source='status.code', read_only=True)
    
    class Meta:
        model = Attendance
        fields = [
            'user',
            'date',
            'duration',
            'status',
            'status_label',
            'status_code',
            'reason',
        ]
    
    def validate(self, data):
        """Validate attendance data"""
        user = data.get('user')
        date = data.get('date')
        
        # Check for duplicate attendance (only for create, not update)
        if not self.instance:
            if Attendance.objects.filter(user=user, date=date).exists():
                raise serializers.ValidationError(
                    f"Attendance for {user.get_full_name()} on {date} already exists."
                )
        
        return data
    

class TotalAttendanceSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    
    class Meta:
        model = TotalAttendance
        fields = [
            "id",
            "user_name",
            "present_days",
            "absent_days",
            "half_day_count",
            "paid_leave_days",
            "total_payable_days",
            "total_payable_hours",
        ]
        read_only_fields = fields
