from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views # Import the entire views module

router = DefaultRouter()
router.register(r'remote-configs', views.RemoteMCPConfigViewSet, basename='remote-mcp-config')

app_name = 'mcp_tools' # Optional: for namespacing URLs if needed later

urlpatterns = [
    # New URL for pinging Remote MCP Configurations (must be before router.urls to avoid conflict)
    path('remote-configs/ping/', views.RemoteMCPConfigPingView.as_view(), name='remote-mcp-config-ping'),
    # Include router URLs directly for RemoteMCPConfigViewSet
    path('', include(router.urls)),
    # New generic endpoint for calling any registered MCP tool
    path('call/', views.MCPToolRunnerView.as_view(), name='mcp_call_tool'),
]