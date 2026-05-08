/**
 * 版本管理服务
 * 提供版本号显示和更新检测功能
 */
import packageJson from '../../package.json'

export interface VersionInfo {
  current: string
  latest?: string
  hasUpdate: boolean
  releaseUrl?: string
  releaseNotes?: string
  checkTime?: Date
}

// GitHub 仓库配置
const GITHUB_REPO = import.meta.env.VITE_GITHUB_REPO || 'mgdaaslab/WHartTest'
const GITHUB_API_BASE = 'https://api.github.com'
const GITHUB_RELEASES_URL = `https://github.com/${GITHUB_REPO}/releases`

// 缓存版本信息，避免频繁请求
let cachedVersionInfo: VersionInfo | null = null
let lastCheckTime: number = 0
const CHECK_INTERVAL = 1000 * 60 * 60 // 1小时缓存

/**
 * 获取当前版本号
 */
export function getCurrentVersion(): string {
  return packageJson.version || '0.0.0'
}

/**
 * 比较版本号
 * @returns 当 v1 > v2 返回 1；v1 < v2 返回 -1；相等返回 0
 */
export function compareVersions(v1: string, v2: string): number {
  const parts1 = v1.replace(/^v/, '').split('.').map(Number)
  const parts2 = v2.replace(/^v/, '').split('.').map(Number)
  
  for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
    const p1 = parts1[i] || 0
    const p2 = parts2[i] || 0
    if (p1 > p2) return 1
    if (p1 < p2) return -1
  }
  return 0
}

/**
 * 检查 GitHub 最新版本
 */
export async function checkLatestVersion(): Promise<VersionInfo> {
  const now = Date.now()
  
  // 使用缓存
  if (cachedVersionInfo && (now - lastCheckTime) < CHECK_INTERVAL) {
    return cachedVersionInfo
  }
  
  const current = getCurrentVersion()
  const versionInfo: VersionInfo = {
    current,
    hasUpdate: false
  }
  
  try {
    const response = await fetch(
      `${GITHUB_API_BASE}/repos/${GITHUB_REPO}/releases/latest`,
      {
        headers: {
          'Accept': 'application/vnd.github.v3+json'
        }
      }
    )
    
    if (!response.ok) {
      // 404: 仓库未创建 Release；403: GitHub API 匿名请求限流
      if (response.status !== 404 && response.status !== 403) {
        console.warn('无法获取最新版本信息:', response.status)
      }
      return versionInfo
    }
    
    const release = await response.json()
    if (release?.message && typeof release.message === 'string' && release.message.includes('API rate limit exceeded')) {
      return versionInfo
    }
    const latestVersion = release.tag_name?.replace(/^v/, '') || ''
    
    versionInfo.latest = latestVersion
    versionInfo.hasUpdate = compareVersions(latestVersion, current) > 0
    versionInfo.releaseUrl = release.html_url
    versionInfo.releaseNotes = release.body
    versionInfo.checkTime = new Date()
    
    // 更新缓存
    cachedVersionInfo = versionInfo
    lastCheckTime = now
    
  } catch (error) {
    console.warn('检查版本更新失败:', error)
  }
  
  return versionInfo
}

/**
 * 格式化版本号显示
 */
export function formatVersion(version: string): string {
  if (!version || version === '0.0.0') {
    return 'dev'
  }
  return `v${version.replace(/^v/, '')}`
}

export function getGithubReleasesUrl(): string {
  return GITHUB_RELEASES_URL
}
