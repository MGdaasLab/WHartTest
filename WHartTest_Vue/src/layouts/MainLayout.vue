<template>
  <a-layout class="main-layout">
    <!-- 顶部导航栏 -->
    <a-layout-header class="header">
      <div class="left-section">
        <div class="logo" unselectable="on">
          <img :src="brandLogoUrl" alt="WHartTest Logo" class="logo-icon" />
          <span class="logo-text">WHartTest</span>
          <img :src="brandBadgeUrl" alt="CE" class="logo-ce-icon" />
        </div>
        <div class="project-selector" v-if="showProjectSelector">
          <a-select
            v-model="selectedProjectId"
            :loading="projectStore.loading"
            :disabled="projectStore.loading"
            :placeholder="t('layout.projectPlaceholder')"
            style="width: 200px; margin-left: 10px;"
            :trigger-props="headerSelectTriggerProps"
            @change="handleProjectChange"
            @popup-visible-change="handlePopupVisibleChange"
          >
            <a-option
              v-for="option in projectStore.projectOptions"
              :key="option.value"
              :value="option.value"
              :label="option.label"
            />
          </a-select>
          <a-select
            v-if="showEnvironmentSelector"
            v-model="selectedEnvironmentId"
            :loading="environmentStore.loading"
            :placeholder="tl('选择环境')"
            style="width: 180px; margin-left: 10px;"
            :trigger-props="headerSelectTriggerProps"
            @change="handleEnvironmentChange"
            @popup-visible-change="handleEnvironmentPopupVisibleChange"
            allow-clear
          >
            <a-option
              v-for="env in environmentStore.environments"
              :key="env.id"
              :value="env.id"
              :label="env.name"
            />
          </a-select>
        </div>
        <!-- 顶部视图切换器 - 仅在用例管理页面展示 -->
        <div class="header-view-switch" v-if="isTestCaseManagementPage">
          <a-radio-group type="button" v-model="testCaseActiveView" size="medium" class="view-selector-group">
            <a-radio value="list">
              <template #default>
                <icon-list /> 列表视图
              </template>
            </a-radio>
            <a-radio value="mindmap">
              <template #default>
                <icon-relation /> 思维导图
              </template>
            </a-radio>
          </a-radio-group>
        </div>
      </div>
      <div class="user-info">
        <AppLocaleToggle />
        <button
          type="button"
          class="theme-switch-button"
          :aria-label="themeButtonLabel"
          :title="themeButtonLabel"
          @click="themeStore.toggleTheme"
        >
          <icon-sun-fill v-if="themeStore.isBlack" class="theme-switch-icon" />
          <icon-moon-fill v-else class="theme-switch-icon" />
        </button>
        <!-- 版本号显示 -->
        <a-popover v-if="hasUpdate" position="bottom" trigger="hover" content-class="version-popover">
          <a 
            class="version-badge update-available" 
            :href="versionInfo?.releaseUrl || 'https://github.com/mgdaaslab/WHartTest/releases'"
            target="_blank"
          >
            {{ tl('当前版本:') }} {{ currentVersion }}
            <span class="update-dot"></span>
          </a>
          <template #content>
            <div class="version-update-info">
              <div class="version-update-header">
                <span class="update-title">🎉 {{ tl('新版本可用') }}</span>
                <span class="update-version">v{{ versionInfo?.latest }}</span>
              </div>
              <div class="version-update-notes" v-if="releaseNotesPreview">
                {{ releaseNotesPreview }}
              </div>
              <a 
                class="version-update-footer"
                :href="versionInfo?.releaseUrl || 'https://github.com/mgdaaslab/WHartTest/releases'"
                target="_blank"
              >
                {{ tl('点击查看完整更新日志') }}
              </a>
            </div>
          </template>
        </a-popover>
        <span v-else class="version-badge">{{ tl('当前版本:') }} {{ currentVersion }}</span>
        
        <a-avatar class="avatar">
          <span>{{ userInitial }}</span>
        </a-avatar>
        <a-dropdown trigger="click" class="user-dropdown-wrapper">
          <div class="user-dropdown">
            <span class="username">{{ username }}</span>
            <icon-down />
          </div>
          <template #content>
            <div class="dropdown-user-info">
              <div class="dropdown-username">{{ username }}</div>
              <div class="dropdown-email" v-if="user?.email">{{ user.email }}</div>
              <div class="dropdown-role" v-if="user?.is_staff">{{ tl('管理员') }}</div>
            </div>
            <a-divider style="margin: 4px 0" />
            <a-doption @click="handleLogout">{{ t('layout.logout') }}</a-doption>
          </template>
        </a-dropdown>
      </div>
    </a-layout-header>

    <a-layout class="inner-layout">
      <!-- 左侧菜单栏 -->
      <a-layout-sider
        :width="170"
        :collapsed-width="50"
        :collapsed="collapsed"
        :trigger="null"
        hide-trigger
        class="sider"
      >
        <a-menu
          :key="`main-menu-${locale}`"
          mode="vertical"
          :selected-keys="[activeMenu]"
          v-model:open-keys="openKeys"
          :auto-open-selected="true"
          :collapsed="collapsed"
          :popup-max-height="false"
          class="menu"
        >

          <a-menu-item key="dashboard">
            <template #icon><icon-home /></template>
            <router-link to="/dashboard">{{ dashboardMenuLabel }}</router-link>
          </a-menu-item>

          <a-menu-item key="projects" v-if="hasProjectsPermission">
            <template #icon><icon-storage /></template>
            <router-link to="/projects">{{ projectsMenuLabel }}</router-link>
          </a-menu-item>

          <a-menu-item key="requirements" v-if="hasRequirementsPermission">
            <template #icon><icon-file /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/requirements')">{{ requirementsMenuLabel }}</a>
          </a-menu-item>

          <a-menu-item key="api-testing" v-if="hasApiTestingPermission">
            <template #icon><icon-cloud /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/api-testing')">{{ apiTestingMenuLabel }}</a>
          </a-menu-item>

          <a-menu-item key="ui-automation" v-if="hasUiAutomationPermission">
            <template #icon><icon-computer /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/ui-automation')">{{ automationMenuLabel }}</a>
          </a-menu-item>

          <a-menu-item key="task-center" v-if="hasTaskCenterPermission">
            <template #icon><icon-schedule /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/task-center')">{{ tasksMenuLabel }}</a>
          </a-menu-item>

          <a-menu-item key="file-management" v-if="hasFileManagementPermission">
            <template #icon><icon-file /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/file-management')">{{ fileManagementMenuLabel }}</a>
          </a-menu-item>

          <!-- 测试管理子菜单 -->
          <a-sub-menu key="test-management" v-if="hasTestManagementMenuItems">
            <template #icon><icon-experiment /></template>
            <template #title>
              <span @click="handleTestManagementClick">{{ testManagementMenuLabel }}</span>
            </template>
            <a-menu-item key="testcases" v-if="hasTestcasesPermission">
              <template #icon><icon-code-block /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/testcases')">{{ caseManagementMenuLabel }}</a>
            </a-menu-item>
            <a-menu-item key="testsuites" v-if="hasTestSuitesPermission">
              <template #icon><icon-folder /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/testsuites')">{{ suitesMenuLabel }}</a>
            </a-menu-item>
            <a-menu-item key="test-executions" v-if="hasTestExecutionsPermission">
              <template #icon><icon-history /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/test-executions')">{{ executionHistoryMenuLabel }}</a>
            </a-menu-item>
          </a-sub-menu>

          <a-menu-item key="langgraph-chat" v-if="hasLangGraphChatPermission">
            <template #icon><icon-message /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/langgraph-chat')">{{ chatMenuLabel }}</a>
          </a-menu-item>

          <a-menu-item key="knowledge-management" v-if="hasKnowledgePermission">
            <template #icon><icon-book /></template>
            <a href="#" @click="checkProjectAndNavigate($event, '/knowledge-management')">{{ knowledgeMenuLabel }}</a>
          </a-menu-item>

          <!-- 系统管理子菜单 -->
          <a-sub-menu key="settings" v-if="hasSystemMenuItems">
            <template #icon><icon-settings /></template>
            <template #title>
              <span @click="handleSystemManagementClick">{{ systemMenuLabel }}</span>
            </template>
            <a-menu-item key="users" v-if="hasUsersPermission">
              <template #icon><icon-user /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/users')">{{ usersMenuLabel }}</a>
            </a-menu-item>
            <a-menu-item key="organizations" v-if="hasOrganizationsPermission">
              <template #icon><icon-apps /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/organizations')">{{ organizationsMenuLabel }}</a>
            </a-menu-item>
            <a-menu-item key="permissions" v-if="hasPermissionsPermission">
              <template #icon><icon-safe /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/permissions')">{{ permissionsMenuLabel }}</a>
            </a-menu-item>
            <a-menu-item key="llm-configs" v-if="hasLlmConfigsPermission">
              <template #icon><icon-tool /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/llm-configs')">{{ modelsMenuLabel }}</a>
            </a-menu-item>
            <a-menu-item key="api-keys" v-if="hasApiKeysPermission">
              <template #icon><icon-safe /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/api-keys')">{{ apiKeysMenuLabel }}</a>
            </a-menu-item>
            <a-menu-item key="remote-mcp-configs" v-if="hasMcpConfigsPermission">
              <template #icon><icon-cloud /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/remote-mcp-configs')">{{ mcpMenuLabel }}</a>
            </a-menu-item>
            <a-menu-item key="skills" v-if="hasSkillsPermission">
              <template #icon><icon-apps /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/skills')">{{ skillsMenuLabel }}</a>
            </a-menu-item>
            <a-menu-item key="operation-logs" v-if="hasOperationLogsPermission">
              <template #icon><icon-history /></template>
              <a href="#" @click="checkProjectAndNavigate($event, '/operation-logs')">{{ operationLogsMenuLabel }}</a>
            </a-menu-item>
          </a-sub-menu>
        </a-menu>
        <!-- 侧边栏底部收起/展开按钮 -->
        <div class="sider-footer">
          <a-button
            type="text"
            size="small"
            @click="toggleCollapse"
            class="collapse-button"
          >
            <template #icon>
              <icon-menu-fold v-if="!collapsed" />
              <icon-menu-unfold v-else />
            </template>
            <span v-if="!collapsed">{{ tl('收起') }}</span>
          </a-button>
        </div>
      </a-layout-sider>

      <!-- 右侧内容区域 -->
      <a-layout-content class="content">
        <router-view v-slot="{ Component }">
          <keep-alive include="LangGraphChat">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch, provide } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/store/authStore';
import { useProjectStore } from '@/store/projectStore';
import { useThemeStore } from '@/store/themeStore';
import { useEnvironmentStore } from '@/features/api-testing/stores/environmentStore';
import { useAppI18n } from '@/composables/useAppI18n';
import { brandLogoUrl, getPublicAssetUrl } from '@/utils/assetUrl';

const brandBadgeUrl = getPublicAssetUrl('CE.svg');
import AppLocaleToggle from '@/components/AppLocaleToggle.vue';
import {
  getCurrentVersion,
  formatVersion,
  checkLatestVersion,
  type VersionInfo
} from '@/services/versionService';
import {
  Layout as ALayout,
  Menu as AMenu,
  Avatar as AAvatar,
  Dropdown as ADropdown,
  Doption as ADoption,
  SubMenu as ASubMenu,
  Select as ASelect,
  Popover as APopover,
  Radio as ARadio,
  RadioGroup as ARadioGroup,
  Message
} from '@arco-design/web-vue';
import {
  IconSettings,
  IconUser,
  IconDown,
  IconApps,
  IconSafe,
  IconMenuFold,
  IconMenuUnfold,
  IconStorage,
  IconCodeBlock,
  IconFile,
  IconTool,
  IconMessage,
  IconCloud,
  IconBook,
  IconFolder,
  IconHistory,
  IconExperiment,
  IconHome,
  IconComputer,
  IconSchedule,
  IconSunFill,
  IconMoonFill,
  IconList,
  IconRelation,
} from '@arco-design/web-vue/es/icon';
import '@arco-design/web-vue/dist/arco.css'; // 引入 Arco Design 样式

const ALayoutHeader = ALayout.Header;
const ALayoutSider = ALayout.Sider;
const ALayoutContent = ALayout.Content;
const AMenuItem = AMenu.Item;
const AOption = ASelect.Option;

const router = useRouter();
const authStore = useAuthStore();

const testCaseActiveView = ref<'list' | 'mindmap'>('list');
provide('testCaseActiveView', testCaseActiveView);

const isTestCaseManagementPage = computed(() => {
  return router.currentRoute.value.name === 'TestCaseManagement';
});
const projectStore = useProjectStore();
const themeStore = useThemeStore();
const environmentStore = useEnvironmentStore();
const { locale, t, tl } = useAppI18n();
const headerSelectTriggerProps = {
  contentClass: 'layout-header-select-dropdown',
};

// 版本信息
const currentVersion = ref(formatVersion(getCurrentVersion()));
const versionInfo = ref<VersionInfo | null>(null);
const hasUpdate = computed(() => versionInfo.value?.hasUpdate ?? false);
const dashboardMenuLabel = computed(() => (locale.value === 'en-US' ? 'Home' : tl('首页')));
const projectsMenuLabel = computed(() => (locale.value === 'en-US' ? 'Projects' : tl('项目管理')));
const requirementsMenuLabel = computed(() => (locale.value === 'en-US' ? 'Requirements' : tl('需求管理')));
const apiTestingMenuLabel = computed(() => (locale.value === 'en-US' ? 'API Testing' : tl('接口自动化')));
const automationMenuLabel = computed(() => (locale.value === 'en-US' ? 'Automation' : tl('UI自动化')));
const tasksMenuLabel = computed(() => (locale.value === 'en-US' ? 'Tasks' : tl('任务中心')));
const fileManagementMenuLabel = computed(() => (locale.value === 'en-US' ? 'Files' : tl('文件管理')));
const knowledgeMenuLabel = computed(() => (locale.value === 'en-US' ? 'RAG' : tl('知识库管理')));
const apiKeysMenuLabel = computed(() => (locale.value === 'en-US' ? 'Keys' : tl('KEY管理')));
const testManagementMenuLabel = computed(() => (locale.value === 'en-US' ? 'Testing' : tl('测试管理')));
const caseManagementMenuLabel = computed(() => (locale.value === 'en-US' ? 'Cases' : tl('用例管理')));
const suitesMenuLabel = computed(() => (locale.value === 'en-US' ? 'Suites' : tl('测试套件')));
const executionHistoryMenuLabel = computed(() => (locale.value === 'en-US' ? 'History' : tl('执行历史')));
const chatMenuLabel = computed(() => (locale.value === 'en-US' ? 'Chat' : tl('LLM对话')));
const systemMenuLabel = computed(() => (locale.value === 'en-US' ? 'Admin' : tl('系统管理')));
const usersMenuLabel = computed(() => (locale.value === 'en-US' ? 'Users' : tl('用户管理')));
const organizationsMenuLabel = computed(() => (locale.value === 'en-US' ? 'Teams' : tl('组织管理')));
const permissionsMenuLabel = computed(() => (locale.value === 'en-US' ? 'Access' : tl('权限管理')));
const operationLogsMenuLabel = computed(() => (locale.value === 'en-US' ? 'Logs' : tl('操作日志')));
const modelsMenuLabel = computed(() => (locale.value === 'en-US' ? 'Models' : tl('LLM配置')));
const mcpMenuLabel = computed(() => (locale.value === 'en-US' ? 'MCP' : tl('MCP配置')));
const skillsMenuLabel = computed(() => (locale.value === 'en-US' ? 'Skills' : tl('Skills管理')));

// 更新说明预览（显示完整内容）
const releaseNotesPreview = computed(() => {
  const notes = versionInfo.value?.releaseNotes;
  if (!notes) return '';
  // 移除 Markdown 标题符号，提取纯文本
  return notes
    .replace(/^#+\s*/gm, '')  // 移除标题 #
    .replace(/\r\n/g, '\n')    // 统一换行符
    .replace(/\*\*/g, '')      // 移除粗体
    .replace(/`[^`]+`/g, '')   // 移除代码
    .trim();
});

// 检查版本更新
async function checkVersion() {
  try {
    versionInfo.value = await checkLatestVersion();
  } catch (error) {
    console.warn('版本检查失败:', error);
  }
}

// 用户信息
const user = computed(() => authStore.currentUser);
const username = computed(() => user.value?.username || '');
const userInitial = computed(() => {
  if (user.value?.first_name && user.value.first_name.length > 0) {
    return user.value.first_name.charAt(0).toUpperCase();
  }
  return username.value.charAt(0).toUpperCase();
});

const themeButtonLabel = computed(() => (
  themeStore.isBlack ? t('layout.themeToDefault') : t('layout.themeToBlack')
));

// 当前激活的菜单项
const activeMenu = computed(() => {
  const path = router.currentRoute.value.path;
  if (path.startsWith('/dashboard')) return 'dashboard';
  if (path.startsWith('/projects')) return 'projects';
  if (path.startsWith('/requirements')) return 'requirements'; // 添加对需求管理路由的识别
  if (path.startsWith('/api-testing')) return 'api-testing';
  if (path.startsWith('/ui-automation')) return 'ui-automation';
  if (path.startsWith('/testsuites')) return 'testsuites'; // 添加对测试套件路由的识别
  if (path.startsWith('/test-executions')) return 'test-executions'; // 添加对执行历史路由的识别
  if (path.startsWith('/testcases')) return 'testcases';
  if (path.startsWith('/users')) return 'users';
  if (path.startsWith('/organizations')) return 'organizations';
  if (path.startsWith('/permissions')) return 'permissions';
  if (path.startsWith('/operation-logs')) return 'operation-logs';
  if (path.startsWith('/llm-configs')) return 'llm-configs';
  if (path.startsWith('/langgraph-chat')) return 'langgraph-chat';
  if (path.startsWith('/task-center')) return 'task-center';
  if (path.startsWith('/file-management')) return 'file-management';
  if (path.startsWith('/knowledge-management')) return 'knowledge-management';
  if (path.startsWith('/api-keys')) return 'api-keys';
  if (path.startsWith('/remote-mcp-configs')) return 'remote-mcp-configs';
  // 其他路由对应的菜单项
  return '';
});

// 当前打开的子菜单
const openKeys = ref<string[]>([]); // 默认所有子菜单都收起

// 侧边栏收起状态
const collapsed = ref(false);

// 检查各个菜单项的权限
const hasProjectsPermission = computed(() => {
  return authStore.hasPermission('projects.view_project');
});

const hasRequirementsPermission = computed(() => {
  return authStore.hasPermission('requirements.view_requirementdocument');
});

const hasTestcasesPermission = computed(() => {
  return authStore.hasPermission('testcases.view_testcase');
});

const hasTestSuitesPermission = computed(() => {
  return authStore.hasPermission('testcases.view_testsuite');
});

const hasTestExecutionsPermission = computed(() => {
  return authStore.hasPermission('testcases.view_testexecution');
});

const hasLangGraphChatPermission = computed(() => {
  return authStore.hasPermission('langgraph_integration.view_llmconfig') ||
         authStore.hasPermission('langgraph_integration.view_chatsession') ||
         authStore.hasPermission('langgraph_integration.view_chatmessage');
});

const hasApiTestingPermission = computed(() => {
  return authStore.hasPermission('api_interfaces.view_apiinterface') ||
         authStore.hasPermission('api_testcases.view_apitestcase') ||
         authStore.hasPermission('api_testtasks.view_apitesttasksuite');
});

const hasUiAutomationPermission = computed(() => {
  return authStore.hasPermission('ui_automation.view_uimodule') ||
         authStore.hasPermission('ui_automation.view_uipage') ||
         authStore.hasPermission('ui_automation.view_uitestcase');
});

const hasKnowledgePermission = computed(() => {
  return authStore.hasPermission('knowledge.view_knowledgebase');
});

const hasTaskCenterPermission = computed(() => {
  return authStore.hasPermission('task_center.view_scheduledtask');
});

const hasFileManagementPermission = computed(() => {
  return authStore.currentUser?.is_staff ||
         authStore.hasPermission('file_management.view_fileasset') ||
         authStore.hasPermission('file_management.add_fileasset');
});

const hasUsersPermission = computed(() => {
  return authStore.hasPermission('auth.view_user');
});

const hasOrganizationsPermission = computed(() => {
  return authStore.hasPermission('auth.view_group');
});

const hasPermissionsPermission = computed(() => {
  return authStore.hasPermission('auth.view_permission');
});

const hasOperationLogsPermission = computed(() => {
  return authStore.currentUser?.is_staff || authStore.hasPermission('operation_logs.view_operationlog');
});

const hasLlmConfigsPermission = computed(() => {
  return authStore.hasPermission('langgraph_integration.view_llmconfig') ||
         authStore.hasPermission('llm_config.view_llmconfiguration') ||
         authStore.hasPermission('llms.view_llmmodel');
});

const hasApiKeysPermission = computed(() => {
  return authStore.hasPermission('api_keys.view_apikey') ||
         authStore.hasPermission('llms.view_apikey');
});

const hasMcpConfigsPermission = computed(() => {
  return authStore.hasPermission('mcp_tools.view_remotemcpconfig');
});

const hasSkillsPermission = computed(() => {
  return authStore.hasPermission('skills.view_skill');
});

// 检查是否有测试管理菜单项的权限
const hasTestManagementMenuItems = computed(() => {
  return hasTestcasesPermission.value ||
         hasTestSuitesPermission.value ||
         hasTestExecutionsPermission.value;
});

// 检查是否有系统管理菜单项的权限
const hasSystemMenuItems = computed(() => {
  return hasUsersPermission.value ||
         hasOrganizationsPermission.value ||
         hasPermissionsPermission.value ||
         hasLlmConfigsPermission.value ||
         hasApiKeysPermission.value ||
         hasMcpConfigsPermission.value ||
         hasSkillsPermission.value ||
         hasOperationLogsPermission.value;
});

// 切换侧边栏收起状态
const toggleCollapse = () => {
  collapsed.value = !collapsed.value;
};

// 处理点击测试管理图标的事件
const handleTestManagementClick = (event: MouseEvent) => {
  // 阻止事件冒泡，防止触发其他事件
  if (event) {
    event.stopPropagation();
  }

  // 如果是收起状态，点击测试管理图标时展开侧边栏
  if (collapsed.value) {
    collapsed.value = false;
    // 展开测试管理子菜单
    openKeys.value = ['test-management'];
  } else {
    // 如果已经展开，则切换子菜单的展开状态
    if (openKeys.value.includes('test-management')) {
      openKeys.value = openKeys.value.filter(key => key !== 'test-management');
    } else {
      openKeys.value.push('test-management');
    }
  }

  // 确保状态更新后立即应用
  nextTick(() => {
    console.log('测试管理菜单状态更新:', openKeys.value);
  });
};

// 处理点击系统管理图标的事件
const handleSystemManagementClick = (event: MouseEvent) => {
  // 阻止事件冒泡，防止触发其他事件
  if (event) {
    event.stopPropagation();
  }

  // 如果是收起状态，点击系统管理图标时展开侧边栏
  if (collapsed.value) {
    collapsed.value = false;
    // 展开系统管理子菜单
    openKeys.value = ['settings'];
  } else {
    // 如果已经展开，则切换子菜单的展开状态
    if (openKeys.value.includes('settings')) {
      openKeys.value = openKeys.value.filter(key => key !== 'settings');
    } else {
      openKeys.value.push('settings');
    }
  }

  // 确保状态更新后立即应用
  nextTick(() => {
    console.log('系统管理菜单状态更新:', openKeys.value);
  });
};

// 检查是否选择了项目，用于需要项目的菜单项
const checkProjectAndNavigate = (event: MouseEvent, path: string) => {
  if (!projectStore.currentProjectId) {
    event.preventDefault();
    Message.warning(tl('请先选择或创建项目'));
    return;
  }
  router.push(path);
};

const handleLogout = () => {
  authStore.logout();
  router.push('/login');
};

// 项目选择器相关
// 在所有页面都显示项目选择器
const showProjectSelector = computed(() => true);

// 当前选中的项目ID
const selectedProjectId = computed({
  get: () => projectStore.currentProjectId,
  set: (value) => {
    if (value) {
      projectStore.setCurrentProjectById(value);
    }
  }
});

// 处理项目变更
const handleProjectChange = (projectId: number) => {
  projectStore.setCurrentProjectById(projectId);
};

// 处理下拉框显示状态变化
const handlePopupVisibleChange = (visible: boolean) => {
  if (visible) {
    // 当下拉框打开时，重新获取项目列表
    projectStore.fetchProjects();
  }
};

// 环境选择器相关
const showEnvironmentSelector = computed(() => {
  const path = router.currentRoute.value.path;
  return path.startsWith('/api-testing');
});

const selectedEnvironmentId = computed({
  get: () => environmentStore.currentEnvironmentId,
  set: (value) => {
    environmentStore.setCurrentEnvironment(value);
  }
});

const handleEnvironmentChange = (envId: number | null) => {
  environmentStore.setCurrentEnvironment(envId ?? null);
};

const handleEnvironmentPopupVisibleChange = (visible: boolean) => {
  if (visible && projectStore.currentProjectId) {
    environmentStore.fetchEnvironments(projectStore.currentProjectId);
  }
};

// 当项目变更时，重新加载环境列表
watch(() => projectStore.currentProjectId, (newProjectId) => {
  if (newProjectId && showEnvironmentSelector.value) {
    environmentStore.fetchEnvironments(newProjectId);
  } else {
    environmentStore.$reset();
  }
});

// 进入 api-testing 路由时加载环境列表
watch(showEnvironmentSelector, (show) => {
  if (show && projectStore.currentProjectId) {
    environmentStore.fetchEnvironments(projectStore.currentProjectId);
  }
});

// 在组件挂载时检查认证状态并加载项目列表
onMounted(async () => {
  // 确保用户信息在组件挂载时被正确加载
  authStore.checkAuthStatus();
  console.log('MainLayout mounted, user:', user.value?.username);

  // 加载项目列表
  await projectStore.fetchProjects();
  
  // 检查版本更新（后台执行，不阻塞页面）
  checkVersion();
});
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--color-bg-2, #ffffff);
  padding: 0 20px;
  height: 56px;
  line-height: 56px;
  color: var(--color-text-1, #333333);
  margin: 10px 10px 5px 10px;
  border-radius: 8px;
  box-shadow: 0 0 12px rgba(0, 0, 0, 0.25), 0 0 4px rgba(0, 0, 0, 0.15);
}

.left-section {
  display: flex;
  align-items: center;
  margin-left: 0; /* 移除左边距，让logo顶着边缘 */
}

.logo {
  font-size: 1.2em;
  font-weight: bold;
  color: var(--color-text-1, #333333);
  text-align: left;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  overflow: hidden;
  white-space: nowrap;
  padding: 0;
  margin: 0;
  margin-right: 20px;
  box-sizing: border-box;
  width: 150px;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

.logo-icon {
  width: 24px;
  height: 24px;
  object-fit: contain;
  border-radius: 3px;
  margin-right: 8px;
}

.logo-text {
  flex-shrink: 0;
}

.logo-ce-icon {
  flex: 0 0 auto;
  width: 22px;
  height: 15px;
  margin-left: 6px;
  object-fit: contain;
  transform: translateY(-25%);
}

.project-selector {
  display: flex;
  align-items: center;
}

:global(.layout-header-select-dropdown.layout-header-select-dropdown .arco-select-dropdown.arco-select-dropdown) {
  background: var(--color-bg-popup, var(--color-bg-2)) !important;
  border: 1px solid var(--color-border-2, #e5e6eb) !important;
  border-radius: 6px !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25) !important;
  color: var(--color-text-1, #1d2129) !important;
  padding: 4px !important;
  margin: 4px 0 !important;
}

:global(.layout-header-select-dropdown.layout-header-select-dropdown .arco-select-dropdown .arco-select-dropdown-list) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 2px !important;
}

:global(.layout-header-select-dropdown.layout-header-select-dropdown .arco-select-dropdown .arco-select-option) {
  display: flex !important;
  align-items: center !important;
  min-height: 32px !important;
  margin: 2px 0 !important;
  padding: 0 12px !important;
  border: none !important;
  border-radius: 4px !important;
  background: transparent !important;
  color: #1d2129 !important;
  line-height: 32px !important;
}

:global(.layout-header-select-dropdown.layout-header-select-dropdown .arco-select-dropdown .arco-select-option:hover) {
  background: #f2f3f5 !important;
  color: #1d2129 !important;
}

:global(.layout-header-select-dropdown.layout-header-select-dropdown .arco-select-dropdown .arco-select-option-active),
:global(.layout-header-select-dropdown.layout-header-select-dropdown .arco-select-dropdown .arco-select-option-selected) {
  background: rgba(var(--theme-accent-rgb), 0.12) !important;
  color: var(--theme-accent) !important;
}

:global(:root[data-theme='black'] body[arco-theme='dark'] .layout-header-select-dropdown.layout-header-select-dropdown .arco-select-dropdown.arco-select-dropdown) {
  background: #1d2639 !important;
  border-color: rgba(148, 163, 184, 0.18) !important;
  box-shadow: 0 22px 42px rgba(2, 6, 23, 0.42) !important;
  color: var(--theme-text) !important;
}

:global(:root[data-theme='black'] body[arco-theme='dark'] .layout-header-select-dropdown.layout-header-select-dropdown .arco-select-dropdown .arco-select-option) {
  background: transparent !important;
  color: var(--theme-text) !important;
}

:global(:root[data-theme='black'] body[arco-theme='dark'] .layout-header-select-dropdown.layout-header-select-dropdown .arco-select-dropdown .arco-select-option:hover) {
  background: #253347 !important;
  color: var(--theme-text) !important;
}

:global(:root[data-theme='black'] body[arco-theme='dark'] .layout-header-select-dropdown.layout-header-select-dropdown .arco-select-dropdown .arco-select-option-active),
:global(:root[data-theme='black'] body[arco-theme='dark'] .layout-header-select-dropdown.layout-header-select-dropdown .arco-select-dropdown .arco-select-option-selected) {
  background: #2a3a52 !important;
  color: #93c5fd !important;
}

.user-info {
  display: flex;
  align-items: center;
  margin-right: 20px;
  gap: 12px;
}

.theme-switch-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--theme-border);
  border-radius: 999px;
  background: var(--theme-toggle-bg);
  color: var(--theme-text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.theme-switch-button:hover {
  color: var(--theme-text);
  border-color: rgba(var(--theme-accent-rgb), 0.36);
  background: var(--theme-toggle-hover);
}

.theme-switch-button:focus-visible {
  outline: 2px solid rgba(var(--theme-accent-rgb), 0.45);
  outline-offset: 2px;
}

.theme-switch-icon {
  font-size: 16px;
  line-height: 1;
}

/* 版本号样式 */
.version-badge {
  font-size: 13px;
  color: #86909c;
  background: #f2f3f5;
  padding: 2px 8px;
  border-radius: 10px;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  line-height: 1.5;
}

.version-badge.update-available {
  color: #00b42a;
  background: #e8ffea;
  cursor: pointer;
}

.version-badge.update-available:hover {
  background: #d4f7d4;
}

.update-dot {
  width: 5px;
  height: 5px;
  background: #00b42a;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
  100% {
    opacity: 1;
  }
}

/* 版本更新弹出框样式 */
.version-update-info {
  max-width: 320px;
  padding: 4px;
}

.version-update-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e6eb;
}

.update-title {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.update-version {
  font-size: 13px;
  color: #00b42a;
  font-weight: 500;
  background: #e8ffea;
  padding: 2px 8px;
  border-radius: 4px;
}

.version-update-notes {
  font-size: 12px;
  color: #4e5969;
  line-height: 1.6;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE/Edge */
}

.version-update-notes::-webkit-scrollbar {
  display: none; /* Chrome/Safari/Opera */
}

.version-update-footer {
  display: block;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e5e6eb;
  font-size: 12px;
  color: #165dff;
  text-align: center;
  text-decoration: none;
  cursor: pointer;
}

.version-update-footer:hover {
  color: #0e42d2;
  text-decoration: underline;
}

.avatar {
  margin-right: 8px;
}

.user-dropdown {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.username {
  margin-right: 4px;
  font-size: 14px;
  color: #333333;
}

.dropdown-user-info {
  padding: 6px 8px;
  min-width: 120px;
  max-width: 150px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-username {
  font-weight: bold;
  font-size: 13px;
  color: #333333;
  margin-bottom: 3px;
}

.dropdown-email {
  font-size: 11px;
  color: #666666;
  margin-bottom: 3px;
}

.dropdown-role {
  font-size: 11px;
  color: var(--theme-accent);
  background-color: rgba(var(--theme-accent-rgb), 0.1);
  padding: 1px 4px;
  border-radius: 3px;
  display: inline-block;
}

.avatar {
  background-color: var(--theme-accent);
  color: #ffffff;
}

.user-dropdown-wrapper :deep(.arco-dropdown-content) {
  right: 35px !important;
  left: auto !important;
  transform: none !important;
}

.sider {
  background: var(--color-bg-2, #ffffff);
  margin: 5px 5px 10px 10px;
  border-radius: 8px;
  box-shadow: 0 0 12px rgba(0, 0, 0, 0.25), 0 0 4px rgba(0, 0, 0, 0.15);
  height: auto; /* 让 flex 自动撑开 */
}

.menu {
  background: var(--color-bg-2, #ffffff);
  color: var(--color-text-1, #333333);
  border-right: none;
  border-radius: 8px;
  overflow-y: auto;
  overflow-x: hidden;
  text-align: left;
  max-height: calc(100% - 50px);
}

:deep(.arco-menu-light) {
  background-color: #ffffff;
}

:deep(.arco-menu-light .arco-menu-item) {
  color: #666666;
  text-align: left;
  padding-left: 14px;
}

:deep(.arco-menu-light .arco-menu-item a) {
  color: inherit;
  text-decoration: none;
  display: block;
}

:deep(.arco-menu-light .arco-menu-item .arco-icon) {
  margin-right: 1px;
  margin-left: 0;
  float: left;
  color: inherit;
}

/* 收起状态下的菜单项样式 */
:deep(.arco-menu-collapse .arco-menu-item) {
  padding-left: 0 !important;
  padding-right: 0 !important;
  text-align: center;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  border-left: none !important;
}

:deep(.arco-menu-collapse .arco-menu-selected) {
  border-left: none !important;
}

:deep(.arco-menu-collapse .arco-menu-item .arco-icon) {
  margin-right: 0;
  margin-left: 0;
  float: none;
  font-size: 18px;
}

:deep(.arco-menu-collapse .arco-menu-inline-header) {
  padding-left: 0 !important;
  padding-right: 0 !important;
  text-align: center;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
}

:deep(.arco-menu-light .arco-menu-item:hover) {
  color: var(--theme-accent);
}

:deep(.arco-menu-light .arco-menu-selected) {
  color: var(--theme-accent);
  background-color: transparent;
  border-left: none;
}

:deep(.arco-menu-light .arco-menu-inline-header) {
  color: #666666;
  cursor: pointer;
  text-align: left;
  padding-left: 14px;
}

:deep(.arco-menu-light .arco-menu-inline-header:hover) {
  color: var(--theme-accent);
}

:deep(.arco-menu-light .arco-menu-inline-header.arco-menu-selected) {
  color: var(--theme-accent);
  background-color: transparent;
  border-left: none;
}

:deep(.arco-menu-light .arco-menu-inline-header .arco-icon) {
  margin-right: 1px;
  margin-left: 0;
  float: left;
  color: inherit;
}

:deep(.arco-menu-light .arco-menu-inline .arco-menu-item) {
  padding-left: 1px;
  padding-right: 0;
  text-align: left;
}

/* 收起状态下的子菜单图标样式 */
:deep(.arco-menu-collapse .arco-menu-inline-header .arco-icon) {
  margin-right: 0;
  margin-left: 0;
  float: none;
  position: relative;
  left: 0;
}

:deep(.arco-menu-light .arco-menu-inline .arco-menu-item a) {
  color: inherit;
  text-decoration: none;
  display: block;
}

:deep(.arco-menu-light .arco-menu-inline-header .arco-icon-down) {
  font-size: 12px;
  margin-right: 0;
  margin-left: 5px;
  transition: transform 0.2s;
  float: none;
}

:deep(.arco-menu-light .arco-menu-inline-header.arco-menu-inline-header-open .arco-icon-down) {
  transform: rotate(180deg);
}
</style>

<!-- 全局样式 - 用于菜单弹出层备用 -->
<style>
/* 备用样式：确保弹出菜单不受高度限制 */
.arco-menu-pop .arco-menu-inner {
  max-height: unset !important;
}

.main-layout {
  height: 100vh;
  background-color: var(--theme-page-bg);
  overflow: hidden;
}

.inner-layout {
  height: calc(100vh - 71px); /* Header(56px) + header-margin-top(10px) + header-margin-bottom(5px) = 71px */
}

.content {
  padding: 0;
  background-color: var(--theme-page-bg);
  height: calc(100vh - 86px); /* inner-layout(100vh-71px) - content-margin-top(5px) - content-margin-bottom(10px) = 100vh-86px */
  margin: 5px 10px 10px 5px;
  overflow: hidden; /* 让子组件自行控制滚动 */
  border-radius: 8px;
  box-shadow: 0 0 12px rgba(0, 0, 0, 0.25), 0 0 4px rgba(0, 0, 0, 0.15);
}

.sider-footer {
  position: absolute;
  bottom: 0;
  width: 100%;
  padding: 10px 0;
  display: flex;
  justify-content: center;
  align-items: center;
  border-top: 1px solid var(--theme-border);
}

.collapse-button {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--theme-text-secondary);
  padding: 0;
  margin: 0 auto;
}

.collapse-button:hover {
  color: var(--theme-accent);
}

/* 收起状态下的按钮样式 */
.sider-footer .arco-btn-icon-only {
  width: 32px;
  height: 32px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.header-view-switch {
  margin-left: 20px;
  display: flex;
  align-items: center;
}

.view-selector-group {
  background-color: var(--theme-surface-soft) !important;
  border-radius: 6px;
  padding: 2px;
}
</style>
