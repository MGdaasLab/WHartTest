import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'; // 导入路由创建函数、HTML5 History 模式和路由类型定义。
import { useAuthStore } from '../store/authStore.ts'; // 导入认证 store 获取函数，用于守卫中读取登录态。
import MainLayout from '../layouts/MainLayout.vue'; // 导入主布局组件，作为受保护页面的统一壳层。
import LoginView from '../views/LoginView.vue'; // 导入登录页面组件。
import RegisterView from '../views/RegisterView.vue'; // 导入注册页面组件。
import DashboardView from '../views/DashboardView.vue'; // 导入首页仪表盘页面组件。
import UserManagementView from '../views/UserManagementView.vue'; // 导入用户管理页面组件。
import OrganizationManagementView from '../views/OrganizationManagementView.vue'; // 导入组织管理页面组件。
import PermissionManagementView from '../views/PermissionManagementView.vue'; // 导入权限管理页面组件。
import ProjectManagementView from '../views/ProjectManagementView.vue'; // 导入项目管理页面组件。
import TestCaseManagementView from '../views/TestCaseManagementView.vue'; // 导入测试用例管理页面组件。
import TestSuiteManagementView from '../views/TestSuiteManagementView.vue'; // 导入测试套件管理页面组件。
import TestExecutionHistoryView from '../views/TestExecutionHistoryView.vue'; // 导入测试执行历史页面组件。
import LlmConfigManagementView from '@/features/langgraph/views/LlmConfigManagementView.vue'; // 导入 LLM 配置管理页面组件。
import LangGraphChatView from '@/features/langgraph/views/LangGraphChatView.vue'; // 导入 LangGraph 聊天页面组件。
import KnowledgeManagementView from '@/features/knowledge/views/KnowledgeManagementView.vue'; // 导入知识库管理页面组件。
import ApiKeyManagementView from '@/views/ApiKeyManagementView.vue'; // 导入 API Key 管理页面组件。
import RemoteMcpConfigManagementView from '@/views/RemoteMcpConfigManagementView.vue'; // 导入远程 MCP 配置管理页面组件。
import RequirementManagementView from '@/features/requirements/views/RequirementManagementView.vue'; // 导入需求管理页面组件。
import DocumentDetailView from '@/features/requirements/views/DocumentDetailView.vue'; // 导入需求文档详情页面组件。
import SpecializedReportView from '@/features/requirements/views/SpecializedReportView.vue'; // 导入专项分析报告页面组件。
import SkillsManagementView from '@/features/skills/views/SkillsManagementView.vue'; // 导入 Skills 管理页面组件。
import TemplateManagementView from '@/features/testcase-templates/views/TemplateManagementView.vue'; // 导入用例模板管理页面组件。
import UiAutomationView from '@/features/ui-automation/views/UiAutomationView.vue'; // 导入 UI 自动化页面组件。
import TraceDetailView from '@/features/ui-automation/views/TraceDetail.vue'; // 导入 UI 自动化 Trace 详情页面组件。
import TaskCenterView from '@/features/task-center/views/TaskCenterView.vue'; // 导入任务中心视图

const routes: Array<RouteRecordRaw> = [ // 声明路由表数组，类型约束为 RouteRecordRaw。
  {
    path: '/login', // 定义登录页访问路径。
    name: 'Login', // 定义登录路由名称，便于命名跳转。
    component: LoginView // 指定该路由渲染的页面组件。
  },
  {
    path: '/register', // 定义注册页访问路径。
    name: 'Register', // 定义注册路由名称。
    component: RegisterView // 指定注册路由对应组件。
  },
  {
    path: '/', // 定义主应用根路径。
    component: MainLayout, // 指定根路径使用主布局组件承载子页面。
    meta: { requiresAuth: true }, // 标记该分支路由默认需要认证。
    redirect: '/dashboard', // 访问根路径时默认重定向到仪表盘。
    children: [
      {
        path: 'dashboard', // 定义仪表盘子路径（最终为 /dashboard）。
        name: 'Dashboard', // 定义仪表盘路由名称。
        component: DashboardView, // 指定仪表盘组件。
      },
      {
        path: 'projects', // 定义项目管理子路径。
        name: 'ProjectManagement', // 定义项目管理路由名称。
        component: ProjectManagementView, // 指定项目管理页面组件。
      },
      {
        path: 'users', // 定义用户管理子路径。
        name: 'UserManagement', // 定义用户管理路由名称。
        component: UserManagementView, // 指定用户管理页面组件。
      },
      {
        path: 'organizations', // 定义组织管理子路径。
        name: 'OrganizationManagement', // 定义组织管理路由名称。
        component: OrganizationManagementView, // 指定组织管理页面组件。
      },
      {
        path: 'permissions', // 定义权限管理子路径。
        name: 'PermissionManagement', // 定义权限管理路由名称。
        component: PermissionManagementView, // 指定权限管理页面组件。
      },
      {
        path: 'testcases', // 定义测试用例管理子路径。
        name: 'TestCaseManagement', // 定义测试用例管理路由名称。
        component: TestCaseManagementView, // 指定测试用例管理页面组件。
      },
      {
        path: 'testsuites', // 定义测试套件管理子路径。
        name: 'TestSuiteManagement', // 定义测试套件管理路由名称。
        component: TestSuiteManagementView, // 指定测试套件管理页面组件。
      },
      {
        path: 'test-executions', // 定义测试执行历史子路径。
        name: 'TestExecutionHistory', // 定义测试执行历史路由名称。
        component: TestExecutionHistoryView, // 指定测试执行历史页面组件。
      },
      {
        path: 'llm-configs', // 定义 LLM 配置管理子路径。
        name: 'LlmConfigManagement', // 定义 LLM 配置管理路由名称。
        component: LlmConfigManagementView, // 指定 LLM 配置管理页面组件。
      },
      {
        path: 'langgraph-chat', // 定义 LangGraph 聊天子路径。
        name: 'LangGraphChat', // 定义 LangGraph 聊天路由名称。
        component: LangGraphChatView, // 指定 LangGraph 聊天页面组件。
      },
      {
        path: 'knowledge-management', // 定义知识库管理子路径。
        name: 'KnowledgeManagement', // 定义知识库管理路由名称。
        component: KnowledgeManagementView, // 指定知识库管理页面组件。
      },
      {
        path: 'api-keys', // 定义 API Key 管理子路径。
        name: 'ApiKeyManagement', // 定义 API Key 管理路由名称。
        component: ApiKeyManagementView, // 指定 API Key 管理页面组件。
      },
      {
        path: 'remote-mcp-configs', // 定义远程 MCP 配置管理子路径。
        name: 'RemoteMcpConfigManagement', // 定义远程 MCP 配置管理路由名称。
        component: RemoteMcpConfigManagementView, // 指定远程 MCP 配置管理页面组件。
      },
      {
        path: 'requirements', // 定义需求管理子路径。
        name: 'RequirementManagement', // 定义需求管理路由名称。
        component: RequirementManagementView, // 指定需求管理页面组件。
      },
      {
        path: 'requirements/:id', // 定义需求文档详情动态路径，:id 为文档主键参数。
        name: 'DocumentDetail', // 定义文档详情路由名称。
        component: DocumentDetailView, // 指定文档详情页面组件。
      },
      {
        path: 'requirements/:id/report', // 定义需求评审报告动态路径。
        name: 'ReportDetail', // 定义评审报告路由名称。
        component: SpecializedReportView, // 指定评审报告页面组件。
      },
      {
        path: 'skills', // 定义 Skills 管理子路径。
        name: 'SkillsManagement', // 定义 Skills 管理路由名称。
        component: SkillsManagementView, // 指定 Skills 管理页面组件。
      },
      {
        path: 'testcase-templates', // 定义用例模板管理子路径。
        name: 'TemplateManagement', // 定义用例模板管理路由名称。
        component: TemplateManagementView, // 指定用例模板管理页面组件。
      },
      {
        path: 'ui-automation', // 定义 UI 自动化子路径。
        name: 'UiAutomation', // 定义 UI 自动化路由名称。
        component: UiAutomationView, // 指定 UI 自动化页面组件。
      },
      {
        path: 'ui-automation/trace/:id', // 定义 Trace 详情动态路径，:id 为 trace 记录标识。
        name: 'TraceDetail', // 定义 Trace 详情路由名称。
        component: TraceDetailView, // 指定 Trace 详情页面组件。
        props: true, // 将路由参数以 props 形式传入组件，降低组件对 $route 的耦合。
      },
      {
        path: 'task-center', // 任务中心
        name: 'TaskCenter',
        component: TaskCenterView,
      },
      // 其他受保护的子路由可以加在这里
    ]
  },
  // Catch-all 路由：捕获所有未匹配的路径，重定向到首页
  {
    path: '/:pathMatch(.*)*', // 定义兜底通配路径，匹配所有未命中的 URL。
    name: 'NotFound', // 定义兜底路由名称。
    redirect: '/dashboard' // 将未知路径统一重定向到仪表盘页面。
  }
]; // 路由表定义结束。

const router = createRouter({ // 创建路由实例，供 Vue 应用注册使用。
  history: createWebHistory(import.meta.env.BASE_URL), // 使用 history 模式，并以 Vite 配置的 BASE_URL 作为基路径。
  routes // 注入前面定义好的路由表。
}); // 路由实例创建完成。

router.beforeEach((to, _from, next) => { // 注册全局前置守卫，在每次导航确认前执行鉴权流程。
  console.log('[Router Guard] 路由守卫触发:', { path: to.path, name: to.name, matched: to.matched.length }); // 输出当前目标路由调试信息。

  const authStore = useAuthStore(); // 获取认证 store，用于读取/更新登录状态。

  // 确保在每次导航前检查认证状态，特别是对于首次加载或刷新
  if (!authStore.isAuthenticated && typeof localStorage !== 'undefined') { // 当内存态未登录且浏览器环境可用时进入状态恢复分支。
    authStore.checkAuthStatus(); // 从本地持久化信息恢复登录态，避免刷新后误判未登录。
  }

  const isLoggedIn = authStore.isAuthenticated; // 读取当前是否已登录，作为路由放行判定依据。
  console.log('[Router Guard] 认证状态:', { isLoggedIn, toName: to.name }); // 输出鉴权判定前的状态日志。

  // 不需要认证的白名单路由
  const publicRoutes = ['Login', 'Register']; // 声明公开路由名称白名单。
  const isPublicRoute = publicRoutes.includes(to.name as string); // 判断目标路由是否属于公开白名单。

  if (!isLoggedIn && !isPublicRoute) { // 未登录且访问受保护路由时触发重定向。
    // 未登录且不是公开路由，重定向到登录页
    console.log('[Router Guard] 未登录，重定向到登录页'); // 输出未登录拦截日志。
    next({ name: 'Login', query: { redirect: to.fullPath } }); // 跳转登录页并携带原目标地址以支持登录后回跳。
  } else if (isLoggedIn && isPublicRoute) { // 已登录但访问登录/注册页时触发反向重定向。
    // 已登录但访问登录/注册页，重定向到首页
    console.log('[Router Guard] 已登录，重定向到首页'); // 输出已登录访问公开页的重定向日志。
    next({ name: 'Dashboard' }); // 直接跳到仪表盘，避免重复登录/注册操作。
  } else {
    console.log('[Router Guard] 放行'); // 输出路由放行日志。
    next(); // 满足条件时继续当前导航流程。
  }
}); // 全局前置守卫定义结束。

export default router; // 导出路由实例，供 main.ts 注册到 Vue 应用。
