from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    KnowledgeBaseViewSet, DocumentViewSet, 
    DocumentChunkViewSet, QueryLogViewSet,
    embedding_services
)

router = DefaultRouter()
router.register(r'knowledge-bases', KnowledgeBaseViewSet)
router.register(r'documents', DocumentViewSet)
router.register(r'chunks', DocumentChunkViewSet)
router.register(r'query-logs', QueryLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('embedding-services/', embedding_services, name='embedding-services'),
]
