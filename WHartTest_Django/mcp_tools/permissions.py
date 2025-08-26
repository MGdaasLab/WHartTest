from rest_framework import permissions
from asgiref.sync import sync_to_async

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it,
    or allow admin users to view/edit all objects.
    Supports both 'user' and 'owner' fields.
    """

    def has_permission(self, request, view):
        # Authenticated users can always list/create objects.
        # Object-level permissions will filter results for list and detail views.
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request, so we'll always allow GET, HEAD, or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner of the object.
        # Admins can modify/delete any object.
        if request.user.is_staff: # Django admin users can access all
            return True
        
        # Support both 'user' and 'owner' fields
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'owner'):
            return obj.owner == request.user
        else:
            # If neither field exists, deny access (safer default)
            return False

class IsOwnerOrAdminOriginal(permissions.BasePermission):
    """
    Original version - only supports 'user' field for backward compatibility.
    """

    def has_permission(self, request, view):
        # Authenticated users can always list/create API keys.
        # Object-level permissions will filter results for list and detail views.
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request, so we'll always allow GET, HEAD, or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner of the snippet.
        # For APIKey, only the owner can modify/delete their own key.
        # Admins can modify/delete any key.
        if request.user.is_staff: # Django admin users can access all
            return True
        
        return obj.user == request.user
