# views.py
from .serializers import AttendanceSerializer, AttendanceStatusSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import AttendanceStatus, Attendance
from accounts.permissions import IsMasterAdminOrOwner


class AttendanceStatusViewSet(ModelViewSet):
    queryset = AttendanceStatus.objects.all()
    serializer_class = AttendanceStatusSerializer
    permission_classes = [IsAuthenticated, IsMasterAdminOrOwner]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return AttendanceStatus.objects.all()
        # Owner sees only their own statuses
        return AttendanceStatus.objects.filter(owner=user)

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            # Admin can set any owner explicitly
            serializer.save()
        else:
            # Owner: automatically set owner to self
            serializer.save(owner=user)


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
