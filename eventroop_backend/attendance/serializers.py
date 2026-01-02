# serializers.py
from rest_framework import serializers
from .models import Attendance, AttendanceStatus,AttendanceReport


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


# class AttendanceReportSerializer(serializers.ModelSerializer):
#     """Serializer for individual attendance reports."""
    
#     class Meta:
#         model = AttendanceReport
#         fields = [
#             'start_date',
#             'end_date',
#             'period_type',
#             'present_days',
#             'absent_days',
#             'half_day_count',
#             'paid_leave_days',
#             'weekly_Offs',
#             'unpaid_leaves',
#             'total_payable_days',
#             'total_payable_hours',
#         ]
#         read_only_fields = fields


# class UserAttendanceReportSerializer(serializers.Serializer):
#     """Serializer for user with their attendance reports."""
    
#     user_id = serializers.IntegerField()
#     user_name = serializers.CharField(source='user.get_full_name', read_only=True)
#     employee_id = serializers.CharField(source='user.employee_id', read_only=True)
#     email = serializers.EmailField(source='user.email', read_only=True)
#     reports = AttendanceReportSerializer(many=True, read_only=True)


# class AttendanceReportListSerializer(serializers.Serializer):
#     """Serializer for list response with single user."""
    
#     status = serializers.CharField()
#     user_id = serializers.IntegerField()
#     user_name = serializers.CharField(required=False)
#     email = serializers.EmailField(required=False)
#     report_count = serializers.IntegerField(required=False)
#     reports = AttendanceReportSerializer(many=True, read_only=True)


# class AttendanceReportBulkListSerializer(serializers.Serializer):
#     """Serializer for bulk list response with multiple users."""
    
#     status = serializers.CharField()
#     count = serializers.IntegerField()
#     results = UserAttendanceReportSerializer(many=True, read_only=True)


#     """Serializer for filtering reports."""
#     user_id = serializers.IntegerField(required=False, allow_null=True)
#     search = serializers.CharField(required=False, allow_blank=True)
#     start_date = serializers.DateField(required=False, allow_null=True)
#     end_date = serializers.DateField(required=False, allow_null=True)
#     period_type = serializers.ChoiceField(
#         choices=['HOURLY', 'DAILY', 'WEEKLY', 'FORTNIGHTLY', 'MONTHLY'],
#         default='MONTHLY'
#     )
#     include_salary = serializers.BooleanField(default=False)
    
#     def validate(self, data):
#         start_date = data.get('start_date')
#         end_date = data.get('end_date')
        
#         if start_date and end_date and end_date < start_date:
#             raise serializers.ValidationError({
#                 'end_date': "end_date cannot be before start_date"
#             })
        
#         return data