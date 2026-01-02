# context_processors.py
from django.utils import timezone
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from attendance.models import AttendanceReport
from payroll.models import SalaryStructure
from accounts.models import CustomUser
from .utils import generate_attendance_report


def attendance_report_context(request):
    """
    Context processor to generate/update attendance reports for current month.
    This is triggered on every page load.
    """ 
    if not request.user.is_superuser:
        user_id = request.query_params.get("user_id")
        if user_id:
            user = CustomUser.objects.get(id=user_id)
            generate_attendance_report(user)
    
    return {}

