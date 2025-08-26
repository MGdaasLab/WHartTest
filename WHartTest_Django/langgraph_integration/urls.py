from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LLMConfigViewSet, ChatAPIView, ChatHistoryAPIView, UserChatSessionsAPIView, ChatStreamAPIView, KnowledgeRAGAPIView, ProviderChoicesAPIView

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'llm-configs', LLMConfigViewSet, basename='llmconfig')

# The API URLs are now determined automatically by the router.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', include(router.urls)),
    path('providers/', ProviderChoicesAPIView.as_view(), name='provider_choices_api'),
    path('chat/', ChatAPIView.as_view(), name='chat_api'),
    path('chat/stream/', ChatStreamAPIView.as_view(), name='chat_stream_api'),
    path('chat/history/', ChatHistoryAPIView.as_view(), name='chat_history_api'),
    path('chat/sessions/', UserChatSessionsAPIView.as_view(), name='user_chat_sessions_api'),
    path('knowledge/rag/', KnowledgeRAGAPIView.as_view(), name='knowledge_rag_api'),
]