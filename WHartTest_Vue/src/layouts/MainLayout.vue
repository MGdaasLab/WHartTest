<template>
  <a-layout class="main-layout">
    <!-- 顶部导航栏 -->
    <a-layout-header class="header">
      <div class="left-section">
        <div class="logo" unselectable="on">
          <img src="/WHartTest.png" alt="WHartTest Logo" class="logo-icon" />
          <span class="logo-text">WHartTest</span>
        </div>
        <div class="project-selector" v-if="showProjectSelector">
          <a-select
            v-model="selectedProjectId"
            :loading="projectStore.loading"
            :disabled="projectStore.loading"
            placeholder="请选择项目"
            style="width: 200px; margin-left: 10px;"
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
        </div>
      </div>
      <div class="user-info">
        <a-avatar class="avatar" style="background-color: #00a0e9; color: white;">
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
              <div class="dropdown-role" v-if="user?.is_staff">管理员</div>
            </div>
            <a-divider style="margin: 4px 0" />
            <a-doption @click="handleLogout">登出</a-doption>
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
          mode="vertical"
          :default-selected-keys="[activeMenu]"
          v-model:open-keys="openKeys"
          :auto-open-selected="true"
          :collapsed="collapsed"
          class="menu"
        >

          <!-- 仪表盘菜单已隐藏 -->

          <a-menu-item key="projects" v-if="hasProjectsPermission">
            <template #icon><icon-storage /></template>
            <router-link to="/projects">项目管理</router-link>
          </a-menu-item>

          <a-menu-item key="requirements" v-if="hasRequirementsPermission">
            <template #icon><icon-file /></template>
            <router-link to="/requirements">需求管理</router-link>
          </a-menu-item>

          <a-menu-item key="testcases" v-if="hasTestcasesPermission">
            <template #icon><icon-code-block /></template>
            <router-link to="/testcases">用例管理</router-link>
          </a-menu-item>

          <a-menu-item key="testsuites" v-if="hasTestSuitesPermission">
            <template #icon><icon-folder /></template>
            <router-link to="/testsuites">测试套件</router-link>
          </a-menu-item>

          <a-menu-item key="test-executions" v-if="hasTestExecutionsPermission">
            <template #icon><icon-history /></template>
            <router-link to="/test-executions">执行历史</router-link>
          </a-menu-item>

          <a-menu-item key="langgraph-chat" v-if="hasLangGraphChatPermission">
            <template #icon><icon-message /></template>
            <router-link to="/langgraph-chat">LLM对话</router-link>
          </a-menu-item>

          <a-menu-item key="knowledge-management" v-if="hasKnowledgePermission">
            <template #icon><icon-book /></template>
            <router-link to="/knowledge-management">知识库管理</router-link>
          </a-menu-item>

          <!-- 展开状态下显示子菜单 -->
          <template v-if="!collapsed && hasSystemMenuItems">
            <a-sub-menu key="settings">
              <template #icon><icon-settings /></template>
              <template #title>
                <span @click="handleSystemManagementClick">系统管理</span>
              </template>
              <a-menu-item key="users" v-if="hasUsersPermission">
                <template #icon><icon-user /></template>
                <router-link to="/users">用户管理</router-link>
              </a-menu-item>
              <a-menu-item key="organizations" v-if="hasOrganizationsPermission">
                <template #icon><icon-apps /></template>
                <router-link to="/organizations">组织管理</router-link>
              </a-menu-item>
              <a-menu-item key="permissions" v-if="hasPermissionsPermission">
                <template #icon><icon-safe /></template>
                <router-link to="/permissions">权限管理</router-link>
              </a-menu-item>
              <a-menu-item key="llm-configs" v-if="hasLlmConfigsPermission">
                <template #icon><icon-tool /></template>
                <router-link to="/llm-configs">LLM配置</router-link>
              </a-menu-item>
              <a-menu-item key="api-keys" v-if="hasApiKeysPermission">
                <template #icon><icon-safe /></template>
                <router-link to="/api-keys">KEY管理</router-link>
              </a-menu-item>
              <a-menu-item key="remote-mcp-configs" v-if="hasMcpConfigsPermission">
                <template #icon><icon-cloud /></template>
                <router-link to="/remote-mcp-configs">MCP配置</router-link>
              </a-menu-item>
            </a-sub-menu>
          </template>

          <!-- 收起状态下只显示系统管理图标 -->
          <template v-else-if="collapsed && hasSystemMenuItems">
            <a-menu-item key="settings">
              <template #icon>
                <icon-settings @click="handleSystemManagementClick" style="cursor: pointer;" />
              </template>
              <span style="display: none;">系统管理</span>
            </a-menu-item>
          </template>
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
            <span v-if="!collapsed">收起</span>
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
import { ref, computed, nextTick, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/store/authStore';
import { useProjectStore } from '@/store/projectStore';
import {
  Layout as ALayout,
  Menu as AMenu,
  Avatar as AAvatar,
  Dropdown as ADropdown,
  Doption as ADoption,
  SubMenu as ASubMenu,
  Select as ASelect
} from '@arco-design/web-vue';
import {
  IconSettings,
  IconUser,
  IconDown,
  IconDashboard,
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
} from '@arco-design/web-vue/es/icon';
import '@arco-design/web-vue/dist/arco.css'; // 引入 Arco Design 样式

const ALayoutHeader = ALayout.Header;
const ALayoutSider = ALayout.Sider;
const ALayoutContent = ALayout.Content;
const AMenuItem = AMenu.Item;
const AOption = ASelect.Option;

const router = useRouter();
const authStore = useAuthStore();
const projectStore = useProjectStore();

// 用户信息
const user = computed(() => authStore.currentUser);
const username = computed(() => user.value?.username || '');
const userInitial = computed(() => {
  if (user.value?.first_name && user.value.first_name.length > 0) {
    return user.value.first_name.charAt(0).toUpperCase();
  }
  return username.value.charAt(0).toUpperCase();
});

// 当前激活的菜单项
const activeMenu = computed(() => {
  const path = router.currentRoute.value.path;
  // 仪表盘路由已移除，不再识别
  if (path.startsWith('/projects')) return 'projects';
  if (path.startsWith('/requirements')) return 'requirements'; // 添加对需求管理路由的识别
  if (path.startsWith('/testsuites')) return 'testsuites'; // 添加对测试套件路由的识别
  if (path.startsWith('/test-executions')) return 'test-executions'; // 添加对执行历史路由的识别
  if (path.startsWith('/testcases')) return 'testcases';
  if (path.startsWith('/users')) return 'users';
  if (path.startsWith('/organizations')) return 'organizations';
  if (path.startsWith('/permissions')) return 'permissions';
  if (path.startsWith('/llm-configs')) return 'llm-configs';
  if (path.startsWith('/langgraph-chat')) return 'langgraph-chat'; // 添加对新路由的识别
  if (path.startsWith('/knowledge-management')) return 'knowledge-management'; // 添加对知识库管理路由的识别
  if (path.startsWith('/api-keys')) return 'api-keys'; // 添加对API Key路由的识别
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

const hasKnowledgePermission = computed(() => {
  return authStore.hasPermission('knowledge.view_knowledgebase');
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

// 检查是否有系统管理菜单项的权限
const hasSystemMenuItems = computed(() => {
  return hasUsersPermission.value ||
         hasOrganizationsPermission.value ||
         hasPermissionsPermission.value ||
         hasLlmConfigsPermission.value ||
         hasApiKeysPermission.value ||
         hasMcpConfigsPermission.value;
});

// 切换侧边栏收起状态
const toggleCollapse = () => {
  collapsed.value = !collapsed.value;
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

// 在组件挂载时检查认证状态并加载项目列表
onMounted(async () => {
  // 确保用户信息在组件挂载时被正确加载
  authStore.checkAuthStatus();
  console.log('MainLayout mounted, user:', user.value?.username);

  // 加载项目列表
  await projectStore.fetchProjects();
});
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #ffffff;
  padding: 0 20px;
  height: 56px;
  line-height: 56px;
  color: #333333;
  margin: 10px 10px;
  border-radius: 8px;
  box-shadow: -4px -4px 10px rgba(0, 0, 0, 0.2), 4px 0 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
}

.left-section {
  display: flex;
  align-items: center;
  margin-left: 0; /* 移除左边距，让logo顶着边缘 */
}

.logo {
  font-size: 1.2em;
  font-weight: bold;
  color: #333333;
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
  width: 140px;
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

.project-selector {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  margin-right: 20px;
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
  color: #00a0e9;
  background-color: rgba(0, 160, 233, 0.1);
  padding: 1px 4px;
  border-radius: 3px;
  display: inline-block;
}

.user-dropdown-wrapper :deep(.arco-dropdown-content) {
  right: 35px !important;
  left: auto !important;
  transform: none !important;
}

.sider {
  background: #ffffff;
  margin: 0 0 10px 10px;
  border-radius: 8px;
  box-shadow: -4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  height: calc(100vh - 86px);
}

.menu {
  background: #ffffff;
  color: #333333;
  border-right: none;
  border-radius: 8px;
  overflow: hidden;
  text-align: left;
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
  color: #00a0e9;
}

:deep(.arco-menu-light .arco-menu-selected) {
  color: #00a0e9;
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
  color: #00a0e9;
}

:deep(.arco-menu-light .arco-menu-inline-header.arco-menu-selected) {
  color: #00a0e9;
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

.main-layout {
  min-height: 100vh;
  background-color: #f8f9fc;
}

.inner-layout {
  height: calc(100vh - 86px);
}

.content {
  padding: 0;
  background-color: #f8f9fc;
  height: calc(100vh - 86px);
  margin: 0 10px 10px 10px;
  overflow-y: auto; /* 允许垂直滚动 */
  border-radius: 8px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
}

.sider-footer {
  position: absolute;
  bottom: 0;
  width: 100%;
  padding: 10px 0;
  display: flex;
  justify-content: center;
  align-items: center;
  border-top: 1px solid #f0f0f0;
}

.collapse-button {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
  padding: 0;
  margin: 0 auto;
}

.collapse-button:hover {
  color: #00a0e9;
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
</style>