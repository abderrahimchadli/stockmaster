from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_status(request):
    """
    Simple API endpoint to check if the rules API is working
    """
    return Response({"status": "ok", "message": "Rules API is operational"}) 