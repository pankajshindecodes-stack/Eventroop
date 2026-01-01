# Django
from datetime import datetime
from django.db.models import Q,Prefetch
from django.utils import timezone

# Third-party
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

# Local apps
from accounts.models import CustomUser
from payroll.models import SalaryStructure

# Attendance app
from .models import Attendance, AttendanceStatus,AttendanceReport
from .serializers import (
    AttendanceSerializer,
    AttendanceStatusSerializer,
)
from .permissions import IsSuperUserOrOwnerOrReadOnly
from .utils import PayrollCalculator
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
        """
        Returns start_date and end_date from query params, or None if not provided.
        """
        start = request.query_params.get("start_date")
        end = request.query_params.get("end_date")
        start_date, end_date = None, None

        if start and end:
            try:
                start_date = datetime.strptime(start, "%Y-%m-%d").date()
                end_date = datetime.strptime(end, "%Y-%m-%d").date()

                if end_date < start_date:
                    raise ValueError("end_date cannot be before start_date")
            except ValueError as e:
                return Response(
                    {"status": "error", "message": str(e)},
                    status=400
                )
        return start_date, end_date

    def get_all_period_reports(self, user, start_date=None, end_date=None):
        """
        Returns all payroll reports for a user:
        - If start_date/end_date provided, restrict to that range
        - Otherwise, automatically from first attendance to today
        """
        payroll = PayrollCalculator(user)
        if start_date and end_date:
            return payroll.calculate_all_periods_auto(start_date=start_date, end_date=end_date)
        return payroll.calculate_all_periods_auto()  # all periods automatically

    def get(self, request):
        start_date, end_date = self.get_date_range(request)
        if isinstance(start_date, Response):  # Error response from get_date_range
            return start_date

        user_id = request.query_params.get("user_id")
        qs = self.apply_filters(self.get_queryset(request.user), request)

        # 🔹 Single user
        if user_id:
            try:
                user = qs.get(id=user_id)
            except CustomUser.DoesNotExist:
                return Response(
                    {"status": "error", "message": "User not found"},
                    status=404
                )

            reports = self.get_all_period_reports(user, start_date, end_date)
            return Response(
                {
                    "status": "success",
                    "user_id": user.id,
                    "reports": reports,
                }
            )

        # 🔹 Multiple users
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
            reports = self.get_all_period_reports(user, start_date, end_date)
            results.append({"user_id": user.id, "reports": reports})

        return Response(
            {
                "status": "success",
                "count": len(results),
                "results": results,
            }
        )
