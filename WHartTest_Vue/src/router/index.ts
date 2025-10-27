import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import { useAuthStore } from '../store/authStore.ts'; // 导入 authStore
import MainLayout from '../layouts/MainLayout.vue'; // 导入主布局组件
import LoginView from '../views/LoginView.vue'; // 显式导入 LoginView
import RegisterView from '../views/RegisterView.vue'; // 导入 RegisterView
import DashboardView from '../views/DashboardView.vue'; // 显式导入 DashboardView
import UserManagementView from '../views/UserManagementView.vue'; // 导入用户管理页面
import OrganizationManagementView from '../views/OrganizationManagementView.vue'; // 导入组织管理页面
import PermissionManagementView from '../views/PermissionManagementView.vue'; // 导入权限管理页面
import ProjectManagementView from '../views/ProjectManagementView.vue'; // 导入项目管理页面
import TestCaseManagementView from '../views/TestCaseManagementView.vue'; // 导入用例管理页面
import TestSuiteManagementView from '../views/TestSuiteManagementView.vue'; // 导入测试套件管理页面
import TestExecutionHistoryView from '../views/TestExecutionHistoryView.vue'; // 导入执行历史页面
import LlmConfigManagementView from '@/features/langgraph/views/LlmConfigManagementView.vue'; // 导入 LLM 配置管理视图
import LangGraphChatView from '@/features/langgraph/views/LangGraphChatView.vue'; // 导入 LLM 聊天视图
import KnowledgeManagementView from '@/features/knowledge/views/KnowledgeManagementView.vue'; // 导入知识库管理视图
import ApiKeyManagementView from '@/views/ApiKeyManagementView.vue'; // 导入 API Key 管理视图
import RemoteMcpConfigManagementView from '@/views/RemoteMcpConfigManagementView.vue'; // 导入远程MCP配置管理视图
import RequirementManagementView from '@/features/requirements/views/RequirementManagementView.vue'; // 导入需求管理视图
import DocumentDetailView from '@/features/requirements/views/DocumentDetailView.vue'; // 导入文档详情视图
import ReportDetailView from '@/features/requirements/views/ReportDetailView.vue'; // 导入报告详情视图

const routes: Array<RouteRecordRaw> = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView
  },
  {
    path: '/register',
    name: 'Register',
    component: RegisterView
  },
  {
    path: '/', // 主应用布局的根路径
    component: MainLayout,
    meta: { requiresAuth: true },
    redirect: '/projects', // 默认重定向到项目管理
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: DashboardView,
      },
      {
        path: 'projects',
        name: 'ProjectManagement',
        component: ProjectManagementView,
      },
      {
        path: 'users',
        name: 'UserManagement',
        component: UserManagementView,
      },
      {
        path: 'organizations',
        name: 'OrganizationManagement',
        component: OrganizationManagementView,
      },
      {
        path: 'permissions',
        name: 'PermissionManagement',
        component: PermissionManagementView,
      },
      {
        path: 'testcases',
        name: 'TestCaseManagement',
        component: TestCaseManagementView,
      },
      {
        path: 'testsuites',
        name: 'TestSuiteManagement',
        component: TestSuiteManagementView,
      },
      {
        path: 'test-executions',
        name: 'TestExecutionHistory',
        component: TestExecutionHistoryView,
      },
      {
        path: 'llm-configs', // LLM 配置管理
        name: 'LlmConfigManagement',
        component: LlmConfigManagementView,
      },
      {
        path: 'langgraph-chat', // LLM 对话
        name: 'LangGraphChat',
        component: LangGraphChatView,
      },
      {
        path: 'knowledge-management', // 知识库管理
        name: 'KnowledgeManagement',
        component: KnowledgeManagementView,
      },
      {
        path: 'api-keys', // API Key 管理
        name: 'ApiKeyManagement',
        component: ApiKeyManagementView,
      },
      {
        path: 'remote-mcp-configs', // 远程MCP配置管理
        name: 'RemoteMcpConfigManagement',
        component: RemoteMcpConfigManagementView,
      },
      {
        path: 'requirements', // 需求管理
        name: 'RequirementManagement',
        component: RequirementManagementView,
      },
      {
        path: 'requirements/:id', // 文档详情
        name: 'DocumentDetail',
        component: DocumentDetailView,
      },
      {
        path: 'requirements/:id/report', // 评审报告详情
        name: 'ReportDetail',
        component: ReportDetailView,
      },
      // 其他受保护的子路由可以加在这里
    ]
  },
  // 可以添加一个 404 页面
  // { path: '/:pathMatch(.*)*', name: 'NotFound', component: NotFoundView }
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
});

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore();

  // 确保在每次导航前检查认证状态，特别是对于首次加载或刷新
  if (!authStore.isAuthenticated && typeof localStorage !== 'undefined') {
    authStore.checkAuthStatus();
  }

  const isLoggedIn = authStore.isAuthenticated;

  if (to.meta.requiresAuth && !isLoggedIn) {
    // 如果目标路由需要认证但用户未登录，重定向到登录页
    next({ name: 'Login', query: { redirect: to.fullPath } });
  } else if ((to.name === 'Login' || to.name === 'Register') && isLoggedIn) {
    // 如果用户已登录并尝试访问登录页或注册页，重定向到项目管理
    next({ name: 'ProjectManagement' });
  } else if (to.path === '/' && isLoggedIn) {
    // 如果用户已登录并访问根路径，重定向到项目管理
    next({ name: 'ProjectManagement' });
  } else if (to.path === '/' && !isLoggedIn) {
    // 如果用户未登录并访问根路径，重定向到登录页
    next({ name: 'Login' });
  }
  else {
    next();
  }
});

export default router;