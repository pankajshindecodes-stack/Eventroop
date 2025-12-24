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
from .permissions import IsSuperUserOrReadOnly
from .utils import SalaryCalculator, AttendanceCalculator

class AttendanceStatusViewSet(ModelViewSet):
    queryset = AttendanceStatus.objects.all()
    serializer_class = AttendanceStatusSerializer
    permission_classes = [IsAuthenticated,IsSuperUserOrReadOnly]

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
    """
    Combined API endpoint to retrieve aggregated attendance reports.
    
    Permissions:
    - Admin: see everything
    - Owner: see attendance of their staff + managers (excluding themselves)
    - Staff/Manager: see only their own attendance
    
    Query Parameters:
    - user_id: Filter by user ID
    - search: Search by user name or email
    - start_date: Custom period start (YYYY-MM-DD)
    - end_date: Custom period end (YYYY-MM-DD)
    """
    permission_classes = [IsAuthenticated]

    def get_default_period(self):
        """Get default period (current month)."""
        today = timezone.now().date()
        start_date = today.replace(day=1)
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
        return start_date, end_date

    def get_queryset(self, user):
        """Get queryset based on user permissions with optimizations."""
        base_queryset = CustomUser.objects.select_related('hierarchy')
        
        if user.is_superuser:
            return base_queryset.all()
        
        if hasattr(user, 'is_owner') and user.is_owner:
            return base_queryset.filter(hierarchy__owner=user).exclude(id=user.id)
        
        return base_queryset.filter(id=user.id)

    def apply_filters(self, queryset, request):
        """Apply query parameter filters."""
        filters = Q()

        # Filter by user_id
        user_id = request.query_params.get('user_id')
        if user_id:
            filters &= Q(id=user_id)

        # Search by name or email
        search = request.query_params.get('search')
        if search:
            filters &= Q(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(employee_id__icontains=search)
            )
        
        if filters:
            return queryset.filter(filters)
        return queryset

    def get_date_range(self, request):
        """Get date range from query params or default to current month."""
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not (start_date_str and end_date_str):
            return self.get_default_period()

        try:
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            # Validate date range
            if end_date < start_date:
                return self.get_default_period()
            
            return start_date, end_date
        except ValueError:
            return self.get_default_period()

    def get_salary_structure(self, user, reference_date):
        """Get the active salary structure for a user."""
        return SalaryStructure.objects.filter(
            user=user,
            effective_from__lte=reference_date
        ).order_by('-effective_from').first()

    def get_aggregated_attendance(self, user, start_date, end_date, salary_structure=None):
        """Calculate aggregated attendance data for a user."""
        # Get salary structure if not provided
        if salary_structure is None:
            salary_structure = self.get_salary_structure(user, timezone.now().date())

        calculator = AttendanceCalculator(user, start_date, end_date)
        attendance_data = calculator.calculate()

        payable_days = attendance_data.get('total_payable_days', 0)
        salary_calc = SalaryCalculator(user, salary_structure)

        return {
            "user_id": user.id,
            "user_name": user.get_full_name(),
            "employee_id": getattr(user, 'employee_id', None),
            "attendance": attendance_data,
            "salary": self._build_salary_response(salary_calc, salary_structure, payable_days)
        }

    def _build_salary_response(self, salary_calc, salary_structure, payable_days):
        """Build salary response dictionary."""
        if not salary_structure:
            return {
                "salary_structure": None,
                "rate": 0,
                "daily_rate": 0,
                "current_payment": 0,
                "remaining_payable_days": 0,
                "remaining_payment": 0,
                "total_salary": 0,
                "advance_amount": 0
            }

        try:
            daily_rate = salary_calc._get_daily_rate()
            current_payment = salary_calc.calculate_salary(payable_days)
            remaining_days = salary_calc.calculate_remaining_days(payable_days)
            remaining_payment = salary_calc.calculate_remaining_salary(payable_days)
        except Exception as e:
            # Log the error here
            return {
                "salary_structure": salary_structure.salary_type,
                "rate": float(salary_structure.rate),
                "error": f"Calculation error: {str(e)}"
            }

        return {
            "salary_structure": salary_structure.salary_type,
            "rate": float(salary_structure.rate),
            "daily_rate": float(daily_rate),
            "current_payment": float(current_payment),
            "remaining_payable_days": remaining_days,
            "remaining_payment": float(remaining_payment),
            "total_salary": float(salary_structure.total_salary),
            "advance_amount": float(salary_structure.advance_amount)
        }

    def get(self, request):
        """Retrieve aggregated attendance reports."""
        start_date, end_date = self.get_date_range(request)
        user_id = request.query_params.get('user_id')

        queryset = self.get_queryset(request.user)
        queryset = self.apply_filters(queryset, request)

        # Single user report
        if user_id:
            try:
                target_user = queryset.get(id=user_id)
            except CustomUser.DoesNotExist:
                return Response(
                    {"status": "error", "message": "User not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )

            report = self.get_aggregated_attendance(target_user, start_date, end_date)
            return Response(
                {
                    "status": "success",
                    "period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "month": start_date.strftime("%B %Y")
                    },
                    "data": report
                },
                status=status.HTTP_200_OK
            )

        # Multiple users report - optimize by prefetching salary structures
        queryset = queryset.prefetch_related(
            Prefetch(
                'salary_structures',
                queryset=SalaryStructure.objects.filter(
                    effective_from__lte=timezone.now().date()
                ).order_by('-effective_from')[:1],
                to_attr='current_salary'
            )
        )

        reports = []
        for user in queryset:
            try:
                # Use prefetched salary structure
                salary_structure = (
                    user.current_salary[0]
                    if hasattr(user, 'current_salary') 
                    and user.current_salary 
                    else None
                )
                
                report = self.get_aggregated_attendance(
                    user, start_date, end_date, salary_structure
                )
                reports.append(report)
            except Exception as e:
                # Log the error here
                reports.append({
                    "user_id": user.id,
                    "user_name": user.get_full_name(),
                    "error": str(e)
                })

        return Response(
            {
                "status": "success",
                "count": len(reports),
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "month": start_date.strftime("%B %Y")
                },
                "results": reports
            },
            status=status.HTTP_200_OK
        )