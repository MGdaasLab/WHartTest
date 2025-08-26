from django.urls import path, include # Added include
from rest_framework.routers import DefaultRouter
from .views import (
    UserCreateAPIView, CurrentUserAPIView,
    GroupViewSet, PermissionViewSet, UserViewSet, ContentTypeViewSet
)

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user') # Registered UserViewSet
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'content-types', ContentTypeViewSet, basename='content-type')

# The API URLs are now determined automatically by the router.
# Additionally, we include the existing paths for user registration and 'me' endpoint.
urlpatterns = [
    path('', include(router.urls)),
    path('register/', UserCreateAPIView.as_view(), name='user-register'),
    path('me/', CurrentUserAPIView.as_view(), name='user-me'),
]