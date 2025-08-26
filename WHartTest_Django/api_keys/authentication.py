from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from .models import APIKey

class APIKeyAuthentication(BaseAuthentication):
    """
    Custom authentication class for API Key based authentication.
    Looks for 'X-API-Key' header in the request.
    """
    def authenticate(self, request):
        api_key_value = None

        # Try to get API key from Authorization: Bearer header
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if auth_header:
            try:
                token_type, token = auth_header.split(' ', 1)
                if token_type.lower() == 'bearer':
                    api_key_value = token
            except ValueError:
                pass # Invalid format, try X-API-Key

        # If not found in Authorization header, try X-API-Key header
        if not api_key_value:
            api_key_value = request.META.get('HTTP_X_API_KEY')

        if not api_key_value:
            return None # No API Key or Authorization header found, let other authentication classes handle it

        try:
            api_key_obj = APIKey.objects.select_related('user').get(key=api_key_value)
        except APIKey.DoesNotExist:
            raise AuthenticationFailed('Invalid API Key.')

        if not api_key_obj.is_valid():
            raise AuthenticationFailed('API Key is inactive or expired.')

        # If the key is valid, return the user and the APIKey object (as token)
        return (api_key_obj.user, api_key_obj)

    def authenticate_header(self, request):
        """
        Returns a string that should be used as the value of the WWW-Authenticate
        header in a 401 Unauthorized response.
        """
        return 'API-Key'