from rest_framework import viewsets, permissions
from .models import APIKey
from .serializers import APIKeySerializer
from .permissions import IsOwnerOrAdmin
from wharttest_django.permissions import HasModelPermission

class APIKeyViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows API Keys to be viewed or edited.
    Users can only see and manage their own API Keys.
    Admins can see and manage all API Keys.
    Requires Django model permissions for api_keys.
    """
    serializer_class = APIKeySerializer
    permission_classes = [permissions.IsAuthenticated, HasModelPermission, IsOwnerOrAdmin]

    def get_queryset(self):
        """
        This view should return a list of all the API Keys
        for the currently authenticated user.
        """
        user = self.request.user
        # Ensure that even staff users (admins) only see their own API keys
        return APIKey.objects.filter(user=user).order_by('-created_at')

    def perform_create(self, serializer):
        """
        Automatically associates the API Key with the creating user.
        """
        serializer.save(user=self.request.user)
