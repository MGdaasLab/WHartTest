from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db.models import Q # For complex queries
from asgiref.sync import sync_to_async # Import sync_to_async

from projects.models import Project # Assuming your Project model is in the 'projects' app
from .serializers import MCPProjectListSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication # Import JWT authentication
from .models import RemoteMCPConfig
from .serializers import RemoteMCPConfigSerializer
# import urllib.request # No longer needed
# import urllib.parse # No longer needed
# import urllib.error # No longer needed
import json
import asyncio # 确保导入 asyncio
import logging # 导入 logging 模块
# from fastmcp import Client # No longer directly used here
# from fastmcp.client.transports import StreamableHttpTransport # No longer directly used here
from langchain_mcp_adapters.client import MultiServerMCPClient # Import LangGraph's MCP client
from wharttest_django.permissions import HasModelPermission

logger = logging.getLogger(__name__) # 获取 logger 实例

# --- Tool Implementation Functions ---
def _get_project_list_tool(request_user, arguments: dict):
    """
    Implements the logic for the 'get_project_list' tool.
    'arguments' is currently unused but reserved for future parameters like filtering or pagination.
    """
    # Ensure request_user is authenticated, though permission_classes on the view should handle this.
    if not request_user or not request_user.is_authenticated:
        # This case should ideally not be hit if permission_classes are correctly enforced.
        raise PermissionError("User is not authenticated.")

    accessible_projects = Project.objects.filter(
        Q(creator=request_user) | Q(members=request_user)
    ).distinct().order_by('-created_at')

    serializer = MCPProjectListSerializer(accessible_projects, many=True)
    return serializer.data

# --- Tool Registry ---
# Maps tool names to their implementation functions.
# Each function should accept 'request_user' and 'arguments' (a dict).
TOOL_REGISTRY = {
    "get_project_list": _get_project_list_tool,
    # Future tools can be added here:
    # "get_project_details": _get_project_details_tool,
}

# --- MCP Tool Runner View ---
class MCPToolRunnerView(APIView):
    """
    A generic view to run MCP tools based on the provided tool name and arguments.
    This view acts as the entry point for MCP tool calls to this Django application.
    """
    authentication_classes = [JWTAuthentication] # Use JWT authentication
    permission_classes = [permissions.IsAuthenticated] # Only auth, custom permission in post method

    def post(self, request, *args, **kwargs):
        # 检查MCP工具执行权限 (这里可以定义具体需要的权限)
        if not request.user.has_perm('mcp_tools.add_remotemcpconfig'):
            return Response({
                "status": "error", "code": status.HTTP_403_FORBIDDEN,
                "message": "You do not have permission to execute MCP tools.",
                "data": {}, "errors": {"permission": ["mcp_tools.add_remotemcpconfig required"]}
            }, status=status.HTTP_403_FORBIDDEN)
            
        tool_name = request.data.get('name')
        tool_arguments = request.data.get('arguments', {}) # Default to empty dict if not provided

        if not tool_name:
            return Response({
                "status": "error", "code": status.HTTP_400_BAD_REQUEST,
                "message": "Tool name ('name') is required in the request body.",
                "data": {}, "errors": {"name": ["This field is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        tool_function = TOOL_REGISTRY.get(tool_name)

        if not tool_function:
            return Response({
                "status": "error", "code": status.HTTP_404_NOT_FOUND,
                "message": f"Tool '{tool_name}' not found.",
                "data": {}, "errors": {"name": [f"Tool '{tool_name}' is not registered."]}
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            # Pass the authenticated user (request.user) and arguments to the tool function
            result_data = tool_function(request.user, tool_arguments)

            # The MCP CallToolResponseSchema expects a list of "content items".
            # For simplicity, we are directly returning the tool's data.
            # To be strictly compliant, we might need to wrap this:
            # "content": [{"type": "application/json" or "text", "text": json.dumps(result_data)}]
            # However, for internal use by a LangGraph agent that knows how to parse this,
            # returning data directly in the "data" field of our unified response is often more practical.
            return Response({
                "status": "success", "code": status.HTTP_200_OK,
                "message": f"Tool '{tool_name}' executed successfully.",
                "data": result_data
            }, status=status.HTTP_200_OK)

        except PermissionError as pe: # Catch specific permission errors from tool functions
            return Response({
                "status": "error", "code": status.HTTP_403_FORBIDDEN,
                "message": f"Permission denied while executing tool '{tool_name}': {str(pe)}",
                "data": {}, "errors": {tool_name: [str(pe)]}
            }, status=status.HTTP_403_FORBIDDEN)

        except Exception as e:
            # In a production environment, you'd want to log this exception.
            # logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return Response({
                "status": "error", "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"An unexpected error occurred while executing tool '{tool_name}'.",
                "data": {}, "errors": {tool_name: [str(e)]} # Avoid exposing too much detail in prod
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from rest_framework import viewsets
from api_keys.permissions import IsOwnerOrAdmin as APIKeyIsOwnerOrAdmin # Original for API keys
from .permissions import IsOwnerOrAdmin # Local version supporting both user/owner fields

class RemoteMCPConfigPingView(APIView):
    """
    API endpoint to check the connectivity status of a Remote MCP Configuration.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated] # Only auth, custom permission in post method

    async def dispatch(self, request, *args, **kwargs):
        self.request = request
        self.args = args
        self.kwargs = kwargs
        request = await sync_to_async(self.initialize_request)(request, *args, **kwargs)
        self.request = request
        self.headers = await sync_to_async(lambda: self.default_response_headers)()

        try:
            await sync_to_async(self.initial)(request, *args, **kwargs)

            if request.method.lower() in self.http_method_names:
                handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
            else:
                handler = self.http_method_not_allowed

            response = await handler(request, *args, **kwargs)

        except Exception as exc:
            response = await sync_to_async(self.handle_exception)(exc)

        self.response = await sync_to_async(self.finalize_response)(request, response, *args, **kwargs)
        return self.response

    async def post(self, request, *args, **kwargs):
        # 检查MCP配置管理权限 (异步)
        has_permission = await sync_to_async(request.user.has_perm)('mcp_tools.view_remotemcpconfig')
        if not has_permission:
            return Response({
                "status": "error", "code": status.HTTP_403_FORBIDDEN,
                "message": "You do not have permission to ping MCP configurations.",
                "data": {}, "errors": {"permission": ["mcp_tools.view_remotemcpconfig required"]}
            }, status=status.HTTP_403_FORBIDDEN)
            
        logger.info("Entering RemoteMCPConfigPingView.post method.")
        config_id = request.data.get('config_id')
        logger.info(f"Received config_id: {config_id}")

        if not config_id:
            logger.warning("Config ID not provided in the request.")
            return Response({
                "status": "error", "code": status.HTTP_400_BAD_REQUEST,
                "message": "Config ID ('config_id') is required in the request body.",
                "data": {}, "errors": {"config_id": ["This field is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            logger.info(f"Attempting to retrieve RemoteMCPConfig with ID: {config_id} for user: {request.user.username}")
            config = await sync_to_async(RemoteMCPConfig.objects.get)(id=config_id, owner=request.user)
            logger.info(f"Successfully retrieved RemoteMCPConfig: {config.name} (ID: {config.id})")
        except RemoteMCPConfig.DoesNotExist:
            logger.error(f"Remote MCP Configuration with ID {config_id} not found or user {request.user.username} does not have permission.")
            return Response({
                "status": "error", "code": status.HTTP_404_NOT_FOUND,
                "message": "Remote MCP Configuration not found or you do not have permission to access it.",
                "data": {}, "errors": {"config_id": ["Configuration not found."]}
            }, status=status.HTTP_404_NOT_FOUND)

        # Use the URL directly from the retrieved config
        # The MultiServerMCPClient and underlying FastMCP client will handle appending /mcp if necessary based on the transport.
        target_mcp_url = config.url
        logger.info(f"Using MCP server URL from config: {target_mcp_url}")

        try:
            # Prepare configuration for MultiServerMCPClient
            server_config_key = config.name or "target_server" # Use config name or a default key

            client_config = {
                server_config_key: {
                    "url": target_mcp_url, # Use the URL directly from the config
                    # Correct the transport string if it's the hyphenated version
                    "transport": (config.transport or "sse").replace('-', '_'),
                }
            }

            # Add headers if they exist and are a dictionary
            if config.headers and isinstance(config.headers, dict) and config.headers:
                client_config[server_config_key]["headers"] = config.headers
                logger.info(f"Using custom headers for MultiServerMCPClient: {config.headers}")
            else:
                logger.info("No custom headers provided or headers are not a valid dictionary for MultiServerMCPClient.")

            logger.info(f"Attempting to connect to MCP server using MultiServerMCPClient with config: {client_config}")

            # Instantiate the MultiServerMCPClient
            # Note: MultiServerMCPClient itself is not an async context manager.
            # Its methods like get_tools are async.
            mcp_client = MultiServerMCPClient(client_config)

            # Use get_tools() as a way to "ping" or check connectivity and basic server health.
            # This will attempt to connect and fetch the list of tools from the /mcp/tools endpoint.
            tools_list = await mcp_client.get_tools() # This is an async call
            tools_count = len(tools_list)
            logger.info(f"Successfully connected to MCP server at {target_mcp_url} and retrieved {tools_count} tools.")

            return Response({
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": f"MCP server at {target_mcp_url} is online and accessible (retrieved {tools_count} tools).",
                "data": {
                    "status": "online",
                    "url": target_mcp_url,
                    "tools_count": tools_count,
                    "tools": [tool.name for tool in tools_list if hasattr(tool, 'name')] # Include names of the tools
                }
            }, status=status.HTTP_200_OK)

        except ImportError:
            logger.error("langchain-mcp-adapters library is not installed. Please install it to use this feature.", exc_info=True)
            return Response({
                "status": "error", "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Server configuration error: langchain-mcp-adapters library not found.",
                "data": {"status": "error", "url": target_mcp_url},
                "errors": {"mcp_check": ["langchain-mcp-adapters library not installed."]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Error connecting to MCP server {target_mcp_url} using MultiServerMCPClient: {e}", exc_info=True)
            error_message = f"Failed to connect or communicate with MCP server at {target_mcp_url}: {type(e).__name__} - {str(e)}"
            return Response({
                "status": "error", "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": error_message,
                "data": {"status": "error", "url": target_mcp_url},
                "errors": {"mcp_check": [f"{type(e).__name__}: {str(e)}"]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RemoteMCPConfigViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Remote MCP Configurations to be viewed or edited.
    Users can only see and manage their own Remote MCP Configurations.
    Admins can see and manage all Remote MCP Configurations.
    """
    serializer_class = RemoteMCPConfigSerializer
    permission_classes = [permissions.IsAuthenticated, HasModelPermission, IsOwnerOrAdmin]

    def get_queryset(self):
        """
        This view should return a list of all the Remote MCP Configurations
        for the currently authenticated user.
        """
        user = self.request.user
        # Ensure that even staff users (admins) only see their own configurations
        return RemoteMCPConfig.objects.filter(owner=user).order_by('-created_at')

    def perform_create(self, serializer):
        """
        Automatically associates the Remote MCP Configuration with the creating user.
        """
        serializer.save(owner=self.request.user)
