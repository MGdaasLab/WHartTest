from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserPromptViewSet

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'user-prompts', UserPromptViewSet, basename='userprompt')

urlpatterns = [
    path('', include(router.urls)),
]
