import { request } from '@/utils/request'
import type {
  Skill,
  SkillListItem,
  SkillUploadResponse,
  SkillGitImportResponse,
  SkillListResponse,
  SkillDetailResponse,
  SkillContentResponse
} from '../types'

export class SkillService {
  /**
   * 获取项目下的所有 Skills
   */
  static async getSkills(projectId: number): Promise<SkillListItem[]> {
    const response = await request<SkillListResponse>({
      url: `/projects/${projectId}/skills/`,
      method: 'GET'
    })

    const api = response.data as any
    if (response.success && api) {
      const data = api.data
      return Array.isArray(data) ? data : []
    }
    throw new Error(response.error || '获取 Skills 列表失败')
  }

  /**
   * 获取 Skill 详情
   */
  static async getSkillDetail(projectId: number, skillId: number): Promise<Skill> {
    const response = await request<SkillDetailResponse>({
      url: `/projects/${projectId}/skills/${skillId}/`,
      method: 'GET'
    })

    const api = response.data as any
    if (response.success && api?.data) {
      return api.data
    }
    throw new Error(response.error || '获取 Skill 详情失败')
  }

  /**
   * 上传 Skill zip 文件
   */
  static async uploadSkill(projectId: number, file: File): Promise<Skill[]> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await request<SkillUploadResponse>({
      url: `/projects/${projectId}/skills/upload/`,
      method: 'POST',
      data: formData
    })

    const api = response.data as any
    if (response.success && api?.data) {
      return Array.isArray(api.data) ? api.data : [api.data]
    }
    throw new Error(api?.message || response.error || '上传 Skill 失败')
  }

  /**
   * 从 Git 仓库导入 Skill
   */
  static async importFromGit(
    projectId: number,
    gitUrl: string,
    branch?: string
  ): Promise<Skill[]> {
    const payload: { git_url: string; branch?: string } = { git_url: gitUrl }
    if (branch) {
      payload.branch = branch
    }

    const response = await request<SkillGitImportResponse>({
      url: `/projects/${projectId}/skills/import-git/`,
      method: 'POST',
      data: payload
    })

    const api = response.data as any
    if (response.success && api?.data) {
      return Array.isArray(api.data) ? api.data : [api.data]
    }
    throw new Error(api?.message || response.error || '从 Git 导入 Skill 失败')
  }

  /**
   * 切换 Skill 启用状态
   */
  static async toggleSkill(projectId: number, skillId: number, isActive: boolean): Promise<Skill> {
    const response = await request<SkillDetailResponse>({
      url: `/projects/${projectId}/skills/${skillId}/`,
      method: 'PATCH',
      data: { is_active: isActive }
    })

    const api = response.data as any
    if (response.success && api?.data) {
      return api.data
    }
    throw new Error(response.error || '更新 Skill 状态失败')
  }

  /**
   * 删除 Skill
   */
  static async deleteSkill(projectId: number, skillId: number): Promise<void> {
    const response = await request({
      url: `/projects/${projectId}/skills/${skillId}/`,
      method: 'DELETE'
    })

    if (!response.success) {
      throw new Error(response.error || '删除 Skill 失败')
    }
  }

  /**
   * 获取 Skill 的 SKILL.md 内容
   */
  static async getSkillContent(projectId: number, skillId: number): Promise<{ name: string; description: string; content: string }> {
    const response = await request<SkillContentResponse>({
      url: `/projects/${projectId}/skills/${skillId}/content/`,
      method: 'GET'
    })

    const api = response.data as any
    if (response.success && api?.data) {
      return api.data
    }
    throw new Error(response.error || '获取 Skill 内容失败')
  }
}
