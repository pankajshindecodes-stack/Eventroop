# Django
from datetime import date, timedelta
from django.db.models import Q,Prefetch
from django.utils import timezone

# Third-party
from dateutil.relativedelta import relativedelta
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

# Local apps
from accounts.models import CustomUser
from payroll.models import SalaryStructure

# Attendance app
from .models import Attendance, AttendanceStatus
from .serializers import (
    AttendanceSerializer,
    AttendanceStatusSerializer,
)
from .permissions import IsSuperUserOrOwnerOrReadOnly
from .utils import SalaryCalculator, AttendanceCalculator
from django.db.models import Q
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

class AttendanceStatusViewSet(ModelViewSet):
    serializer_class = AttendanceStatusSerializer
    permission_classes = [IsAuthenticated, IsSuperUserOrOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user

        # Superuser → everything
        if user.is_superuser:
            return AttendanceStatus.objects.all()

        # Global statuses (created by superuser)
        global_qs = AttendanceStatus.objects.filter(owner__is_superuser=True)

        # Owner → global + own
        if user.is_owner:
            return global_qs | AttendanceStatus.objects.filter(owner=user)

        # Staff / Manager → global + their owner's
        if hasattr(user, "hierarchy") and user.hierarchy.owner:
            return global_qs | AttendanceStatus.objects.filter(
                owner=user.hierarchy.owner
            )

        return global_qs.none()

class AttendanceView(APIView):
    """
    GET: List all attendance records with filters
    POST: Create or Update attendance
    If attendance exists for user+date, update it. Otherwise create new.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Admin → see everything
        if user.is_superuser:
            queryset = Attendance.objects.all()
        # Owner → see attendance of their staff + managers
        elif user.is_owner:
            queryset = Attendance.objects.filter(user__hierarchy__owner=user)
        # Staff or Manager → see only their own attendance
        else:
            queryset = Attendance.objects.filter(user=user)

        # Apply filters from query parameters
        user_id = request.query_params.get('user_id', None)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        status_code = request.query_params.get('status', None)
        if status_code:
            queryset = queryset.filter(status__code=status_code)
        
        date = request.query_params.get('date', None)
        if date:
            queryset = queryset.filter(date=date)

        queryset = queryset.select_related('user', 'status').order_by('-date')
        serializer = AttendanceSerializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        user_id = request.data.get('user')
        date = request.data.get('date')

        # Validate required fields
        if not user_id:
            return Response(
                {'error': 'user field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not date:
            return Response(
                {'error': 'date field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if attendance already exists
        try:
            attendance = Attendance.objects.select_related('user', 'status').get(
                user_id=user_id, 
                date=date
            )
            # Update existing attendance
            serializer = AttendanceSerializer(attendance, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {
                        'message': 'Attendance updated successfully',
                        'data': serializer.data
                    },
                    status=status.HTTP_200_OK
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Attendance.DoesNotExist:
            # Create new attendance
            serializer = AttendanceSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {
                        'message': 'Attendance created successfully',
                        'data': serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class AttendanceReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_default_period(self):
        today = timezone.now().date()
        start = today.replace(day=1)
        end = (start + relativedelta(months=1)) - timedelta(days=1)
        return start, end

    def get_queryset(self, user):
        qs = CustomUser.objects.select_related("hierarchy")

        if user.is_superuser:
            return qs

        if getattr(user, "is_owner", False):
            return qs.filter(hierarchy__owner=user).exclude(id=user.id)

        return qs.filter(id=user.id)

    def apply_filters(self, queryset, request):
        q = Q()

        if uid := request.query_params.get("user_id"):
            q &= Q(id=uid)

        if search := request.query_params.get("search"):
            q &= (
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(employee_id__icontains=search)
            )

        return queryset.filter(q) if q else queryset

    def get_date_range(self, request):
        try:
            start = request.query_params.get("start_date")
            end = request.query_params.get("end_date")

            if not start or not end:
                return self.get_default_period()

            start_date = timezone.datetime.strptime(start, "%Y-%m-%d").date()
            end_date = timezone.datetime.strptime(end, "%Y-%m-%d").date()

            if end_date < start_date:
                raise ValueError("end_date cannot be before start_date")

            return start_date, end_date
        except ValueError as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_salary_structure(self, user, ref_date):
        return (
            SalaryStructure.objects
            .filter(user=user, effective_from__lte=ref_date)
            .order_by("-effective_from")
            .first()
        )

    def build_salary_response(self, salary_calc, salary_structure, payable_days):
        if not salary_structure:
            return {
                "salary_type": None,
                "final_salary": 0,
                "daily_rate": 0,
                "current_payment": 0,
                "remaining_payable_days": 0,
                "remaining_payment": 0,
            }

        daily_rate = salary_calc._daily_rate()
        current_payment = salary_calc.calculate_salary(payable_days)
        remaining_days = salary_calc.calculate_remaining_days(payable_days)
        remaining_payment = salary_calc.calculate_remaining_salary(payable_days)

        return {
            "salary_type": salary_structure.salary_type,
            "daily_rate": float(daily_rate),
            "current_payment": float(current_payment),
            "remaining_payable_days": remaining_days,
            "remaining_payment": float(remaining_payment),
        }

    def get_user_report(self, user, start_date, end_date, salary_structure=None):
        if not salary_structure:
            salary_structure = self.get_salary_structure(
                user, timezone.now().date()
            )

        attendance_calc = AttendanceCalculator(user, start_date, end_date)
        attendance = attendance_calc.calculate()

        payable_days = attendance["total_payable_days"]
        salary_calc = SalaryCalculator(user, salary_structure)

        return {
            "user_id": user.id,
            "user_name": user.get_full_name(),
            "employee_id": getattr(user, "employee_id", None),
            "attendance": attendance,
            "salary": self.build_salary_response(
                salary_calc, salary_structure, payable_days
            ),
        }

    def get(self, request):
        start_date, end_date = self.get_date_range(request)
        user_id = request.query_params.get("user_id")

        qs = self.apply_filters(
            self.get_queryset(request.user),
            request
        )

        # 🔹 Single user report
        if user_id:
            try:
                user = qs.get(id=user_id)
            except CustomUser.DoesNotExist:
                return Response(
                    {"status": "error", "message": "User not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                {
                    "status": "success",
                    "period": {
                        "start_date": start_date,
                        "end_date": end_date,
                        "month": start_date.strftime("%B %Y"),
                    },
                    "data": self.get_user_report(
                        user, start_date, end_date
                    ),
                }
            )

        # 🔹 Multiple users (optimized)
        qs = qs.prefetch_related(
            Prefetch(
                "salary_structures",
                queryset=SalaryStructure.objects.filter(
                    effective_from__lte=timezone.now().date()
                ).order_by("-effective_from"),
                to_attr="current_salary",
            )
        )

        results = []
        for user in qs:
            salary = user.current_salary[0] if user.current_salary else None
            results.append(
                self.get_user_report(user, start_date, end_date, salary)
            )

        return Response(
            {
                "status": "success",
                "count": len(results),
                "period": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "month": start_date.strftime("%B %Y"),
                },
                "results": results,
            }
        )
