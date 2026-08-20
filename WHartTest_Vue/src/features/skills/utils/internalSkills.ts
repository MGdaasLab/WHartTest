/** 依赖平台 API Key 的内部 Skill 名称（与后端 platform_skills 对齐） */
export const INTERNAL_PLATFORM_SKILL_NAMES = new Set([
  'whart-test',
  'api-automation',
  'ui-automation',
])

export function isInternalPlatformSkill(name: string | undefined | null): boolean {
  return !!name && INTERNAL_PLATFORM_SKILL_NAMES.has(name.trim())
}

/** zip 文件名粗判（完整校验以后端 SKILL.md name 为准） */
export function zipNameSuggestsInternalSkill(fileName: string | undefined | null): boolean {
  if (!fileName) return false
  const lower = fileName.toLowerCase()
  // 与内部名单派生，避免两处硬编码漂移；另兼容 wharttest_skills.zip 等包名
  for (const name of INTERNAL_PLATFORM_SKILL_NAMES) {
    if (lower.includes(name)) return true
  }
  return lower.includes('whart')
}
