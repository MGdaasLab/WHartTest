"""
URL configuration for wharttest_django project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include # Added include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedSimpleRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from accounts.views import MyTokenObtainPairView # 修改为导入自定义视图
from projects.views import ProjectViewSet # 导入 ProjectViewSet
from testcases.views import (
    TestCaseViewSet, TestCaseModuleViewSet,
    TestSuiteViewSet, TestExecutionViewSet
)  # 导入 TestCase、TestCaseModule、TestSuite 和 TestExecution 视图集
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')

projects_router = NestedSimpleRouter(router, r'projects', lookup='project')
projects_router.register(r'testcases', TestCaseViewSet, basename='project-testcases')
projects_router.register(r'testcase-modules', TestCaseModuleViewSet, basename='project-testcase-modules')
projects_router.register(r'test-suites', TestSuiteViewSet, basename='project-test-suites')
projects_router.register(r'test-executions', TestExecutionViewSet, basename='project-test-executions')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'), # 修改为使用自定义视图
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/accounts/', include('accounts.urls')), # Added accounts urls
    # path('api/projects/', include('projects.urls')), # 注释掉旧的 projects.urls include
    path('api/', include(router.urls)), # 包含主 router 的 URL
    path('api/', include(projects_router.urls)), # 包含嵌套的 testcases router 的 URL
    path('api/lg/', include('langgraph_integration.urls')), # LangGraph Integration URLs
    path('api/mcp_tools/', include('mcp_tools.urls')), # MCP Tools URLs
    path('api/', include('api_keys.urls')), # API Keys URLs
    path('api/knowledge/', include('knowledge.urls')), # Knowledge Base URLs
    path('api/prompts/', include('prompts.urls')), # 提示词管理 URLs
    path('api/requirements/', include('requirements.urls')), # 需求评审管理 URLs
    # DRF Spectacular - OpenAPI schema and docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Optional UI:
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# 开发环境下提供媒体文件访问
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
