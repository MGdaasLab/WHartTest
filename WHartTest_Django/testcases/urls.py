from rest_framework_nested import routers
from .views import TestCaseViewSet

# 此处的 router 期望从主 urls.py 或 projects.urls.py 中传递或构建
# 为了模块化，通常在主 urls.py 中处理顶层路由和嵌套路由的注册
# 这里我们只定义 TestCaseViewSet 如何被注册到一个已有的 projects_router

# projects_router = routers.NestedSimpleRouter(parent_router, r'projects', lookup='project')
# projects_router.register(r'testcases', TestCaseViewSet, basename='project-testcases')
# urlpatterns = projects_router.urls

# 更简洁的方式是，这个文件只导出需要注册到父级路由器的视图集和前缀
# 然后在父级 urls.py 中进行实际的嵌套注册。

# 暂定方案：直接创建一个 router 并注册，然后在主 urls.py 中 include 这个 router 的 urls，
# 但需要确保 project_pk 的传递和视图中 get_queryset 的正确性。
# 为了与计划中提到的 NestedSimpleRouter 保持一致，我们假设这个文件
# 会被 include 到一个已经处理了 project 嵌套的上下文中。

# 最常见的做法是在主 URLConf (或 app URLConf) 中创建嵌套路由。
# 此文件可以保持简单，只定义本 app 内的路由模式，如果它们不是嵌套的。
# 但由于我们明确需要 /projects/{project_pk}/testcases/，
# 嵌套路由的注册逻辑主要在更高层级的 urls.py 文件中。

# 因此，这个文件可能只是一个占位，或者定义非嵌套的 testcase 路由（如果未来需要）。
# 按照我们的计划，TestCaseViewSet 是嵌套的，所以其路由注册将在主 URL 文件中完成。
# 这个文件可以暂时为空，或者包含一个简单的 router 实例，
# 但实际的嵌套注册会在 wharttest_django/urls.py 中进行。

# 为了让 testcases 应用有一个自己的 urls.py，并且能够被 include，
# 我们可以创建一个空的 urlpatterns 列表，或者一个简单的 router，
# 实际的嵌套路由注册将在主 urls.py 中完成。

# 方案：我们在这里不直接使用 NestedSimpleRouter，
# 而是创建一个普通的 SimpleRouter，然后在主 urls.py 中处理嵌套。
# 或者，更推荐的做法是，此文件不定义 urlpatterns，
# 而是让主 urls.py 直接导入 TestCaseViewSet 并使用 NestedSimpleRouter。

# 让我们采用更清晰的方式：此文件不产生 urlpatterns，
# 而是让主 urls.py 负责 TestCaseViewSet 的嵌套路由注册。
# 如果将来 testcases 应用有非嵌套的独立路由，可以加在这里。
# 目前，为了让 include('testcases.urls') 能工作，我们至少需要一个 urlpatterns 列表。

app_name = 'testcases'
urlpatterns = [
    # TestCaseViewSet 的路由将通过 Nested Routers 在主 urls.py 中定义
]

# 如果我们希望在 wharttest_django/urls.py 中使用 include('testcases.urls')
# 并且让 testcases.urls.py 自己定义其在 /projects/{project_pk}/testcases 下的路由，
# 这会比较复杂，因为 SimpleRouter 本身不直接支持从 URL 中提取父级 lookup。
# Nested Routers 更适合这种情况，并且通常在父级 router 声明的地方使用。

# 因此，最合适的做法是：
# 1. testcases/views.py 定义 TestCaseViewSet。
# 2. wharttest_django/urls.py (或 projects/urls.py 如果项目路由在那里定义)
#    导入 TestCaseViewSet 并使用 NestedSimpleRouter 将其注册到 projects 路由下。
# 3. testcases/urls.py 可以为空，或者用于将来可能的非嵌套路由。

# 为了保持结构，我们创建一个空的 urlpatterns。
# 实际的路由将在主 urls.py 中使用 NestedRouter 定义。