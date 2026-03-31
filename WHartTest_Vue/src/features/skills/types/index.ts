export interface Skill {
  id: number
  name: string
  description: string
  skill_content: string
  skill_path: string
  script_path: string | null
  is_active: boolean
  project: number
  project_name: string
  creator: number
  creator_name: string
  created_at: string
  updated_at: string
}

export interface SkillListItem {
  id: number
  name: string
  description: string
  is_active: boolean
  creator_name: string
  created_at: string
}

export interface SkillUploadResponse {
  code: number
  message: string
  data: Skill[] | null
}

export interface SkillGitImportResponse {
  code: number
  message: string
  data: Skill[] | null
}

export interface SkillListResponse {
  code: number
  message: string
  data: SkillListItem[]
}

export interface SkillDetailResponse {
  code: number
  message: string
  data: Skill
}

export interface SkillContentResponse {
  code: number
  message: string
  data: {
    name: string
    description: string
    content: string
  }
}
