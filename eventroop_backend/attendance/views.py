# views.py
from .serializers import AttendanceSerializer, AttendanceStatusSerializer,TotalAttendanceSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import AttendanceStatus, Attendance,TotalAttendance
from .permissions import IsSuperUserOrReadOnly


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


class TotalAttendanceView(APIView):
    """
    GET: List all total attendance records with filters
    - Admin → see everything
    - Owner → see attendance of their staff + managers
    - Staff/Manager → see only their own attendance
    
    Query Parameters:
    - user_id: Filter by user ID
    - search: Search by user name or email
    - order_by: Order results (default: -updated_at)
    
    Examples:
    - GET /total-attendance/?user_id=5
    - GET /total-attendance/?search=john
    - GET /total-attendance/?order_by=user_name
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Admin → see everything
        if user.is_superuser:
            queryset = TotalAttendance.objects.all()
        # Owner → see attendance of their staff + managers
        elif hasattr(user, 'is_owner') and user.is_owner:
            queryset = TotalAttendance.objects.filter(user__hierarchy__owner=user)
        # Staff or Manager → see only their own attendance
        else:
            queryset = TotalAttendance.objects.filter(user=user)

        # Apply filters from query parameters
        user_id = request.query_params.get('user_id', None)
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Search by user name or email
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                user__first_name__icontains=search
            ) | queryset.filter(
                user__last_name__icontains=search
            ) | queryset.filter(
                user__email__icontains=search
            )

        # Filter by user type
        user_type = request.query_params.get('user_type', None)
        if user_type:
            queryset = queryset.filter(user__user_type=user_type)

        # Ordering
        order_by = request.query_params.get('order_by', '-updated_at')
        queryset = queryset.order_by(order_by)

        # Select related for optimization
        queryset = queryset.select_related('user')

        serializer = TotalAttendanceSerializer(queryset, many=True)

        return Response(
            {
                'count': queryset.count(),
                'results': serializer.data
            },
            status=status.HTTP_200_OK
        )
