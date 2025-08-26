from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RequirementDocumentViewSet, RequirementModuleViewSet,
    ReviewReportViewSet, ReviewIssueViewSet, ModuleReviewResultViewSet
)

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'documents', RequirementDocumentViewSet, basename='requirement-documents')
router.register(r'modules', RequirementModuleViewSet, basename='requirement-modules')
router.register(r'reports', ReviewReportViewSet, basename='review-reports')
router.register(r'issues', ReviewIssueViewSet, basename='review-issues')
router.register(r'module-results', ModuleReviewResultViewSet, basename='module-review-results')

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('', include(router.urls)),
]
