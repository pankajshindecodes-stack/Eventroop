# views.py
from django.utils import timezone
from django.contrib.auth.hashers import check_password 
from rest_framework import viewsets,generics,status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from eventroop_backend.pagination import StandardResultsSetPagination
from django.db.models import Count, Q
from .permissions import IsVSREOwner,IsCreator,IsVSREOwnerOrManager,IsMasterAdmin
from .models import CustomUser, UserHierarchy, PricingModel, UserPlan
from .serializers import *

# ---------------------- User registration ViewSet ----------------------
class CustomerRegistrationView(generics.CreateAPIView):
    serializer_class = CustomerRegistrationSerializer
    permission_classes = [AllowAny]

class VSREOwnerRegistrationView(generics.CreateAPIView):
    serializer_class = VSREOwnerRegistrationSerializer
    permission_classes = [AllowAny]

# ---------------------- User Authentication ViewSet ----------------------
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            if not user.is_active:
                return Response(
                    {'error': 'Account pending approval by Master Admin.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            user.last_login = timezone.now()
            user.save()

            refresh = RefreshToken.for_user(user)
            return Response({
                'message': f'Login successful as {user.user_type}',
                'user': BaseUserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token)
                }
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'error': 'Invalid token or logout failed'}, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not check_password(serializer.validated_data['old_password'], user.password):
                return Response(
                    {"old_password": "Current password is incorrect."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ---------------------- User Profile ViewSet -------------------------
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self, user):
        role = user.user_type
        if role == CustomUser.UserTypes.VSRE_OWNER:
            return OwnerSerializer
        elif role == CustomUser.UserTypes.VSRE_MANAGER:
            return ManagerSerializer
        elif role == CustomUser.UserTypes.VSRE_STAFF:
            return StaffSerializer
        elif role == CustomUser.UserTypes.CUSTOMER:
            return CustomerSerializer
        return BaseUserSerializer  # fallback

    def get(self, request):
        serializer_class = self.get_serializer_class(request.user)
        serializer = serializer_class(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer_class = self.get_serializer_class(request.user)
        serializer = serializer_class(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ---------------------- User management ViewSet -------------------------

class MasterViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Allows MASTER_ADMIN to:
      - View all VSRE Owners
      - See their Managers and Staff counts
      - Retrieve full hierarchy for each owner
    """

    serializer_class = OwnerSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, IsMasterAdmin]
    filterset_fields = ["is_active", "city"]
    search_fields = ["email", "first_name", "last_name", "mobile_number"]

    def get_queryset(self):
        """Fetch all VSRE Owners."""
        return CustomUser.objects.owners().order_by("id")

    # ----------------------------------------------------------------------
    # LIST: All Owners with summary counts
    # ----------------------------------------------------------------------
    def list(self, request, *args, **kwargs):
        owners = self.filter_queryset(self.get_queryset())

        # Use CustomUserManager methods for counts
        data = []
        for owner in owners:
            managers = CustomUser.objects.get_all_managers_under_owner(owner)
            staff = CustomUser.objects.get_staff_under_owner(owner)

            data.append({
                "id": owner.id,
                "first_name": owner.first_name,
                "last_name": owner.last_name,
                "email": owner.email,
                "mobile_number": owner.mobile_number,
                "city": owner.city,
                "manager_count": managers.count(),
                "staff_count": staff.count(),
            })

        page = self.paginate_queryset(data)
        if page is not None:
            return self.get_paginated_response(page)

        return Response(data)

    # ----------------------------------------------------------------------
    # RETRIEVE: Detailed hierarchy of a specific owner
    # ----------------------------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        owner = self.get_object()

        # Use manager’s hierarchy helper
        hierarchy = CustomUser.objects.get_entire_hierarchy_under_owner(owner)

        managers = hierarchy["all_managers"]
        staff = hierarchy["all_staff"]

        data = OwnerSerializer(owner).data
        data.update({
            "manager_count": managers.count(),
            "staff_count": staff.count(),
            "managers": [
                {
                    "id": m.id,
                    "name": f"{m.first_name} {m.last_name}".strip(),
                    "email": m.email,
                    "staff_count": CustomUser.objects.get_staff_under_manager(m).count(),
                }
                for m in managers
            ],
        })

        return Response(data)


class ManagerViewSet(viewsets.ModelViewSet):
    """
    Allows VSRE_OWNER to manage their own VSRE_MANAGER users.
    """
    serializer_class = ManagerSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [ IsVSREOwner, IsCreator]
    filterset_fields = ["is_active", "city"]
    search_fields = ["email", "first_name", "last_name", "mobile_number"]

    def get_queryset(self):
        """Return only managers created by this owner."""
        return CustomUser.objects.filter(
            user_type="VSRE_MANAGER",
            created_by=self.request.user
        )

    def perform_create(self, serializer):
        """Auto-assign owner as creator."""
        serializer.save(
            user_type=CustomUser.UserTypes.VSRE_MANAGER,
            created_by=self.request.user
        )

    @action(detail=True, methods=["get"], url_path="assignable-parents")
    def get_assignable_parents(self, request, pk=None):

        user = self.get_object()  # manager selected
        owner = request.user      # authenticated owner

        # all managers under same owner
        all_managers = (
            CustomUser.objects
            .filter(
                user_type=CustomUser.UserTypes.VSRE_MANAGER,
                hierarchy__owner=owner
            )
            .exclude(id=user.id)
            .select_related("hierarchy")
        )

        # exclude children (cycle prevention)
        children_ids = user.subordinates.values_list("id", flat=True)
        all_managers = all_managers.exclude(id__in=children_ids)

        serializer = ManagerHierarchySerializer(all_managers, many=True)

        return Response(serializer.data, status=200)
    @action(detail=True, methods=["post"], url_path="assign")
    def assign_manager_to_manager(self, request,pk=None):
        user = self.get_object()   # manager we are modifying
        parent_manager_id = request.data.get("parent_manager_id")

        if not parent_manager_id:
            return Response({"error": "parent_manager_id is required"}, status=400)

        # validate parent
        try:
            new_parent_manager = CustomUser.objects.get(id=parent_manager_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "Parent manager not found"}, status=404)

        # Only manager can be parent
        if new_parent_manager.user_type not in [
            CustomUser.UserTypes.VSRE_MANAGER,
            CustomUser.UserTypes.LINE_MANAGER,
        ]:
            return Response({"error": "Parent must be a manager"}, status=400)

        # same owner?
        if new_parent_manager.hierarchy.owner != user.hierarchy.owner:
            return Response({"error": "Cannot assign to manager under another owner"}, status=400)

        # No self-assigning
        if new_parent_manager.id == user.id:
            return Response({"error": "Cannot assign user to itself"}, status=400)

        # Prevent cycle: cannot assign parent to its child
        children_ids = user.subordinates.values_list("id", flat=True)
        if new_parent_manager.id in children_ids:
            return Response({"error": "Cannot assign a manager under its own subordinate"}, status=400)

        # Update hierarchy
        hierarchy = user.hierarchy
        hierarchy.parent = new_parent_manager
        hierarchy.owner = new_parent_manager.hierarchy.owner
        hierarchy.save()

        return Response(
            status=status.HTTP_200_OK)


class StaffViewSet(viewsets.ModelViewSet):
    """
    Allows both VSRE_OWNER and VSRE_MANAGER to manage their own VSRE_STAFF users.
    """
    serializer_class = StaffSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsCreator,IsVSREOwnerOrManager]
    filterset_fields = ["is_active", "city"]
    search_fields = ["email", "first_name", "last_name", "mobile_number"]

    def get_queryset(self):
        """
        Return only staff created by the logged-in owner/manager.
        """
        return CustomUser.objects.filter(
            user_type="VSRE_STAFF",
            created_by=self.request.user
        )

    def perform_create(self, serializer):
        """
        Auto-assign creator and user type.
        """
        serializer.save(
            user_type=CustomUser.UserTypes.VSRE_STAFF,
            created_by=self.request.user
        )

    @action(detail=True, methods=["get"], url_path="assignable-parents")    
    def get_assignable_parents(self, request, pk=None):
        """
        Return a list of staff under the same owner
        excluding:
        - the current staff
        - its children (to avoid cycles)
        """
        user = self.get_object()  # staff selected

        owner = request.user # autherized owner 

        # all staff under the same owner
        all_staff = CustomUser.objects.filter(
            user_type =CustomUser.UserTypes.VSRE_STAFF,
            hierarchy__owner=owner,
        ).exclude(id=user.id)

        # exclude direct children (simple cycle prevention)
        children_ids = user.subordinates.values_list("id", flat=True)
        all_staff = all_staff.exclude(id__in=children_ids)

        data = [
            {
                "id": m.id,
                "name": f"{m.first_name} {m.last_name}",
                "email": m.email,
                "level": m.hierarchy.level,
                "parent_id": m.hierarchy.parent_id,
            }
            for m in all_staff
        ]

        return Response(data, status=200)

    @action(detail=True, methods=["post"], url_path="assign")
    def assign_manager_to_manager(self, request,pk=None):
        user = self.get_object()   # manager we are modifying
        parent_manager_id = request.data.get("parent_manager_id")

        if not parent_manager_id:
            return Response({"error": "parent_manager_id is required"}, status=400)

        # validate parent
        try:
            new_parent_manager = CustomUser.objects.get(id=parent_manager_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "Parent manager not found"}, status=404)

        # Only manager can be parent
        if new_parent_manager.user_type not in [
            CustomUser.UserTypes.VSRE_MANAGER,
            CustomUser.UserTypes.LINE_MANAGER,
        ]:
            return Response({"error": "Parent must be a manager"}, status=400)

        # same owner?
        if new_parent_manager.hierarchy.owner != user.hierarchy.owner:
            return Response({"error": "Cannot assign to manager under another owner"}, status=400)

        # No self-assigning
        if new_parent_manager.id == user.id:
            return Response({"error": "Cannot assign user to itself"}, status=400)

        # Prevent cycle: cannot assign parent to its child
        children_ids = user.subordinates.values_list("id", flat=True)
        if new_parent_manager.id in children_ids:
            return Response({"error": "Cannot assign a manager under its own subordinate"}, status=400)

        # Update hierarchy
        hierarchy = user.hierarchy
        hierarchy.parent = new_parent_manager
        hierarchy.owner = new_parent_manager.hierarchy.owner
        hierarchy.save()

        return Response(
            status=status.HTTP_200_OK)

# ---------------------- UserHierarchy ViewSet ----------------------
class UserHierarchyViewSet(viewsets.ModelViewSet):
    queryset = UserHierarchy.objects.select_related("user", "parent", "owner")
    serializer_class = UserHierarchySerializer
    filterset_fields = ['owner', 'parent', 'level', 'band', 'department']
    search_fields = ['user__email', 'owner__email', 'parent__email']


# ---------------------- PricingModel ViewSet ----------------------
class PricingModelViewSet(viewsets.ModelViewSet):
    queryset = PricingModel.objects.select_related("created_by")
    serializer_class = PricingModelSerializer
    filterset_fields = ['plan_type', 'is_active']
    search_fields = ['name', 'description', 'created_by__email']


# ---------------------- UserPlan ViewSet ----------------------
class UserPlanViewSet(viewsets.ModelViewSet):
    queryset = UserPlan.objects.select_related("user", "plan")
    serializer_class = UserPlanSerializer
    filterset_fields = ['is_active', 'plan__plan_type']
    search_fields = ['user__email', 'plan__name']

    @action(detail=True, methods=['post'])
    def expire(self, request, pk=None):
        plan = self.get_object()
        plan.is_active = False
        plan.end_date = timezone.now()
        plan.save()
        return Response({"detail": "Plan expired."})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        plan = self.get_object()
        plan.is_active = True
        if (
            plan.plan.plan_type == "SUBSCRIPTION"
            and (not plan.end_date or plan.end_date < timezone.now())
        ):
            plan.end_date = plan.start_date + timezone.timedelta(days=plan.plan.duration_days)
        plan.save()
        return Response({"detail": "Plan activated."})
