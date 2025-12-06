from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import api_view,permission_classes

@api_view(["GET"])
@permission_classes([AllowAny])
def status(request):
    return Response({"Status": "Ok"},status=200)
