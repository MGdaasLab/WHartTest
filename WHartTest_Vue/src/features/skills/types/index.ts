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

export interface SkillStoreConfig {
  default_source: string
  default_source_name: string
  allow_custom_source: boolean
  max_zip_size: number
}

export interface SkillStoreSource {
  id: string
  name: string
  baseUrl: string
  isDefault?: boolean
}

export interface SkillStoreCategory {
  slug: string
  name: string
  name_en?: string
  description?: string
  skill_count?: number
}

export interface ManifestSkill {
  id: string
  name: string
  name_en?: string
  description: string
  description_en?: string
  version?: string
  author?: string
  category?: string
  category_name?: string
  category_name_en?: string
  tags?: string[]
  zip_path: string
  readme_path?: string
  sha256?: string
}

export interface SkillStoreManifest {
  version: string
  updated_at?: string
  categories?: SkillStoreCategory[]
  skills: ManifestSkill[]
}

export type StoreItemStatus = 'idle' | 'installing' | 'uninstalling' | 'ok' | 'error'

export interface StoreItemState {
  item: ManifestSkill
  installed: boolean
  installedId: number | null
  selected: boolean
  status: StoreItemStatus
  error: string
}
