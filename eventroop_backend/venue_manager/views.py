# #views.py
# from .models import Venue
# from .serializers import VenueSerializer
# from .permissions import DashboardAccessPermission
# from rest_framework import viewsets, status
# from rest_framework.response import Response
# from rest_framework.parsers import JSONParser, MultiPartParser
# from rest_framework.pagination import PageNumberPagination

# class VenueViewSet(viewsets.ViewSet):
#     serializer_class = VenueSerializer
#     parser_classes = [JSONParser, MultiPartParser]
#     # permission_classes = [DashboardAccessPermission]
#     pagination_class = PageNumberPagination

#     def get_queryset(self):
#         user = self.request.user
#         user_type = getattr(user, "user_type", None)

#         # Base queryset
#         if user.is_superuser:
#             queryset = Venue.objects.all()
#         else:
#             queryset = Venue.objects.filter(is_deleted=False)


#         # Filter by user type if authenticated
#         if user.is_authenticated:
#             filters = {
#                 "VSRE_OWNER": {"owner": getattr(user, "owner_profile", None)},
#                 "VSRE_MANAGER": {"manager": getattr(user, "manager_profile", None)},
#             }
#             if user_type in filters:
#                 queryset = queryset.filter(**filters[user_type])
#         return queryset.order_by("-id")

#     def get_object(self, pk=None):
#         """Helper method to get single venue object"""
#         try:
#             if pk is None:
#                 pk = self.kwargs.get('pk')
#             return self.get_queryset().get(pk=pk)
#         except Venue.DoesNotExist:
#             return None

#     def list(self, request):
#         """Get list of venues"""
#         try:
#             queryset = self.get_queryset()
            
#             # Apply pagination
#             paginator = self.pagination_class()
#             page = paginator.paginate_queryset(queryset, request)
            
#             if page is not None:
#                 serializer = self.serializer_class(page, many=True)
#                 return paginator.get_paginated_response(serializer.data)
            
#             serializer = self.serializer_class(queryset, many=True)
#             return Response(serializer.data, status=status.HTTP_200_OK)
            
#         except Exception as e:
#             return Response({
#                 "status": "error",
#                 "message": "Failed to list venues",
#                 "error": str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def retrieve(self, request, pk=None):
#         """Get single venue details"""
#         try:
#             instance = self.get_object(pk)
#             if not instance:
#                 return Response({
#                     "status": "error",
#                     "message": "Venue not found"
#                 }, status=status.HTTP_404_NOT_FOUND)
                
#             serializer = self.serializer_class(instance)
#             return Response(serializer.data, status=status.HTTP_200_OK)
            
#         except Exception as e:
#             return Response({
#                 "status": "error",
#                 "message": "Failed to retrieve venue",
#                 "error": str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def create(self, request):
#         """Create new venue"""
#         serializer = self.serializer_class(data=request.data,context={'request': request})
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         else:
#             return Response({
#                 "status": "error",
#                 "message": "Validation failed",
#                 "errors": serializer.errors
#             }, status=status.HTTP_400_BAD_REQUEST)
                

#     def partial_update(self, request, pk=None):
#         """Partial update venue (PATCH)"""
#         try:
#             instance = self.get_object(pk)
#             if not instance:
#                 return Response({
#                     "status": "error",
#                     "message": "Venue not found"
#                 }, status=status.HTTP_404_NOT_FOUND)

#             serializer = self.serializer_class(instance, data=request.data, partial=True)
#             if serializer.is_valid():
#                 serializer.save()
#                 return Response(serializer.data, status=status.HTTP_200_OK)
#             else:
#                 return Response({
#                     "status": "error",
#                     "message": "Validation failed",
#                     "errors": serializer.errors
#                 }, status=status.HTTP_400_BAD_REQUEST)
                
#         except Exception as e:
#             return Response({
#                 "status": "error",
#                 "message": "Failed to update venue",
#                 "error": str(e)
#             }, status=status.HTTP_400_BAD_REQUEST)

#     def destroy(self, request, pk=None):
#         """Delete venue"""
#         try:
#             instance = self.get_object(pk)
#             if not instance:
#                 return Response({
#                     "status": "error",
#                     "message": "Venue not found"
#                 }, status=status.HTTP_404_NOT_FOUND)

#             user = request.user
#             user_type = getattr(user, "user_type", None)

#             # Perform deletion based on user type
#             if user_type == "MASTER_ADMIN":
#                 instance.delete()
#                 message = "Venue permanently deleted"
#             elif user_type == "VSRE_OWNER" and instance.owner.user == user:
#                 instance.soft_delete()
#                 message = "Venue soft deleted successfully"
#             else:
#                 return Response({
#                     "status": "error",
#                     "message": "You don't have permission to delete this venue"
#                 }, status=status.HTTP_403_FORBIDDEN)

#             return Response({
#                 "status": "success",
#                 "message": message
#             }, status=status.HTTP_200_OK)
            
#         except Exception as e:
#             return Response({
#                 "status": "error",
#                 "message": "Failed to delete venue",
#                 "error": str(e)
#             }, status=status.HTTP_400_BAD_REQUEST)