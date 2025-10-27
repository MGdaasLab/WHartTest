import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import { API_BASE_URL } from '@/config/api';

// 用户详情接口
export interface UserDetail {
  id: number;
  username: string;
  email: string;
}

// 项目成员接口
export interface ProjectMember {
  id: number;
  user: number;
  user_detail: UserDetail;
  role: string;
  joined_at: string;
}

// 项目类型定义
export interface Project {
  id: number;
  name: string;
  description: string;
  creator: number;
  creator_detail: UserDetail;
  created_at: string;
  updated_at: string;
  members?: ProjectMember[];
}

// 创建项目请求参数
export interface CreateProjectRequest {
  name: string;
  description: string;
}

// 更新项目请求参数
export interface UpdateProjectRequest {
  name?: string;
  description?: string;
}

// 分页参数
export interface PaginationParams {
  page?: number;
  pageSize?: number;
  search?: string;
}

// 项目列表响应
interface ProjectListResponse {
  success: boolean;
  data?: Project[];
  error?: string;
  statusCode?: number;
  total?: number;
}

// 单个项目响应
interface ProjectResponse {
  success: boolean;
  data?: Project;
  error?: string;
  statusCode?: number;
}

// 基本响应
interface BasicResponse {
  success: boolean;
  message?: string;
  error?: string;
  statusCode?: number;
}

/**
 * 获取项目列表
 * @param params 分页和搜索参数
 * @returns 返回一个Promise，解析为包含项目列表的响应对象
 */
export const getProjectList = async (params?: PaginationParams): Promise<ProjectListResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/projects/`, {
      params: params ? {
        page: params.page,
        page_size: params.pageSize,
        search: params.search || '',
      } : undefined,
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // API返回的格式为 { status: 'success', code: 200, data: [...] }
    if (response.data && response.data.status === 'success' && Array.isArray(response.data.data)) {
      return {
        success: true,
        data: response.data.data,
        total: response.data.data.length,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取项目列表失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('获取项目列表出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '获取项目列表时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 创建新项目
 * @param projectData 项目数据
 * @returns 返回一个Promise，解析为创建结果
 */
export const createProject = async (projectData: CreateProjectRequest): Promise<ProjectResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(`${API_BASE_URL}/projects/`, projectData, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设创建项目API返回的格式为 { status: 'success', code: 201, message: '项目创建成功', data: {...项目对象} }
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '创建项目失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('创建项目出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '创建项目时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 获取项目详情
 * @param projectId 项目ID
 * @returns 返回一个Promise，解析为项目详情
 */
export const getProjectDetail = async (projectId: number): Promise<ProjectResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/projects/${projectId}/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设API返回的格式为 { status: 'success', code: 200, data: {...项目对象} }
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取项目详情失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('获取项目详情出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '获取项目详情时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 更新项目
 * @param projectId 项目ID
 * @param projectData 更新的项目数据
 * @returns 返回一个Promise，解析为更新结果
 */
export const updateProject = async (projectId: number, projectData: UpdateProjectRequest): Promise<ProjectResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.patch(`${API_BASE_URL}/projects/${projectId}/`, projectData, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设更新项目API返回的格式为 { status: 'success', code: 200, message: '项目更新成功', data: {...项目对象} }
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '更新项目失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('更新项目出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '更新项目时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 删除项目
 * @param projectId 项目ID
 * @returns 返回一个Promise，解析为删除结果
 */
export const deleteProject = async (projectId: number): Promise<BasicResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.delete(`${API_BASE_URL}/projects/${projectId}/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设删除项目API返回的格式为 { status: 'success', code: 204, message: '项目删除成功' }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '项目删除成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '删除项目失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('删除项目出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '删除项目时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 获取项目成员列表
 * @param projectId 项目ID
 * @returns 返回一个Promise，解析为项目成员列表
 */
export const getProjectMembers = async (projectId: number): Promise<{
  success: boolean;
  data?: ProjectMember[];
  error?: string;
  statusCode?: number;
}> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/projects/${projectId}/members/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 打印原始响应，便于调试
    console.log('项目成员API响应:', response.data);

    // API返回的格式为 { status: 'success', code: 200, data: [...] }
    if (response.data && response.data.status === 'success' && Array.isArray(response.data.data)) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取项目成员列表失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('获取项目成员列表出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '获取项目成员列表时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 添加项目成员
 * @param projectId 项目ID
 * @param userId 用户ID
 * @param role 角色
 * @returns 返回一个Promise，解析为添加结果
 */
export const addProjectMember = async (projectId: number, userId: number, role: string): Promise<{
  success: boolean;
  data?: ProjectMember;
  error?: string;
  statusCode?: number;
}> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(`${API_BASE_URL}/projects/${projectId}/add_member/`, {
      user_id: userId,
      role: role
    }, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // API返回的格式为 { status: 'success', code: 201, data: {...} }
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '添加成员失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('添加成员出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '添加成员时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 移除项目成员
 * @param projectId 项目ID
 * @param userId 用户ID
 * @returns 返回一个Promise，解析为移除结果
 */
export const removeProjectMember = async (projectId: number, userId: number): Promise<BasicResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  console.log(`移除成员API调用: 项目ID=${projectId}, 用户ID=${userId}`);

  try {
    // 构建请求URL和数据
    const url = `${API_BASE_URL}/projects/${projectId}/remove_member/`;
    const requestData = { user_id: userId };

    console.log('移除成员请求URL:', url);
    console.log('移除成员请求数据:', requestData);

    const response = await axios.delete(url, {
      data: requestData,
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    console.log('移除成员API原始响应:', response.data);

    // API返回的格式为 { status: 'success', code: 204, message: '成员移除成功' }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '成员移除成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '移除成员失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('移除成员出错:', error);
    console.error('错误详情:', error.response?.data);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '移除成员时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 更新项目成员角色
 * @param projectId 项目ID
 * @param userId 用户ID
 * @param role 新角色
 * @returns 返回一个Promise，解析为更新结果
 */
export const updateProjectMemberRole = async (projectId: number, userId: number, role: string): Promise<{
  success: boolean;
  data?: ProjectMember;
  error?: string;
  statusCode?: number;
}> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.patch(`${API_BASE_URL}/projects/${projectId}/update_member_role/`, {
      user_id: userId,
      role: role
    }, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // API返回的格式为 { status: 'success', code: 200, data: {...} }
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '更新成员角色失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error: any) {
    console.error('更新成员角色出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '更新成员角色时发生错误',
      statusCode: error.response?.status,
    };
  }
};
