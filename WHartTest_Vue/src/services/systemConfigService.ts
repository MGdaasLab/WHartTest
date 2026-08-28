import { request } from '@/utils/request';

// 系统配置对象接口
export interface SystemConfig {
  title: string;                       // 浏览器标签页标题
  name: string;                        // 系统名称
  login_title: string;                 // 登录页主标题
  login_subtitle: string;              // 登录页副标题
  login_tags: string;                  // 登录页标签，逗号分隔
  logo_url: string;                    // Logo 地址
  brand_badge_enabled: boolean;        // 是否展示品牌角标
  brand_badge_url: string;             // 品牌角标地址
  operation_log_retention_days: number; // 操作日志保留天数
}

// 统一返回结果接口
export interface SystemConfigResponse {
  success: boolean;
  data?: SystemConfig;
  error?: string;
}

export const systemConfigService = {
  // 获取公开系统配置，无需登录，用于登录页等场景
  async getPublicConfig(): Promise<SystemConfigResponse> {
    try {
      const response = await request<SystemConfig>({
        url: '/accounts/system-config/public/',
        method: 'GET',
      });

      if (response.success && response.data) {
        return { success: true, data: response.data };
      }

      return {
        success: false,
        error: response.error || '获取系统公开配置失败',
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '获取系统公开配置发生网络异常',
      };
    }
  },

  // 更新系统配置，需要管理员权限
  async updateConfig(payload: Partial<SystemConfig>): Promise<SystemConfigResponse> {
    try {
      const response = await request<SystemConfig>({
        url: '/accounts/system-config/',
        method: 'PATCH',
        data: payload,
      });

      if (response.success && response.data) {
        return { success: true, data: response.data };
      }

      return {
        success: false,
        error: response.error || '更新系统配置失败',
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || '更新系统配置发生网络异常',
      };
    }
  },
};
