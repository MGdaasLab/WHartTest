"""
wharttest_django 项目的 URL 路由配置。

`urlpatterns` 用于将 URL 路径分发到对应视图。
更多说明见：
https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

# 导入 Django 后台站点对象。
from django.contrib import admin


# 导入 path/include，用于声明 URL 与组合子路由。
from django.urls import path, include

# 导入项目配置，后续用于读取 MEDIA/STATIC 设置。
from django.conf import settings

# 导入开发环境静态路由辅助函数。
from django.conf.urls.static import static

# 导入 DRF 默认路由器。
from rest_framework.routers import DefaultRouter

# 导入 DRF 嵌套路由器。
from rest_framework_nested.routers import NestedSimpleRouter



# 导入 JWT 刷新视图。
from rest_framework_simplejwt.views import TokenRefreshView

# 导入自定义 token 获取视图。
from accounts.views import MyTokenObtainPairView

# 导入项目视图集。
from projects.views import ProjectViewSet

# 导入测试相关视图集。
from testcases.views import (
    TestCaseViewSet,
    TestCaseModuleViewSet,
    TestSuiteViewSet,
    TestExecutionViewSet,
)

# 导入技能视图集。
from skills.views import SkillViewSet

# 导入 OpenAPI schema 与文档视图。
from task_center.views import ScheduledTaskViewSet, TaskExecutionViewSet as TaskExecViewSet  # 导入任务中心视图集
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# 创建主路由器实例。
router = DefaultRouter()

# 注册项目一级资源路由。
router.register(r"projects", ProjectViewSet, basename="project")

# 创建项目维度嵌套路由器。
projects_router = NestedSimpleRouter(router, r"projects", lookup="project")

# 注册项目下测试用例路由。
projects_router.register(r"testcases", TestCaseViewSet, basename="project-testcases")

# 注册项目下用例模块路由。
projects_router.register(
    r"testcase-modules",
    TestCaseModuleViewSet,
    basename="project-testcase-modules",
)

# 注册项目下测试套件路由。
projects_router.register(
    r"test-suites", TestSuiteViewSet, basename="project-test-suites"
)

# 注册项目下测试执行路由。
projects_router.register(
    r"test-executions",
    TestExecutionViewSet,
    basename="project-test-executions",
)

# 注册项目下技能路由。
projects_router.register(r"skills", SkillViewSet, basename="project-skills")
projects_router.register(r'scheduled-tasks', ScheduledTaskViewSet, basename='project-scheduled-tasks')
projects_router.register(r'task-executions', TaskExecViewSet, basename='project-task-executions')

# 定义根 URL 路由表。
urlpatterns = [
    # 挂载 Django Admin。
    path("admin/", admin.site.urls),
    # 挂载 JWT 获取接口。
    path("api/token/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    # 挂载 JWT 刷新接口。
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # 挂载账户模块路由。
    path("api/accounts/", include("accounts.urls")),
    # 旧 projects include 保留注释历史（当前不启用）。
    # 如需启用旧版 projects 路由，可在此恢复对应 include 配置。
    # 挂载主路由器自动生成的一级 REST 路由。
    path("api/", include(router.urls)),
    # 挂载项目嵌套路由。
    path("api/", include(projects_router.urls)),
    # 挂载 LangGraph 路由。
    path("api/lg/", include("langgraph_integration.urls")),
    # 挂载 MCP 工具路由。
    path("api/mcp_tools/", include("mcp_tools.urls")),
    # 挂载 API Keys 路由。
    path("api/", include("api_keys.urls")),
    # 挂载知识库路由。
    path("api/knowledge/", include("knowledge.urls")),
    # 挂载提示词管理路由。
    path("api/prompts/", include("prompts.urls")),
    # 挂载需求评审路由。
    path("api/requirements/", include("requirements.urls")),
    # 挂载智能编排路由。
    path("api/orchestrator/", include("orchestrator_integration.urls")),
    # 挂载用例模板路由。
    path("api/", include("testcase_templates.urls")),
    # 挂载 UI 自动化路由。
    path("api/ui-automation/", include("ui_automation.urls")),
    # 挂载 OpenAPI schema 接口。
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # 挂载 Swagger UI。
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # 挂载 ReDoc 文档。
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

# 追加媒体文件访问路由（开发/容器环境使用）。
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# 追加静态文件访问路由。
urlpatterns += static(
    settings.STATIC_URL,
    document_root=settings.STATIC_ROOT if hasattr(settings, "STATIC_ROOT") else None,
)
