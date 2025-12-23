# serializers.py
from rest_framework import serializers
from .models import SalaryStructure, CustomUser
from django.utils import timezone
from decimal import Decimal


class SalaryStructureSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = SalaryStructure
        fields = [
            'id', 'user', 'user_name', 'user_email', 'salary_type', 
            'rate', 'total_salary', 'advance_amount', 'is_increment',
            'effective_from', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_effective_from(self, value):
        """Ensure effective_from is not in the past for new entries"""
        if not self.instance and value < timezone.now().date():
            raise serializers.ValidationError("Effective date cannot be in the past.")
        return value
    
    def validate(self, data):
        """Validate salary structure data"""
        # Check for overlapping salary structures
        user = data.get('user', getattr(self.instance, 'user', None))
        effective_from = data.get('effective_from', getattr(self.instance, 'effective_from', None))
        
        if user and effective_from:
            existing = SalaryStructure.objects.filter(
                user=user,
                effective_from=effective_from
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "A salary structure already exists for this user on this date."
                )
        
        # Validate rate for non-monthly salary types
        salary_type = data.get('salary_type', getattr(self.instance, 'salary_type', None))
        rate = data.get('rate')
        
        if salary_type != 'MONTHLY' and not rate:
            raise serializers.ValidationError({
                'rate': f"Rate is required for {salary_type} salary type."
            })
        
        return data


class SalaryIncrementSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())
    increment_amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        required=False,
        min_value=Decimal('0.01')
    )
    increment_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        min_value=Decimal('0.01'),
        max_value=Decimal('100.00')
    )
    effective_from = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate_effective_from(self, value):
        """Ensure effective_from is not in the past"""
        if value < timezone.now().date():
            raise serializers.ValidationError("Effective date cannot be in the past.")
        return value
    
    def validate(self, data):
        """Ensure either increment_amount or increment_percentage is provided, not both"""
        has_amount = 'increment_amount' in data and data['increment_amount']
        has_percentage = 'increment_percentage' in data and data['increment_percentage']
        
        if has_amount and has_percentage:
            raise serializers.ValidationError(
                "Provide either increment_amount or increment_percentage, not both."
            )
        
        if not has_amount and not has_percentage:
            raise serializers.ValidationError(
                "Either increment_amount or increment_percentage is required."
            )
        
        # Check if user has existing salary structure
        user = data['user']
        if not SalaryStructure.objects.filter(user=user).exists():
            raise serializers.ValidationError({
                'user': "User must have an existing salary structure before applying increment."
            })
        
        return data


# views.py
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
from .models import SalaryStructure, CustomUser
from .serializers import SalaryStructureSerializer, SalaryIncrementSerializer


class SalaryStructureListCreateView(APIView):
    """
    GET: List salary structures based on user hierarchy
    POST: Create a new salary structure
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Admin → see everything
        if user.is_superuser:
            queryset = SalaryStructure.objects.all()
        # Owner → see salary structures of their staff + managers
        elif user.is_owner:
            queryset = SalaryStructure.objects.filter(user__hierarchy__owner=user)
        # Staff or Manager → see only their own salary structure
        else:
            queryset = SalaryStructure.objects.filter(user=user)
        
        # Apply filters from query parameters
        user_id = request.query_params.get('user_id', None)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by salary type
        salary_type = request.query_params.get('salary_type')
        if salary_type:
            queryset = queryset.filter(salary_type=salary_type)
        
        # Filter by increment status
        is_increment = request.query_params.get('is_increment')
        if is_increment is not None:
            queryset = queryset.filter(is_increment=is_increment.lower() == 'true')
        
        # Filter by date range
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(effective_from__gte=start_date)
        if end_date:
            queryset = queryset.filter(effective_from__lte=end_date)
        
        queryset = queryset.select_related('user').order_by('-effective_from')
        serializer = SalaryStructureSerializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Create a new salary structure"""
        serializer = SalaryStructureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {
                'message': 'Salary structure created successfully',
                'data': serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class SalaryStructureDetailView(APIView):
    """
    GET: Retrieve a specific salary structure
    PUT: Update a salary structure
    PATCH: Partially update a salary structure
    DELETE: Delete a salary structure
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        """Get salary structure with hierarchy-based permissions"""
        try:
            salary_structure = SalaryStructure.objects.select_related('user').get(pk=pk)
        except SalaryStructure.DoesNotExist:
            return None
        
        # Check permissions
        if user.is_superuser:
            return salary_structure
        elif user.is_owner:
            if salary_structure.user.hierarchy.owner == user:
                return salary_structure
        else:
            if salary_structure.user == user:
                return salary_structure
        
        return None
    
    def get(self, request, pk):
        """Retrieve a specific salary structure"""
        salary_structure = self.get_object(pk, request.user)
        
        if not salary_structure:
            return Response(
                {'error': 'Salary structure not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = SalaryStructureSerializer(salary_structure)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, pk):
        """Update a salary structure"""
        salary_structure = self.get_object(pk, request.user)
        
        if not salary_structure:
            return Response(
                {'error': 'Salary structure not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = SalaryStructureSerializer(salary_structure, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {
                'message': 'Salary structure updated successfully',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def patch(self, request, pk):
        """Partially update a salary structure"""
        salary_structure = self.get_object(pk, request.user)
        
        if not salary_structure:
            return Response(
                {'error': 'Salary structure not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = SalaryStructureSerializer(
            salary_structure, 
            data=request.data, 
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {
                'message': 'Salary structure updated successfully',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def delete(self, request, pk):
        """Delete a salary structure"""
        salary_structure = self.get_object(pk, request.user)
        
        if not salary_structure:
            return Response(
                {'error': 'Salary structure not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        salary_structure.delete()
        
        return Response(
            {'message': 'Salary structure deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


class SalaryIncrementView(APIView):
    """
    POST: Apply salary increment to a user
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Apply salary increment to a user"""
        serializer = SalaryIncrementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        effective_from = serializer.validated_data['effective_from']
        
        # Check if requesting user has permission to increment this user's salary
        requesting_user = request.user
        if not requesting_user.is_superuser:
            if requesting_user.is_owner:
                if not hasattr(user, 'hierarchy') or user.hierarchy.owner != requesting_user:
                    return Response(
                        {'error': 'You do not have permission to modify this user\'s salary'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            else:
                return Response(
                    {'error': 'You do not have permission to apply salary increments'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Get the latest salary structure before the effective date
        latest_salary = SalaryStructure.objects.filter(
            user=user,
            effective_from__lt=effective_from
        ).order_by('-effective_from').first()
        
        if not latest_salary:
            return Response(
                {'error': 'No previous salary structure found for this user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate new salary
        if 'increment_amount' in serializer.validated_data and serializer.validated_data['increment_amount']:
            new_salary = latest_salary.total_salary + serializer.validated_data['increment_amount']
        else:
            percentage = serializer.validated_data['increment_percentage']
            increment = (latest_salary.total_salary * percentage) / Decimal('100')
            new_salary = latest_salary.total_salary + increment
        
        # Create new salary structure
        new_salary_structure = SalaryStructure.objects.create(
            user=user,
            salary_type=latest_salary.salary_type,
            rate=latest_salary.rate,
            total_salary=new_salary,
            advance_amount=Decimal('0'),
            is_increment=True,
            effective_from=effective_from
        )
        
        response_serializer = SalaryStructureSerializer(new_salary_structure)
        
        return Response(
            {
                'message': 'Salary increment applied successfully',
                'previous_salary': str(latest_salary.total_salary),
                'new_salary': str(new_salary),
                'increment_amount': str(new_salary - latest_salary.total_salary),
                'data': response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class CurrentSalaryView(APIView):
    """
    GET: Get current active salary for a user
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current active salary for a user"""
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        requesting_user = request.user
        
        # Check permissions
        if not requesting_user.is_superuser:
            if requesting_user.is_owner:
                try:
                    target_user = CustomUser.objects.get(pk=user_id)
                    if not hasattr(target_user, 'hierarchy') or target_user.hierarchy.owner != requesting_user:
                        return Response(
                            {'error': 'Access denied'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                except CustomUser.DoesNotExist:
                    return Response(
                        {'error': 'User not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                if str(requesting_user.id) != str(user_id):
                    return Response(
                        {'error': 'Access denied'},
                        status=status.HTTP_403_FORBIDDEN
                    )
        
        current_salary = SalaryStructure.objects.filter(
            user_id=user_id,
            effective_from__lte=timezone.now().date()
        ).order_by('-effective_from').first()
        
        if not current_salary:
            return Response(
                {'error': 'No active salary structure found for this user'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = SalaryStructureSerializer(current_salary)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SalaryHistoryView(APIView):
    """
    GET: Get salary history for a user
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get salary history for a user"""
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        requesting_user = request.user
        
        # Check permissions
        if not requesting_user.is_superuser:
            if requesting_user.is_owner:
                try:
                    target_user = CustomUser.objects.get(pk=user_id)
                    if not hasattr(target_user, 'hierarchy') or target_user.hierarchy.owner != requesting_user:
                        return Response(
                            {'error': 'Access denied'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                except CustomUser.DoesNotExist:
                    return Response(
                        {'error': 'User not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                if str(requesting_user.id) != str(user_id):
                    return Response(
                        {'error': 'Access denied'},
                        status=status.HTTP_403_FORBIDDEN
                    )
        
        history = SalaryStructure.objects.filter(user_id=user_id).order_by('-effective_from')
        serializer = SalaryStructureSerializer(history, many=True)
        
        return Response({
            'count': history.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)

