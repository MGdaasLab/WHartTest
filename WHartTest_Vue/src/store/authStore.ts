import { defineStore } from 'pinia';
import {
  login as loginService,
  register as registerService,
  type AuthServiceLoginResponse,
  type AuthServiceRegisterResponse,
} from '@/services/authService';
import { getUserPermissions } from '@/services/permissionService';
import { useStorage } from '@vueuse/core';

// 用户信息结构
interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_active: boolean;
  groups: any[];
}

// 权限对象接口
interface Permission {
  id: number;
  name: string;
  name_cn: string; // 中文权限名称字段
  codename: string;
  content_type: {
    id: number;
    app_label: string;
    app_label_cn: string; // 应用中文名称
    app_label_sort: number; // 应用排序字段（1-6）
    app_label_subcategory: string | null; // 第二层分类名称
    app_label_subcategory_sort: number; // 第二层分类排序权重
    model: string;
    model_cn: string; // 模型中文名称
    model_verbose: string; // 模型详细名称
  };
}

interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  loginError: string | null; // 用于存储登录错误信息
  registerError: string | null; // 用于存储注册错误信息
  isLoading: boolean; // 用于跟踪登录/注册请求状态
  userPermissions: Permission[] | string[] | []; // 支持新的Permission对象数组和旧的字符串数组格式
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => {
    // 直接从 localStorage 获取数据，确保数据类型正确
    let storedUser = null;
    try {
      const userStr = localStorage.getItem('auth-user');
      if (userStr) {
        storedUser = JSON.parse(userStr);
      }
    } catch (e) {
      console.error('Failed to parse user data from localStorage:', e);
    }

    return {
      isAuthenticated: localStorage.getItem('auth-isAuthenticated') === 'true',
      user: storedUser,
      accessToken: localStorage.getItem('auth-accessToken'),
      refreshToken: localStorage.getItem('auth-refreshToken'),
      loginError: null,
      registerError: null,
      isLoading: false,
      userPermissions: (() => {
        try {
          const permissionsStr = localStorage.getItem('auth-userPermissions');
          if (permissionsStr) {
            return JSON.parse(permissionsStr);
          }
        } catch (e) {
          console.error('Failed to parse user permissions from localStorage:', e);
        }
        return [];
      })(), // 直接执行函数获取权限
    };
  },
  
  actions: {
    /**
     * 用户登录 Action
     * @param username 用户名
     * @param password 密码
     * @returns 返回一个 Promise，解析为登录是否成功 (boolean)
     */
    async login(username: string, password: string): Promise<boolean> {
      this.isLoading = true;
      this.loginError = null;
      try {
        const response: AuthServiceLoginResponse = await loginService(username, password);
        if (response.success && response.data) {
          this.isAuthenticated = true;
          // 存储API返回的用户信息
          this.user = response.data.user;
          this.accessToken = response.data.access;
          this.refreshToken = response.data.refresh;

          // 直接存储到 localStorage
          localStorage.setItem('auth-isAuthenticated', 'true');
          localStorage.setItem('auth-user', JSON.stringify(this.user));
          localStorage.setItem('auth-accessToken', this.accessToken);
          localStorage.setItem('auth-refreshToken', this.refreshToken);

          // 异步获取用户权限（不阻塞登录流程）
          this.loadUserPermissions().catch(error => {
            console.error('获取用户权限失败:', error);
          });

          this.isLoading = false;
          return true;
        } else {
          this.isAuthenticated = false;
          this.user = null;
          this.accessToken = null;
          this.refreshToken = null;
          this.loginError = response.error || '登录失败，请检查您的凭据。';
          // 清理 localStorage
          localStorage.removeItem('auth-isAuthenticated');
          localStorage.removeItem('auth-user');
          localStorage.removeItem('auth-accessToken');
          localStorage.removeItem('auth-refreshToken');
          this.isLoading = false;
          return false;
        }
      } catch (error: any) {
        this.isAuthenticated = false;
        this.user = null;
        this.accessToken = null;
        this.refreshToken = null;
        this.loginError = error.message || '发生未知错误，请稍后再试。';
        // 清理 localStorage
        localStorage.removeItem('auth-isAuthenticated');
        localStorage.removeItem('auth-user');
        localStorage.removeItem('auth-accessToken');
        localStorage.removeItem('auth-refreshToken');
        this.isLoading = false;
        return false;
      }
    },
    logout() {
      this.isAuthenticated = false;
      this.user = null;
      this.accessToken = null;
      this.refreshToken = null;
      this.loginError = null;
      this.userPermissions = []; // 清理权限
      // 清理 localStorage
      localStorage.removeItem('auth-isAuthenticated');
      localStorage.removeItem('auth-user');
      localStorage.removeItem('auth-accessToken');
      localStorage.removeItem('auth-refreshToken');
      localStorage.removeItem('auth-userPermissions');
    },
    // 应用初始化时调用此方法来同步 localStorage 的状态到 Pinia state
    checkAuthStatus() {
      // 直接从 localStorage 获取数据
      this.isAuthenticated = localStorage.getItem('auth-isAuthenticated') === 'true';

      // 解析用户信息
      try {
        const userStr = localStorage.getItem('auth-user');
        if (userStr) {
          this.user = JSON.parse(userStr);
        } else {
          this.user = null;
        }
      } catch (e) {
        console.error('Failed to parse user data from localStorage:', e);
        this.user = null;
      }

      this.accessToken = localStorage.getItem('auth-accessToken');
      this.refreshToken = localStorage.getItem('auth-refreshToken');

      // 如果没有 token，确保是登出状态
      if (!this.accessToken) {
        this.logout();
      } else if (this.isAuthenticated && this.user?.id) {
        // 如果已登录且有用户信息，加载权限
        this.loadUserPermissions();
      }

      console.log('Auth status checked:', {
        isAuthenticated: this.isAuthenticated,
        user: this.user ? this.user.username : 'none',
        hasToken: !!this.accessToken
      });
    },
    /**
     * 用户注册 Action
     * @param username 用户名
     * @param email 邮箱
     * @param password 密码
     * @returns 返回一个 Promise，解析为注册是否成功 (boolean)
     */
    async register(username: string, email: string, password: string): Promise<boolean> {
      this.isLoading = true;
      this.registerError = null;
      try {
        const response: AuthServiceRegisterResponse = await registerService(username, email, password);
        if (response.success && response.data) {
          // 注册成功后，可以选择是否自动登录用户
          // 当前实现：注册成功，但不自动登录，用户需要手动登录
          // 如果需要自动登录，可以调用 login action 或者直接设置 state
          this.isLoading = false;
          // 可以考虑将注册成功信息（如用户名）暂时存起来，以便在注册成功页面显示
          // this.user = { username: response.data.username, email: response.data.email, id: response.data.id };
          // 清理可能存在的旧的认证信息
          this.logout(); // 调用 logout 清理 localStorage 和 state
          return true;
        } else {
          this.registerError = response.error || '注册失败，请检查您输入的信息。';
          this.isLoading = false;
          return false;
        }
      } catch (error: any) {
        this.registerError = error.message || '发生未知错误，请稍后再试。';
        this.isLoading = false;
        return false;
      }
    },
    
    // 检查用户是否有指定权限
    hasPermission(permission: string): boolean {
      if (!this.isAuthenticated || !this.user) {
        return false;
      }
      
      // 管理员拥有所有权限
      if (this.user.is_staff) {
        return true;
      }
      
      // 如果权限列表为空或未加载，返回false（安全策略）
      if (!this.userPermissions || this.userPermissions.length === 0) {
        return false;
      }
      
      let hasPermissionResult = false;
      
      // 检查用户权限列表 - 支持新的Permission对象结构
      if (typeof this.userPermissions[0] === 'string') {
        // 兼容旧的字符串数组格式
        hasPermissionResult = (this.userPermissions as string[]).includes(permission);
      } else {
        // 新的Permission对象格式 - 通过codename或name检查权限
        hasPermissionResult = (this.userPermissions as Permission[]).some(p => {
          const standardFormat = `${p.content_type.app_label}.${p.codename}`;
          return p.codename === permission || p.name === permission || standardFormat === permission;
        });
      }
      
      // 调试日志
      if (permission.includes('langgraph_integration')) {
        console.log(`权限检查 [${permission}]: ${hasPermissionResult ? '✅ 通过' : '❌ 失败'}`);
        console.log('当前检查的权限列表类型:', typeof this.userPermissions[0]);
      }
      
      return hasPermissionResult;
    },
    
    // 检查权限是否已加载
    get isPermissionsLoaded(): boolean {
      return this.userPermissions !== null && Array.isArray(this.userPermissions);
    },
    
    // 设置用户权限 - 支持Permission对象数组或字符串数组
    setUserPermissions(permissions: Permission[] | string[]) {
      this.userPermissions = permissions;
      // 同时存储到localStorage
      localStorage.setItem('auth-userPermissions', JSON.stringify(permissions));
    },
    
    // 加载用户权限
    async loadUserPermissions() {
      if (!this.user?.id) {
        this.setUserPermissions([]); // 没有用户ID时，清空权限
        return;
      }
      
      try {
        const response = await getUserPermissions(this.user.id);
        if (response.success && response.data) {
          // 直接存储权限对象数组，不再转换为字符串
          this.setUserPermissions(response.data);
          console.log('用户权限加载成功:', response.data.length, '个权限');
          console.log('权限详细信息:', response.data);
        } else {
          // API返回失败或无数据时，清空权限
          this.setUserPermissions([]);
          console.warn('获取用户权限失败或无权限数据:', response.error || '无数据');
        }
      } catch (error) {
        // 接口报错时，清空权限（安全策略）
        this.setUserPermissions([]);
        console.error('获取用户权限失败:', error);
      }
    },
  },
  getters: {
    isLoggedIn: (state: AuthState) => state.isAuthenticated,
    currentUser: (state: AuthState) => state.user,
    getAccessToken: (state: AuthState) => state.accessToken,
    getRefreshToken: (state: AuthState) => state.refreshToken,
    getLoginError: (state: AuthState) => state.loginError,
    getRegisterError: (state: AuthState) => state.registerError, // 新增 getter
    getIsLoading: (state: AuthState) => state.isLoading,
  },
});