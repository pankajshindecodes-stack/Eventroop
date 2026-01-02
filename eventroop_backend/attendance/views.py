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
    # AttendanceReportSerializer,
)
from .permissions import IsSuperUserOrOwnerOrReadOnly
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

# class AttendanceReportAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self, user):
#         """Get users based on permission level."""
#         qs = CustomUser.objects.select_related("hierarchy").filter(is_active=True)
        
#         if user.is_superuser:
#             return qs
        
#         if getattr(user, "is_owner", False):
#             return qs.filter(hierarchy__owner=user).exclude(id=user.id)
        
#         return qs.filter(id=user.id)

#     def apply_filters(self, queryset, request):
#         """Apply search and user_id filters."""
#         q = Q()
        
#         if uid := request.query_params.get("user_id"):
#             q &= Q(id=uid)
        
#         if search := request.query_params.get("search"):
#             q &= (
#                 Q(first_name__icontains=search) |
#                 Q(last_name__icontains=search) |
#                 Q(email__icontains=search) |
#                 Q(employee_id__icontains=search)
#             )
        
#         return queryset.filter(q) if q else queryset

#     def parse_date_range(self, request):
#         """
#         Parse and validate date range from query params.
#         Returns (start_date, end_date) or (None, None) if not provided.
#         Raises ValueError if invalid.
#         """
#         start = request.query_params.get("start_date")
#         end = request.query_params.get("end_date")
        
#         if not start or not end:
#             return None, None

#         try:
#             start_date = datetime.strptime(start, "%Y-%m-%d").date()
#             end_date = datetime.strptime(end, "%Y-%m-%d").date()

#             if end_date < start_date:
#                 raise ValueError("end_date cannot be before start_date")
            
#             return start_date, end_date
        
#         except ValueError as e:
#             raise ValueError(f"Invalid date format or range: {str(e)}")

#     def get_reports_for_user(self, user, start_date=None, end_date=None):
#         """
#         Fetch attendance reports for a user.
#         Uses database cache via signals.
#         """
#         queryset = AttendanceReport.objects.filter(user=user).order_by('-start_date')
        
#         if start_date and end_date:
#             queryset = queryset.filter(
#                 start_date__gte=start_date,
#                 end_date__lte=end_date
#             )
        
#         return queryset

#     def get(self, request):
#         """
#         Get attendance reports for one or multiple users.
        
#         Query params:
#             - user_id: Filter by specific user (optional)
#             - search: Search by name, email, or employee_id (optional)
#             - start_date: Filter reports by start date (YYYY-MM-DD, optional)
#             - end_date: Filter reports by end date (YYYY-MM-DD, optional)
        
#         Returns:
#             Single user: {"status": "success", "user_id": X, "reports": [...]}
#             Multiple users: {"status": "success", "count": X, "results": [...]}
#         """
#         # Parse and validate date range
#         try:
#             start_date, end_date = self.parse_date_range(request)
#         except ValueError as e:
#             return Response(
#                 {"status": "error", "message": str(e)},
#                 status=400
#             )

#         # Get authorized users
#         queryset = self.apply_filters(
#             self.get_queryset(request.user),
#             request
#         )

#         user_id = request.query_params.get("user_id")

#         # 🔹 Single user endpoint
#         if user_id:
#             try:
#                 user = queryset.get(id=user_id)
#             except CustomUser.DoesNotExist:
#                 return Response(
#                     {"status": "error", "message": "User not found or access denied"},
#                     status=404
#                 )

#             reports = self.get_reports_for_user(user, start_date, end_date)
#             serializer = AttendanceReportSerializer(reports, many=True)

#             return Response(
#                 {
#                     "status": "success",
#                     "user_id": user.id,
#                     "user_name": user.get_full_name(),
#                     "email": user.email,
#                     "report_count": reports.count(),
#                     "reports": serializer.data,
#                 }
#             )

#         # 🔹 Multiple users endpoint
#         queryset = queryset.prefetch_related(
#             Prefetch(
#                 "attendance_reports",
#                 queryset=AttendanceReport.objects.order_by('-start_date'),
#                 to_attr="prefetched_reports",
#             )
#         )

#         results = []
#         for user in queryset:
#             # Filter reports by date range if provided
#             reports = user.prefetched_reports
#             if start_date and end_date:
#                 reports = [
#                     r for r in reports
#                     if r.start_date >= start_date and r.end_date <= end_date
#                 ]

#             serializer = AttendanceReportSerializer(reports, many=True)
#             results.append({
#                 "user_id": user.id,
#                 "user_name": user.get_full_name(),
#                 "employee_id": user.employee_id,
#                 "email": user.email,
#                 "report_count": len(reports),
#                 "reports": serializer.data,
#             })

#         return Response(
#             {
#                 "status": "success",
#                 "count": len(results),
#                 "results": results,
#             }
#         )