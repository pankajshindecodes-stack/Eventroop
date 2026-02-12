from rest_framework import status,generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from django.db import transaction
from django.shortcuts import get_object_or_404
from accounts.models import CustomUser

from .models import Attendance, AttendanceStatus,AttendanceReport
from .utils import AttendanceCalculator
from .permissions import IsSuperUserOrOwnerOrReadOnly
from .serializers import (
    AttendanceSerializer,
    AttendanceStatusSerializer,
    AttendanceReportSerializer,
)

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

class AttendanceReportView(generics.ListAPIView):
    serializer_class = AttendanceReportSerializer
    permission_classes = [IsAuthenticated]

    queryset = AttendanceReport.objects.select_related("user")

    #  Exact match filters
    filterset_fields = [
        "user_id",
        "period_type",
        "start_date",
        "end_date",
    ]

    #  Search (LIKE %term%)
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "period_type",
    ]

    #  Ordering
    ordering_fields = [
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["-start_date"]
    
    def get_queryset(self):
        user = self.request.user
        
        user_id = self.request.query_params.get("user_id")
        if user_id:
            report_user = get_object_or_404(CustomUser, id=user_id)

            with transaction.atomic():
                AttendanceCalculator(report_user).get_all_periods_attendance()

        if user.is_superuser:
            return self.queryset

        if user.is_owner:
            return self.queryset.filter(user__hierarchy__owner=user)

        if user.is_manager or user.is_vsre_staff:
            return self.queryset.filter(user=user)
