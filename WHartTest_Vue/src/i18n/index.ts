import arcoEnUS from '@arco-design/web-vue/es/locale/lang/en-us';
import arcoZhCN from '@arco-design/web-vue/es/locale/lang/zh-cn';
import {
  API_TESTING_LEGACY_EXACT_EN_MAP,
  API_TESTING_LEGACY_EXACT_ZH_OVERRIDES,
  API_TESTING_LEGACY_REGEX_EN_MAP,
  API_TESTING_LEGACY_REGEX_ZH_MAP,
} from './apiTestingLegacyMap';

export const APP_LOCALES = ['zh-CN', 'en-US'] as const;
export type AppLocale = (typeof APP_LOCALES)[number];
export type MessageParams = Record<string, string | number>;

export const DEFAULT_APP_LOCALE: AppLocale = 'zh-CN';
export const LOCALE_STORAGE_KEY = 'wharttest-app-locale';

const isBrowser = () => typeof window !== 'undefined' && typeof document !== 'undefined';

export const isAppLocale = (value: unknown): value is AppLocale => (
  typeof value === 'string' && APP_LOCALES.includes(value as AppLocale)
);

export const getSavedLocale = (): AppLocale => {
  if (!isBrowser()) {
    return DEFAULT_APP_LOCALE;
  }

  const savedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return isAppLocale(savedLocale) ? savedLocale : DEFAULT_APP_LOCALE;
};

export const applyDocumentLanguage = (locale: AppLocale) => {
  if (!isBrowser()) {
    return;
  }

  document.documentElement.lang = locale;
};

type AppMessageKey =
  | 'locale.switcherLabel'
  | 'locale.switchToChinese'
  | 'locale.switchToEnglish'
  | 'layout.themeToDefault'
  | 'layout.themeToBlack'
  | 'layout.logout'
  | 'layout.admin'
  | 'login.openDialog'
  | 'login.closeDialog'
  | 'login.showPassword'
  | 'login.hidePassword'
  | 'register.title'
  | 'register.subtitle'
  | 'register.submit'
  | 'register.submitting'
  | 'register.passwordMismatch'
  | 'register.invalidEmail'
  | 'register.fillRequired'
  | 'register.success'
  | 'register.unexpectedError'
  | 'register.existingAccount'
  | 'register.loginNow'
  | 'register.usernamePlaceholder'
  | 'register.emailPlaceholder'
  | 'register.passwordPlaceholder'
  | 'register.confirmPasswordPlaceholder'
  | 'common.confirm'
  | 'common.cancel'
  | 'common.close'
  | 'common.copy'
  | 'common.retry'
  | 'common.delete'
  | 'common.expand'
  | 'common.collapse'
  | 'common.previewHtml'
  | 'common.previewDiagram'
  | 'common.openInNewTab'
  | 'common.download'
  | 'common.open'
  | 'common.upload'
  | 'common.send'
  | 'common.stop'
  | 'common.image'
  | 'common.default'
  | 'common.enabled'
  | 'common.disabled'
  | 'common.loading'
  | 'common.noDescription'
  | 'chat.screenshot'
  | 'chat.floatingPreview'
  | 'chat.thinking'
  | 'chat.empty'
  | 'chat.releaseToUpload'
  | 'chat.imageSelected'
  | 'chat.clearImages'
  | 'chat.inputPlaceholder'
  | 'chat.inputPlaceholderVision'
  | 'chat.imageOnly'
  | 'chat.pastedImage'
  | 'chat.pastedImages'
  | 'chat.previewDiagramUnavailable'
  | 'chat.previewHtmlUnavailable'
  | 'chat.copySuccess'
  | 'chat.copyFailed'
  | 'chat.diagramPreview'
  | 'chat.htmlPreview'
  | 'chat.selectProjectFirst'
  | 'chat.startConversation'
  | 'chat.toolScreenshot'
  | 'chat.previewing'
  | 'layout.projectPlaceholder';

type MessageCatalog = Record<AppMessageKey, Record<AppLocale, string>>;

const APP_MESSAGES: MessageCatalog = {
  'locale.switcherLabel': {
    'zh-CN': '语言切换',
    'en-US': 'Language switcher',
  },
  'locale.switchToChinese': {
    'zh-CN': '切换到中文',
    'en-US': 'Switch to Chinese',
  },
  'locale.switchToEnglish': {
    'zh-CN': '切换到英语',
    'en-US': 'Switch to English',
  },
  'layout.themeToDefault': {
    'zh-CN': '切换到默认主题',
    'en-US': 'Switch to default theme',
  },
  'layout.themeToBlack': {
    'zh-CN': '切换到黑色主题',
    'en-US': 'Switch to black theme',
  },
  'layout.logout': {
    'zh-CN': '登出',
    'en-US': 'Log out',
  },
  'layout.admin': {
    'zh-CN': '管理员',
    'en-US': 'Administrator',
  },
  'layout.projectPlaceholder': {
    'zh-CN': '请选择项目',
    'en-US': 'Select a project',
  },
  'login.openDialog': {
    'zh-CN': '打开登录弹窗',
    'en-US': 'Open login dialog',
  },
  'login.closeDialog': {
    'zh-CN': '关闭登录弹窗',
    'en-US': 'Close login dialog',
  },
  'login.showPassword': {
    'zh-CN': '显示密码',
    'en-US': 'Show password',
  },
  'login.hidePassword': {
    'zh-CN': '隐藏密码',
    'en-US': 'Hide password',
  },
  'register.title': {
    'zh-CN': '注册新账户',
    'en-US': 'Create an account',
  },
  'register.subtitle': {
    'zh-CN': '欢迎加入WHartTest',
    'en-US': 'Welcome to WHartTest',
  },
  'register.submit': {
    'zh-CN': '注册',
    'en-US': 'Register',
  },
  'register.submitting': {
    'zh-CN': '注册中...',
    'en-US': 'Registering...',
  },
  'register.passwordMismatch': {
    'zh-CN': '两次输入的密码不一致',
    'en-US': 'The passwords do not match',
  },
  'register.invalidEmail': {
    'zh-CN': '请输入有效的邮箱地址',
    'en-US': 'Enter a valid email address',
  },
  'register.fillRequired': {
    'zh-CN': '请填写所有必填字段',
    'en-US': 'Fill in all required fields',
  },
  'register.success': {
    'zh-CN': '注册成功！请登录。',
    'en-US': 'Registration succeeded. Please sign in.',
  },
  'register.unexpectedError': {
    'zh-CN': '注册过程中发生意外错误。',
    'en-US': 'An unexpected error occurred during registration.',
  },
  'register.existingAccount': {
    'zh-CN': '已经有账户了?',
    'en-US': 'Already have an account?',
  },
  'register.loginNow': {
    'zh-CN': '点此登录',
    'en-US': 'Sign in now',
  },
  'register.usernamePlaceholder': {
    'zh-CN': '请输入用户名',
    'en-US': 'Enter username',
  },
  'register.emailPlaceholder': {
    'zh-CN': '请输入邮箱地址',
    'en-US': 'Enter email address',
  },
  'register.passwordPlaceholder': {
    'zh-CN': '请输入密码',
    'en-US': 'Enter password',
  },
  'register.confirmPasswordPlaceholder': {
    'zh-CN': '请再次输入密码',
    'en-US': 'Confirm password',
  },
  'common.confirm': {
    'zh-CN': '确认',
    'en-US': 'Confirm',
  },
  'common.cancel': {
    'zh-CN': '取消',
    'en-US': 'Cancel',
  },
  'common.close': {
    'zh-CN': '关闭',
    'en-US': 'Close',
  },
  'common.copy': {
    'zh-CN': '复制',
    'en-US': 'Copy',
  },
  'common.retry': {
    'zh-CN': '重试',
    'en-US': 'Retry',
  },
  'common.delete': {
    'zh-CN': '删除',
    'en-US': 'Delete',
  },
  'common.expand': {
    'zh-CN': '展开',
    'en-US': 'Expand',
  },
  'common.collapse': {
    'zh-CN': '收起',
    'en-US': 'Collapse',
  },
  'common.previewHtml': {
    'zh-CN': '预览 HTML',
    'en-US': 'Preview HTML',
  },
  'common.previewDiagram': {
    'zh-CN': '预览图表',
    'en-US': 'Preview diagram',
  },
  'common.openInNewTab': {
    'zh-CN': '新标签打开',
    'en-US': 'Open in new tab',
  },
  'common.download': {
    'zh-CN': '下载',
    'en-US': 'Download',
  },
  'common.open': {
    'zh-CN': '打开',
    'en-US': 'Open',
  },
  'common.upload': {
    'zh-CN': '上传',
    'en-US': 'Upload',
  },
  'common.send': {
    'zh-CN': '发送',
    'en-US': 'Send',
  },
  'common.stop': {
    'zh-CN': '停止',
    'en-US': 'Stop',
  },
  'common.image': {
    'zh-CN': '图片',
    'en-US': 'Image',
  },
  'common.default': {
    'zh-CN': '默认',
    'en-US': 'Default',
  },
  'common.enabled': {
    'zh-CN': '启用',
    'en-US': 'Enabled',
  },
  'common.disabled': {
    'zh-CN': '禁用',
    'en-US': 'Disabled',
  },
  'common.loading': {
    'zh-CN': '加载中...',
    'en-US': 'Loading...',
  },
  'common.noDescription': {
    'zh-CN': '暂无描述',
    'en-US': 'No description',
  },
  'chat.screenshot': {
    'zh-CN': '工具截图',
    'en-US': 'Tool screenshot',
  },
  'chat.floatingPreview': {
    'zh-CN': '悬浮预览中',
    'en-US': 'Floating preview',
  },
  'chat.thinking': {
    'zh-CN': '思考过程',
    'en-US': 'Thinking',
  },
  'chat.empty': {
    'zh-CN': '开始与 WHartTest 的对话吧',
    'en-US': 'Start a conversation with WHartTest',
  },
  'chat.releaseToUpload': {
    'zh-CN': '释放以上传图片',
    'en-US': 'Release to upload images',
  },
  'chat.imageSelected': {
    'zh-CN': '已选择 {count} 张图片',
    'en-US': '{count} image(s) selected',
  },
  'chat.clearImages': {
    'zh-CN': '清空',
    'en-US': 'Clear',
  },
  'chat.inputPlaceholder': {
    'zh-CN': '请输入你的消息... (Shift+Enter换行，Enter发送)',
    'en-US': 'Enter your message... (Shift+Enter for a new line, Enter to send)',
  },
  'chat.inputPlaceholderVision': {
    'zh-CN': '输入消息、拖拽、粘贴或选择图片... (Shift+Enter换行，Enter发送)',
    'en-US': 'Enter text, drag, paste, or choose images... (Shift+Enter for a new line, Enter to send)',
  },
  'chat.imageOnly': {
    'zh-CN': '请查看图片',
    'en-US': 'Please check the image',
  },
  'chat.pastedImage': {
    'zh-CN': '图片已粘贴',
    'en-US': 'Image pasted',
  },
  'chat.pastedImages': {
    'zh-CN': '已粘贴 {count} 张图片',
    'en-US': '{count} images pasted',
  },
  'chat.previewDiagramUnavailable': {
    'zh-CN': '未检测到可预览的图表XML',
    'en-US': 'No diagram XML available for preview',
  },
  'chat.previewHtmlUnavailable': {
    'zh-CN': '未检测到可预览的HTML内容',
    'en-US': 'No HTML content available for preview',
  },
  'chat.copySuccess': {
    'zh-CN': '复制成功',
    'en-US': 'Copied successfully',
  },
  'chat.copyFailed': {
    'zh-CN': '复制失败，请手动复制',
    'en-US': 'Copy failed. Please copy manually.',
  },
  'chat.diagramPreview': {
    'zh-CN': '图表预览',
    'en-US': 'Diagram preview',
  },
  'chat.htmlPreview': {
    'zh-CN': 'HTML 预览',
    'en-US': 'HTML preview',
  },
  'chat.selectProjectFirst': {
    'zh-CN': '请先选择一个项目',
    'en-US': 'Select a project first',
  },
  'chat.startConversation': {
    'zh-CN': '开始与 WHartTest 的对话吧',
    'en-US': 'Start a conversation with WHartTest',
  },
  'chat.toolScreenshot': {
    'zh-CN': '📷 工具截图',
    'en-US': '📷 Tool screenshot',
  },
  'chat.previewing': {
    'zh-CN': '预览中',
    'en-US': 'Previewing',
  },
};

const interpolate = (template: string, params?: MessageParams) => {
  if (!params) {
    return template;
  }

  return Object.entries(params).reduce((result, [key, value]) => (
    result.split(`{${key}}`).join(String(value))
  ), template);
};

export const translate = (locale: AppLocale, key: AppMessageKey, params?: MessageParams) => {
  const message = APP_MESSAGES[key]?.[locale] ?? APP_MESSAGES[key]?.[DEFAULT_APP_LOCALE] ?? key;
  return interpolate(message, params);
};

export const getArcoLocale = (locale: AppLocale) => (
  locale === 'en-US' ? arcoEnUS : arcoZhCN
);

export const toServerLanguage = (locale: AppLocale) => (
  locale === 'en-US' ? 'en' : 'zh-Hans'
);

const preserveWhitespace = (original: string, translated: string) => {
  const leading = original.match(/^\s*/)?.[0] ?? '';
  const trailing = original.match(/\s*$/)?.[0] ?? '';
  return `${leading}${translated}${trailing}`;
};

const LEGACY_EXACT_EN_MAP: Record<string, string> = {
  '中': 'ZH',
  '首页': 'Home',
  '项目管理': 'Projects',
  '需求管理': 'Requirements',
  'UI自动化': 'UI Automation',
  '任务中心': 'Task Center',
  '测试管理': 'Test Management',
  '用例管理': 'Case Management',
  '测试套件': 'Test Suites',
  '执行历史': 'Execution History',
  'LLM对话': 'LLM Chat',
  '知识库管理': 'Knowledge Base',
  '系统管理': 'System',
  '用户管理': 'Users',
  '组织管理': 'Organizations',
  '权限管理': 'Permissions',
  'LLM配置': 'LLM Configs',
  'KEY管理': 'Key Management',
  'MCP配置': 'MCP Configs',
  'Skills管理': 'Skills',
  '收起': 'Collapse',
  '请选择项目': 'Select a project',
  '当前版本:': 'Version:',
  '点击查看完整更新日志': 'View full release notes',
  '新版本可用': 'Update available',
  '管理员': 'Administrator',
  '登出': 'Log out',
  '账号登录': 'Account Login',
  '点击展开登录框': 'Click to open the sign-in dialog',
  '欢迎回来': 'Welcome back',
  '请登录您的账户': 'Sign in to your account',
  '请输入用户名': 'Enter username',
  '请输入密码': 'Enter password',
  '请输入用户名和密码': 'Enter username and password',
  '记住我': 'Remember me',
  '登录': 'Sign in',
  '登录中...': 'Signing in...',
  '登录成功！': 'Signed in successfully!',
  '还没有账号?': 'No account yet?',
  '立即注册': 'Register now',
  '注册新账户': 'Create an account',
  '欢迎加入WHartTest': 'Welcome to WHartTest',
  '请输入邮箱地址': 'Enter email address',
  '请再次输入密码': 'Confirm password',
  '注册': 'Register',
  '注册中...': 'Registering...',
  '已经有账户了?': 'Already have an account?',
  '点此登录': 'Sign in now',
  '语言切换': 'Language switcher',

  // 操作日志页面翻译 / Operation Log Page Translations
  '清理设置': 'Cleanup Settings',
  '操作日志自动清理设置': 'Operation Log Auto Cleanup Settings',
  '系统会每天凌晨 3 点自动清理超过保留天数的操作日志，默认保留 7 天。': 'The system automatically removes operation logs older than the retention period at 03:00 every day. The default retention period is 7 days.',
  '系统会每天自动清理超过保留天数的操作日志，默认保留 7 天。': 'The system automatically removes operation logs older than the retention period every day. The default retention period is 7 days.',
  '自动清理保留天数': 'Auto cleanup retention days',
  '7天（默认）': '7 days (default)',
  '15天': '15 days',
  '30天': '30 days',
  '自定义': 'Custom',
  '自定义保留天数': 'Custom retention days',
  '当前生效保留天数：': 'Current retention days:',
  '您当前仅有查看权限，不能修改自动清理设置。': 'You currently have read-only access and cannot modify the auto cleanup settings.',
  '请填写有效的保留天数': 'Please enter a valid retention period.',
  '操作日志自动清理设置已保存': 'Operation log auto cleanup settings have been saved.',
  '加载自动清理设置失败': 'Failed to load auto cleanup settings.',
  '保存自动清理设置失败': 'Failed to save auto cleanup settings.',
  '操作日志': 'Operation Logs',
  '操作日志记录': 'Operation Logs',
  '操作日志审计': 'Operation Log Audit',
  '无访问权限': 'Access Denied',
  '返回首页': 'Back to Home',
  '操作审计日志仅系统管理员或被授权的审计人员可访问。': 'Operation audit logs are only accessible to system administrators or authorized auditors.',
  '搜索用户名、模块、路径': 'Search username, module, path',
  '操作模块': 'Module',
  '请求方法': 'Method',
  '状态码': 'Status Code',
  '查询': 'Search',
  '重置': 'Reset',
  '操作时间': 'Time',
  '操作人': 'Operator',
  '操作描述': 'Description',
  '请求路径': 'Path',
  '明细': 'Detail',
  '操作日志详细明细': 'Operation Log Details',
  '耗时': 'Duration',
  '执行耗时': 'Duration',
  '复制成功！已写入系统剪切板': 'Copy successful! Written to clipboard',
  '复制失败，请手动选择复制': 'Copy failed, please copy manually',
  '无内容可复制': 'No content to copy',
  '无载荷内容 / Empty Body': 'Empty Body',
  '加载日志失败': 'Failed to load logs',
  '加载日志时发生网络异常': 'Network error while loading logs',
  '请求数据 (Request Data)': 'Request Data',
  '响应数据 (Response Data)': 'Response Data',
  '立即清理': 'Clean Up Now',
  '立即清理操作日志': 'Clean up operation logs now',
  '系统将立刻删除超过当前保留天数的操作日志，是否继续？': 'The system will immediately delete operation logs older than the current retention period. Do you want to continue?',
  '立即清理完成，已删除': 'Cleanup completed. Deleted',
  '条过期日志，当前保留': 'expired logs. Current retention is',
  '立即清理失败': 'Immediate cleanup failed',
  '天': 'days',
  '用户认证': 'User Authentication',
  '系统配置': 'System Configuration',
  '提示词管理': 'Prompt Management',
  '用例模块': 'Case Modules',
  '测试执行': 'Test Execution',
  '技能管理': 'Skill Management',
  'API Key管理': 'API Key Management',
  'MCP配置管理': 'MCP Config Management',
  '知识库文档': 'Knowledge Base Documents',
  '文档切片': 'Document Chunks',
  '知识库检索日志': 'Knowledge Base Query Logs',
  '用户提示词': 'User Prompts',
  'AI对话': 'AI Chat',
  '智能编排': 'Orchestrator',
  '微信集成': 'WeChat Integration',
  '接口自动化': 'API Automation',
  'API数据库配置': 'API Database Config',
  'API环境管理': 'API Environment',
  'API环境变量': 'API Env Variables',
  'API全局请求头': 'API Global Headers',
  'API自定义函数': 'API Custom Functions',
  'API接口模块': 'API Interface Modules',
  'API接口管理': 'API Interface Management',
  'API接口结果': 'API Interface Results',
  'API测试用例': 'API Test Cases',
  'API用例标签': 'API Case Tags',
  'API用例组': 'API Case Groups',
  'API测试报告': 'API Test Reports',
  'API测试任务集': 'API Test Task Suites',
  'API任务执行': 'API Task Execution',
  'API接口同步': 'API Interface Sync',
  'API同步历史': 'API Sync History',
  'API全局同步配置': 'API Global Sync Config',
  'UI模块': 'UI Modules',
  'UI页面': 'UI Pages',
  'UI元素': 'UI Elements',
  'UI页面步骤': 'UI Page Steps',
  'UI页面步骤详情': 'UI Page Steps Details',
  'UI用例': 'UI Cases',
  'UI用例步骤详情': 'UI Case Steps Details',
  'UI执行记录': 'UI Execution Records',
  'UI公共数据': 'UI Public Data',
  'UI环境配置': 'UI Environment Config',
  'UI批量执行记录': 'UI Batch Execution Records',
  '导入导出模板': 'Import/Export Templates',
  '新建': 'Create',
  '更新': 'Update',
  '部分更新': 'Partial Update',
  '列表查询': 'List',
  '详情查询': 'Retrieve',
  '运行': 'Run',
  '执行': 'Execute',
  '同步': 'Sync',
  '获取可用工具': 'Get Available Tools',
  '测试连接': 'Test Connection',
  '添加用例': 'Add Cases',
  '用例结果': 'Case Results',
  '成员管理': 'Member Management',
  '快捷调试': 'Quick Debug',
  '用户登录': 'User Login',
  '用户注册': 'User Registration',
  '当前用户信息': 'Current User Info',
  '发起对话': 'Start Chat',
  '查询对话历史': 'Get Chat History',
  '批量删除对话': 'Bulk Delete Conversations',
  '切换到默认主题': 'Switch to default theme',
  '切换到黑色主题': 'Switch to black theme',
  '知识库': 'Knowledge Base',
  '提示词：': 'Prompt:',
  '选择提示词': 'Select prompt',
  '默认': 'Default',
  '管理提示词': 'Manage prompts',
  '工具审批': 'Tool approval',
  '微信接入': 'WeChat access',
  '清除对话': 'Clear chat',
  '开始与 WHartTest 的对话吧': 'Start a conversation with WHartTest',
  '图表预览': 'Diagram preview',
  'HTML 预览': 'HTML preview',
  '工具执行审批': 'Tool execution approval',
  '以下操作需要您的确认后才能执行': 'The following action requires your approval before execution.',
  '执行参数': 'Execution parameters',
  '记住此选择': 'Remember this choice',
  '开启': 'On',
  '关闭': 'Off',
  '公开': 'Public',
  '私有': 'Private',
  '图片': 'Image',
  '发送': 'Send',
  '停止': 'Stop',
  '释放以上传图片': 'Release to upload images',
  '需要审批': 'Approval required',
  '打开': 'Open',
  '下载': 'Download',
  '思考过程': 'Thinking',
  '复制': 'Copy',
  '引用': 'Quote',
  '重试': 'Retry',
  '删除': 'Delete',
  '预览图表': 'Preview diagram',
  '新标签打开': 'Open in new tab',
  '悬浮预览中': 'Floating preview active',
  '工具审批偏好设置': 'Tool approval settings',
  '暂无需要审批的工具': 'No tools need approval',
  '请先添加 MCP 配置并同步工具': 'Add an MCP configuration and sync tools first',
  '取消': 'Cancel',
  '选择知识库': 'Select knowledge base',
  '相似度阈值:': 'Similarity threshold:',
  '检索数量:': 'Retrieval count:',
  '已绑定': 'Bound',
  '运行中': 'Running',
  '异常': 'Error',
  '扫码区': 'QR area',
  '连接微信账号': 'Connect WeChat account',
  '点击上方按钮生成二维码': 'Click the button above to generate a QR code.',
  '会话状态：': 'Session status:',
  '更新时间：': 'Updated at:',
  '账号区': 'Account area',
  '已绑定账号': 'Bound account',
  '可直接启停监听，不需要重新创建绑定': 'Start or stop listening directly without rebinding.',
  '最近收消息': 'Latest received message',
  '最近发消息': 'Latest sent message',
  '我的提示词': 'My prompts',
  '加载中...': 'Loading...',
  '暂无提示词': 'No prompts yet',
  '创建您的第一个提示词来开始使用': 'Create your first prompt to get started.',
  '暂无描述': 'No description',
  '启用': 'Enabled',
  '禁用': 'Disabled',
  '编辑': 'Edit',
  '设为默认': 'Set as default',
  '新建提示词': 'Create prompt',
  '编辑提示词': 'Edit prompt',
  '请选择提示词类型': 'Select prompt type',
  '请输入提示词名称': 'Enter prompt name',
  '请输入提示词描述（可选）': 'Enter prompt description (optional)',
  '请输入提示词内容': 'Enter prompt content',
  '未命名对话': 'Untitled conversation',
  '基础信息': 'Basic information',
  '状态设置': 'Status settings',
  '激活配置': 'Activate config',
  '已激活': 'Active',
  '未激活': 'Inactive',
  '全局共享': 'Global sharing',
  '仅自己可见': 'Private to me',
  '当前激活': 'Currently active',
  '连接配置': 'Connection settings',
  '系统提示词': 'System prompt',
  '请求策略': 'Request policy',
  '运行能力': 'Runtime capabilities',
  '多模态输入': 'Multimodal input',
  '上下文摘要': 'Context summarization',
  '人工审批': 'Human approval',
  '流式输出': 'Streaming output',
  '当前模块未单独配置': 'This module has no dedicated configuration',
  '默认供应商': 'Default provider',
  '默认模型': 'Default model',
  '默认 API URL': 'Default API URL',
  '未填写': 'Not set',
  '未设置': 'Not set',
  '测试成功': 'Test succeeded',
  '测试失败': 'Test failed',
  '获取模型列表失败': 'Failed to fetch model list',
  '请先填写当前页签的 API URL': 'Fill in the API URL for the current tab first',
  '请先保存配置，再测试当前页签': 'Save the configuration before testing this tab',
  '复制成功': 'Copied successfully',
  '复制失败，请手动复制': 'Copy failed. Please copy manually.',
  '图片已粘贴': 'Image pasted',
  '已停止生成': 'Generation stopped',
  '消息已删除': 'Message deleted',
  '对话历史已清空': 'Chat history cleared',
  '对话已删除': 'Conversation deleted',
  '批量删除对话失败': 'Bulk delete failed',
  '消息内容不能为空！': 'Message content cannot be empty.',
  '请先选择一个项目': 'Select a project first',
  '请先选择一个知识库': 'Select a knowledge base first',
  '未找到可用的 LLM 配置': 'No available LLM configuration found',
  '获取LLM配置失败': 'Failed to get LLM configuration',
  '请添加或初始化提示词后才能开始对话': 'Add or initialize prompts before starting a conversation.',
  '系统提示词更新成功': 'System prompt updated successfully',
  '更新系统提示词失败': 'Failed to update the system prompt',
  '无法获取项目或会话信息': 'Unable to get project or session information',
  '正在执行工具...': 'Executing tool...',
  '已拒绝执行': 'Execution denied',
  '操作失败，请重试': 'Action failed. Please try again.',
  '获取会话列表失败': 'Failed to get sessions',
  '获取会话列表失败，请稍后重试': 'Failed to get sessions. Please try again later.',
  '加载聊天历史失败，将开始新的对话': 'Failed to load chat history. Starting a new conversation.',
  '未检测到可预览的图表XML': 'No diagram XML available for preview',
  '未检测到可预览的HTML内容': 'No HTML content available for preview',
  '当前环境不支持全屏预览': 'Fullscreen preview is not supported in the current environment',
  '未找到对应的消息': 'The corresponding message was not found',
  '未找到对应的用户消息': 'The corresponding user message was not found',
  '未找到该消息': 'Message not found',
  '服务器回滚可能未完成，但本地消息已删除': 'Server rollback may still be running, but the local message was deleted.',
  '删除消息失败，请稍后重试': 'Failed to delete the message. Please try again later.',
  '新对话': 'New conversation',
  '加载会话历史失败': 'Failed to load conversation history',
  '没有选择项目，无法删除会话': 'No project selected. Unable to delete the conversation.',
  '删除对话失败': 'Failed to delete the conversation',
  '删除对话失败，请稍后重试': 'Failed to delete the conversation. Please try again later.',
  '对话历史已从服务器删除': 'Chat history deleted from the server',
  '服务器删除可能未完成，但本地对话已清除': 'Server deletion may still be running, but the local conversation was cleared.',
  '删除聊天历史失败，请稍后重试': 'Failed to delete chat history. Please try again later.',
  '请选择用户': 'Select a user',
  '选择用户': 'Select user',
  '请选择角色': 'Select a role',
  '状态': 'Status',
  '描述': 'Description',
  '名称': 'Name',
  '创建时间': 'Created at',
  '更新时间': 'Updated at',
  '创建者': 'Created by',
  '操作': 'Actions',
  '删除成功': 'Deleted successfully',
  '删除失败': 'Failed to delete',
  '更新成功': 'Updated successfully',
  '更新失败': 'Update failed',
  '创建成功': 'Created successfully',
  '创建失败': 'Creation failed',
  '失败': 'Failed',
  '成功': 'Succeeded',
  '未登录或会话已过期': 'Not signed in or the session has expired',
  '未登录或登录已过期': 'Not signed in or the session has expired',
  '登录已过期，请重新登录': 'Session expired. Please sign in again.',
  '网络连接超时或服务器无响应': 'Network timeout or no server response',
  '未知错误': 'Unknown error',
  '请填写必填项': 'Fill in the required fields',
  '用户名': 'Username',
  '邮箱': 'Email',
  '角色': 'Role',
  '密码': 'Password',
  '用例名称': 'Case Name',
  '前置条件': 'Preconditions',
  '测试内容': 'Test content',
  '测试结果:': 'Test result:',
  '优先级': 'Priority',
  '测试类型': 'Test type',
  '审核状态': 'Review status',
  '模块': 'Module',
  '所属模块': 'Module',
  '模块名称': 'Module name',
  '模块管理': 'Module management',
  '暂无模块数据': 'No module data',
  '选择': 'Select',
  '搜索套件名称': 'Search suite name',
  '搜索用例名称': 'Search case name',
  '统计': 'Statistics',
  '未执行': 'Not Run',
  '等待中': 'Waiting',
  '执行中': 'Running',
  '已完成': 'Completed',
  '已取消': 'Cancelled',
  '通过': 'Passed',
  '跳过': 'Skipped',
  '执行人': 'Executor',
  '执行状态': 'Execution status',
  '触发类型': 'Trigger type',
  '执行时长': 'Duration',
  '开始时间': 'Start time',
  '时长': 'Duration',
  '浏览器': 'Browser',
  '定位类型': 'Locator type',
  '可选': 'Optional',
  '未配置': 'Not configured',
  '调度策略': 'Schedule',
  '分块大小': 'Chunk size',
  '分块重叠': 'Chunk overlap',
  '页面管理': 'Pages',
  '页面步骤': 'Page Steps',
  '测试用例': 'Test Cases',
  '执行记录': 'Execution Records',
  '批量执行': 'Batch Execution',
  '公共数据': 'Public Data',
  '环境配置': 'Environment Configs',
  '执行器': 'Actuators',
  '元素管理': 'Element Management',
  '步骤详情': 'Step Details',
  '用例步骤': 'Case Steps',
  '编辑模块': 'Edit module',
  '新增模块': 'Create module',
  '编辑用例': 'Edit case',
  '新增用例': 'Create case',
  '父模块': 'Parent module',
  '页面': 'Page',
  '元素': 'Elements',
  '页面名称': 'Page name',
  '页面 URL': 'Page URL',
  '所属页面': 'Page',
  '元素名称': 'Element name',
  '步骤名称': 'Step name',
  '定位表达式': 'Locator expression',
  '定位设置': 'Locator settings',
  '无头模式': 'Headless mode',
  '刷新': 'Refresh',
  '详情': 'Details',
  '新增环境': 'Add environment',
  '编辑环境配置': 'Edit environment config',
  '新增环境配置': 'Create environment config',
  '环境名称': 'Environment name',
  '基础 URL': 'Base URL',
  '用例等级': 'Case level',
  '用例描述': 'Case description',
  '如：开发环境、测试环境': 'Example: development or test environment',
  '如：http://localhost:3000': 'Example: http://localhost:3000',
  '无头': 'Headless',
  '有头': 'Headed',
  '视口宽度': 'Viewport width',
  '视口高度': 'Viewport height',
  '超时(ms)': 'Timeout (ms)',
  '启用新增': 'Allow creating',
  '启用查改删': 'Allow viewing, editing, and deleting',
  '主机地址': 'Host',
  '端口': 'Port',
  '数据库用户名': 'Database username',
  '数据库密码': 'Database password',
  '数据库': 'Database',
  'localhost 或 127.0.0.1': 'localhost or 127.0.0.1',
  '要连接的数据库名称': 'Database name to connect',
  '已设为默认': 'Set as default successfully',
  '设置失败': 'Failed to apply setting',
  '编辑数据': 'Edit data',
  '新增数据': 'Create data',
  '变量名': 'Variable name',
  '变量值': 'Variable value',
  '数据类型': 'Data type',
  '字符串': 'String',
  '整数': 'Integer',
  '列表': 'List',
  '字典': 'Dictionary',
  '编辑元素': 'Edit element',
  '新增元素': 'Create element',
  '主定位': 'Primary locator',
  '备用定位 1（可选）': 'Backup locator 1 (optional)',
  '配置': 'Configuration',
  '下标': 'Index',
  '等待时间（秒）': 'Wait time (seconds)',
  '在 iframe 中': 'Inside iframe',
  'iframe 定位表达式': 'Iframe locator expression',
  '请输入 iframe 定位表达式': 'Enter iframe locator expression',
  '可选描述': 'Optional description',
  '备用定位表达式1': 'Backup locator 1',
  '备用定位表达式2': 'Backup locator 2',
  'iframe设置': 'Iframe settings',
  'iframe定位表达式': 'Iframe locator expression',
  '编辑页面': 'Edit page',
  '新增页面': 'Create page',
  '请输入页面名称': 'Enter page name',
  '请输入页面 URL': 'Enter page URL',
  '请输入描述': 'Enter description',
  '编辑页面步骤': 'Edit page step',
  '新增页面步骤': 'Create page step',
  '新增步骤': 'Add step',
  '编辑步骤': 'Edit step',
  '添加步骤': 'Add step',
  '编辑操作': 'Edit action',
  '添加操作': 'Add action',
  '操作类型': 'Action type',
  '操作方法': 'Action method',
  '选择元素': 'Select element',
  '鼠标操作': 'Mouse actions',
  '输入操作': 'Input actions',
  '其他': 'Other',
  '点击': 'Click',
  '双击': 'Double click',
  '悬停': 'Hover',
  '填充': 'Fill',
  '输入': 'Type',
  '清空': 'Clear',
  '等待': 'Wait',
  '截图': 'Screenshot',
  '选择下拉': 'Select option',
  '断言元素': 'Assertion element',
  '断言方法': 'Assertion method',
  '元素可见': 'Element visible',
  '元素隐藏': 'Element hidden',
  '文本断言': 'Text assertion',
  '值断言': 'Value assertion',
  '数量断言': 'Count assertion',
  'SQL 配置': 'SQL config',
  'JSON 格式 SQL 配置': 'SQL config in JSON format',
  '自定义变量': 'Custom variable',
  'JSON 格式变量定义': 'Variable definition in JSON format',
  '条件配置': 'Condition config',
  'JSON 格式条件配置': 'Condition config in JSON format',
  '输入内容': 'Input text',
  '等待时间(毫秒)': 'Wait time (ms)',
  '截图文件名': 'Screenshot filename',
  '可选，留空自动生成': 'Optional, leave blank to auto-generate',
  '选项值': 'Option value',
  '期望文本': 'Expected text',
  '期望值': 'Expected value',
  '期望数量': 'Expected count',
  '请输入要填充的文本': 'Enter the text to fill',
  '请输入要键入的文本': 'Enter the text to type',
  '默认1000': 'Default 1000',
  '请输入要选择的选项值': 'Enter the option value to select',
  '请输入期望的文本内容': 'Enter the expected text',
  '请输入期望的值': 'Enter the expected value',
  '请输入期望的元素数量': 'Enter the expected element count',
  '搜索元素名称': 'Search element name',
  '搜索环境名称': 'Search environment name',
  '搜索页面名称/URL': 'Search page name / URL',
  '搜索变量名': 'Search variable name',
  '搜索步骤名称': 'Search step name',
  '请选择数据类型': 'Select a data type',
  '请选择定位类型': 'Select a locator type',
  '请选择操作类型': 'Select an action type',
  '请选择用例等级': 'Select a case level',
  '请选择元素': 'Select an element',
  '请输入变量名': 'Enter variable name',
  '请输入变量值': 'Enter variable value',
  '请输入元素名称': 'Enter element name',
  '请输入定位表达式': 'Enter locator expression',
  '请输入模块名称': 'Enter module name',
  '请输入步骤名称': 'Enter step name',
  '请输入环境名称': 'Enter environment name',
  '请输入用例名称': 'Enter case name',
  '请输入用例描述': 'Enter case description',
  '选择模块': 'Select module',
  '请选择模块': 'Select module',
  '选择页面': 'Select page',
  '请选择页面': 'Select page',
  '选择页面步骤': 'Select page step',
  '请选择页面步骤': 'Select page step',
  '选择执行器': 'Select actuator',
  '请选择执行器': 'Select actuator',
  '执行环境': 'Execution environment',
  '请选择一个在线的执行器': 'Select an online actuator',
  '暂无在线执行器': 'No online actuators',
  '在线': 'Online',
  '离线': 'Offline',
  '请先选择执行器': 'Select an actuator first',
  '请先选择模块': 'Select a module first',
  '请先选择父模块': 'Select a parent module first',
  '请先选择要删除的用例': 'Select the cases to delete first',
  '请先选择要执行的用例': 'Select the cases to execute first',
  '没有可用的执行器，请先启动执行器': 'No actuators are available. Start one first',
  '没有可用的执行器，请先启动执行器服务': 'No actuator is available. Start the actuator service first.',
  '请先启动执行器服务：cd WHartTest_Actuator && python main.py': 'Start the actuator service first: cd WHartTest_Actuator && python main.py',
  '该页面步骤没有操作': 'This page step has no actions',
  '该模块下有子模块，请先删除子模块': 'This module has child modules. Delete them first',
  '存在关联，无法删除。请先解除关联': 'Linked data prevents deletion. Remove the associations first',
  '获取元素列表失败': 'Failed to fetch element list',
  '获取公共数据失败': 'Failed to fetch public data',
  '获取操作步骤失败': 'Failed to fetch action steps',
  '获取模块列表失败': 'Failed to fetch module list',
  '获取模块树失败': 'Failed to fetch module tree',
  '获取步骤列表失败': 'Failed to fetch step list',
  '获取环境配置失败': 'Failed to fetch environment configs',
  '获取用例列表失败': 'Failed to fetch case list',
  '获取页面列表失败': 'Failed to fetch page list',
  '获取页面步骤列表失败': 'Failed to fetch page step list',
  '发送执行命令失败': 'Failed to send execution command',
  '发送批量执行命令失败': 'Failed to send batch execution command',
  '批量删除': 'Batch delete',
  '批量删除失败': 'Failed to batch delete',
  '批量删除用例时发生错误': 'An error occurred while batch deleting cases',
  'WebSocket 连接失败': 'WebSocket connection failed',
  'WebSocket 连接失败，请刷新页面重试': 'WebSocket connection failed. Refresh and try again',
  '添加成功': 'Added successfully',
  '添加失败': 'Add failed',
  '导出成功': 'Export succeeded',
  '导出失败': 'Export failed',
  '导出用例失败': 'Failed to export cases',
  '服务器返回的不是有效的文件数据': 'The server returned invalid file data',
  '请选择至少一个模块': 'Please select at least one module',
  '测试执行已启动': 'Test execution has started',
  '启动执行失败': 'Failed to start execution',
  '启动执行时发生错误': 'An error occurred while starting the execution',
  '创建测试执行失败': 'Failed to create test execution',
  '创建测试执行时发生错误': 'An error occurred while creating the test execution',
  '缺少必要信息': 'Missing required information',
  '连接测试成功': 'Connection test succeeded',
  '连接测试失败': 'Connection test failed',
  '排序已保存': 'Order saved',
  '保存排序失败': 'Failed to save order',
  '嵌入模型测试成功！服务运行正常': 'Embedding test passed! Service is running normally',
  'Reranker 服务测试成功！': 'Reranker test passed!',
  'Reranker 服务测试成功！服务运行正常': 'Reranker test passed! Service is running normally',
  'Reranker 服务测试成功！ 服务运行正常': 'Reranker test passed! Service is running normally',
  'Reranker 测试失败': 'Reranker test failed',
  '无法连接到 Reranker 服务': 'Unable to connect to reranker service',
  '服务运行正常': 'Service is running normally',
  '开始专项分析': 'Starting specialized analysis',
  '初始化': 'Initializing',
  '分析模块一致性': 'Analyzing module consistency',
  '执行记录详情': 'Execution record details',
  '批量执行详情': 'Batch execution details',
  '执行追踪': 'Execution trace',
  '步骤执行结果': 'Step execution results',
  '查看 Trace': 'View Trace',
  '无权限访问任务中心': 'Task Center access denied',
  '请联系管理员分配任务中心查看权限': 'Contact an administrator to get Task Center view permission.',
  '请在顶部选择一个项目': 'Select a project from the top bar first',
  '任务名称最大长度为50字符': 'Task name must be at most 50 characters',
  '测试套件模块必须关联一个测试套件': 'The test suite module must be linked to a test suite',
  '测试套件必须属于当前项目': 'The test suite must belong to the current project',
  'UI用例必须属于当前项目': 'UI cases must belong to the current project',
  '仅执行一次时必须指定执行时间': 'A one-time task must specify an execution time',
  '每天执行时必须指定时间': 'A daily task must specify a time',
  '每周执行时必须选择至少一天': 'A weekly task must select at least one day',
  '每周执行时必须指定时间': 'A weekly task must specify a time',
  '每小时执行时必须指定分钟数': 'An hourly task must specify the minute',
  '批次名称': 'Batch name',
  '执行进度': 'Execution progress',
  '成功率': 'Success rate',
  '用例统计': 'Case summary',
  '错误信息': 'Error message',
  '步骤': 'Step',
  '消息': 'Message',
  '结束时间': 'End time',
  '元素数': 'Element count',
  '操作数': 'Action count',
  '步骤数': 'Step count',
  '暂无模块': 'No modules',
  '暂无步骤，请添加页面步骤': 'No steps yet. Please add page steps',
  '暂无操作步骤': 'No action steps',
  '暂无控制台消息': 'No console messages',
  '暂无快照': 'No snapshots',
  '暂无操作记录': 'No action records',
  '正在加载 Trace 数据...': 'Loading trace data...',
  '此执行记录没有 Trace 数据': 'This execution record has no trace data',
  '加载 Trace 数据失败': 'Failed to load trace data',
  '刷新 Trace 数据失败': 'Failed to refresh trace data',
  '确定删除？': 'Delete this item?',
  '确定删除该元素？': 'Delete this element?',
  '确定删除该操作？': 'Delete this action?',
  '确定删除该步骤？': 'Delete this step?',
  '确定删除该用例？': 'Delete this case?',
  '确定删除该页面？关联的元素也会被删除。': 'Delete this page? Related elements will also be deleted.',
  '确定删除此执行记录？关联的截图、视频、Trace文件将一并删除。': 'Delete this execution record? Related screenshots, videos, and trace files will be deleted too.',
  '确定删除此批量执行记录？关联的执行记录将一并删除。': 'Delete this batch execution record? Related execution records will be deleted too.',
  '确定要删除选中的用例吗？此操作不可恢复。': 'Delete the selected cases? This action cannot be undone.',
  '连接时间': 'Connected at',
  '状态已更新': 'Status updated',
  'IP地址': 'IP address',
  '模式': 'Mode',
  '手动执行': 'Manual',
  'API 触发': 'API',
  '定时执行': 'Scheduled',
  '待执行': 'Pending',
  '全部成功': 'All succeeded',
  '部分失败': 'Partially failed',
  '全部失败': 'All failed',
  '原始数据': 'Raw data',
  '文本': 'Text',
  '类型': 'Type',
  '是': 'Yes',
  '否': 'No',
  '切换页面URL': 'Navigate to URL',
  '失败重试次数': 'Retries on failure',
  '等待时间': 'Wait time',
  '等待(秒)': 'Wait (seconds)',
  'P0 - 冒烟': 'P0 - Smoke',
  'P1 - 核心': 'P1 - Core',
  'P2 - 重要': 'P2 - Important',
  'P3 - 一般': 'P3 - Normal',
  '点击 (click)': 'Click (click)',
  '双击 (dblclick)': 'Double click (dblclick)',
  '悬停 (hover)': 'Hover (hover)',
  '填充 (fill)': 'Fill (fill)',
  '输入 (type)': 'Type (type)',
  '清空 (clear)': 'Clear (clear)',
  '等待 (wait)': 'Wait (wait)',
  '截图 (screenshot)': 'Screenshot (screenshot)',
  '选择下拉 (select_option)': 'Select option (select_option)',
  '成功:': 'Passed:',
  '失败:': 'Failed:',
  '总计:': 'Total:',

  // ── 通用按钮 / 标签 ──
  '返回列表': 'Back to list',
  '上一条': 'Previous',
  '下一条': 'Next',
  '上一步': 'Previous',
  '下一步': 'Next',
  '保存': 'Save',
  '保存中...': 'Saving...',
  '导入': 'Import',
  '导出': 'Export',
  '导入/导出': 'Import / Export',
  '导入中...': 'Importing...',
  '导出中...': 'Exporting...',
  '开始导入': 'Start import',
  '开始导出': 'Start export',
  '导入用例': 'Import cases',
  '导出用例': 'Export cases',
  '重新导入': 'Re-import',
  '全选': 'Select all',
  '选择文件': 'Choose file',
  '添加规则': 'Add rule',
  '预览': 'Preview',
  '确认': 'Confirm',
  '创建人': 'Created by',
  '新建模版': 'Create template',
  '暂无模版': 'No templates',
  '管理模版': 'Manage templates',
  '模版名称': 'Template name',
  '模版类型': 'Template type',
  '模版配置': 'Template config',
  '编辑模版': 'Edit template',
  '启用状态': 'Enabled',
  '高优先级': 'High priority',
  '中优先级': 'Medium priority',
  '低优先级': 'Low priority',
  '最新版本': 'Latest version',
  '历史版本': 'Previous version',
  '导出报告': 'Export report',
  '分享报告': 'Share report',
  '完整报告': 'Full report',
  '专项分析': 'Specialized analysis',
  '评审报告': 'Review report',
  '已解决': 'Resolved',
  '标记已解决': 'Mark as resolved',
  '高': 'High',
  '低': 'Low',
  '全部': 'All',
  '全部类型': 'All types',
  '问题': 'Issues',
  '问题类型': 'Issue type',
  '错误': 'Errors',
  '建议': 'Suggestions',
  '建议：': 'Suggestion:',
  '优点': 'Strengths',
  '不足': 'Weaknesses',
  '优势': 'Strengths',

  // ── 模板导入导出（TemplateManagementView / TemplateFormModal / ExportModal / ImportModal）──
  '用例导入导出模版管理': 'Case import/export template management',
  '点击上方"新建模版"创建您的第一个导入导出模版': 'Click "Create template" above to create your first import/export template',
  '确定要删除此模版吗？': 'Are you sure you want to delete this template?',
  '请输入模版名称': 'Enter template name',
  '请输入模版描述': 'Enter template description',
  // TemplateFormModal — steps & labels
  '基本信息': 'Basic info',
  '表头配置': 'Header config',
  '字段映射': 'Field mapping',
  '值转换': 'Value conversion',
  '步骤解析': 'Step parsing',
  '上传样例 Excel 文件（可选）': 'Upload a sample Excel file (optional)',
  '表头行号': 'Header row number',
  '数据起始行号': 'Data start row number',
  '工作表名称': 'Sheet name',
  '默认第一个': 'First sheet by default',
  '解析表头': 'Parse headers',
  '识别到的表头列': 'Detected header columns',
  '将 Excel 列名映射到用例字段。带 * 的字段为必填。': 'Map Excel columns to case fields. Fields marked with * are required.',
  '请选择对应的 Excel 列': 'Select the corresponding Excel column',
  '请先在上一步解析表头或手动输入列名': 'Parse headers in the previous step or enter column names manually first',
  '手动输入 Excel 列名': 'Enter Excel column names manually',
  '输入列名，用逗号分隔，如: 用例名称,模块,前置条件,步骤,预期结果': 'Enter column names separated by commas, e.g.: Case name, Module, Preconditions, Steps, Expected result',
  '配置字段值的转换规则。例如将 Excel 中的 "高" 转换为系统中的 "P0"。': 'Configure value conversion rules. For example, convert "High" in Excel to "P0" in the system.',
  '用例等级转换': 'Case level conversion',
  'Excel中的值': 'Value in Excel',
  'Excel 中的值': 'Value in Excel',
  '转换为': 'Convert to',
  'P0 - 最高': 'P0 - Highest',
  'P1 - 高': 'P1 - High',
  'P2 - 中': 'P2 - Medium',
  'P3 - 低': 'P3 - Low',
  '步骤解析模式': 'Step parsing mode',
  '单元格合并模式': 'Merged cell mode',
  '所有步骤在一个单元格中，如 [1]步骤1\n[2]步骤2': 'All steps in one cell, e.g. [1]Step1\\n[2]Step2',
  '多行模式': 'Multi-row mode',
  '每个步骤占一行，用例信息在第一行': 'Each step on a separate row; case info on the first row',
  '模块路径分隔符': 'Module path separator',
  '如 / 或 >': 'e.g. / or >',
  '用于解析模块层级路径，如 "模块A/子模块B"': 'Used to parse module hierarchy paths, e.g. "ModuleA/SubModuleB"',
  // ExportModal
  '导出范围': 'Export scope',
  '导出所有用例': 'Export all cases',
  '导出当前项目的全部测试用例': 'Export all test cases in the current project',
  '导出选中用例': 'Export selected cases',
  '按模块导出': 'Export by module',
  '选择模块导出其下所有用例': 'Select a module to export all its cases',
  '当前项目暂无模块': 'No modules in the current project',
  '请选择要导出的模块': 'Select modules to export',
  '导出模版': 'Export template',
  '（可选）': '(optional)',
  '使用默认格式导出': 'Export with default format',
  '工作表': 'Sheet',
  '表头行': 'Header row',
  '数据起始': 'Data start',
  '数据起始行': 'Data start row',
  // ImportModal
  '导入完成': 'Import completed',
  '导入完成（有警告）': 'Import completed (with warnings)',
  '总行数': 'Total rows',
  '成功导入': 'Successfully imported',
  '选择模版': 'Select template',
  '上传文件': 'Upload file',
  '选择导入模版': 'Select an import template',
  '请选择导入模版': 'Select an import template',
  '解析模式': 'Parsing mode',
  '上传 Excel 文件': 'Upload Excel file',
  '点击或拖拽文件到此处上传': 'Click or drag a file here to upload',
  '支持 .xlsx, .xls 格式': 'Supports .xlsx and .xls formats',
  '请先在列表中选择用例': 'Select cases from the list first',

  // ── 需求评审报告（ReportDetailView / ReviewReportView / SpecializedReportView）──
  '完整度评分': 'Completeness score',
  '发现问题': 'Issues found',
  '评审时间': 'Review time',
  '评审总结': 'Review summary',
  '改进建议': 'Improvement suggestions',
  '问题分布': 'Issue distribution',
  '模块评审结果': 'Module review results',
  '详细问题列表': 'Detailed issue list',
  '按优先级筛选': 'Filter by priority',
  '规范性': 'Compliance',
  '清晰度': 'Clarity',
  '完整性': 'Completeness',
  '一致性': 'Consistency',
  '可行性': 'Feasibility',
  '可测性': 'Testability',
  '严重度:': 'Severity:',
  '解决说明：': 'Resolution note:',
  '暂无问题数据': 'No issue data',
  '暂无评审报告数据': 'No review report data',
  '该模块暂无发现问题': 'No issues found in this module',
  '该维度暂无发现问题': 'No issues found in this dimension',
  '暂无分析数据': 'No analysis data',
  // SpecializedReportView — analysis dimensions
  '完整性分析': 'Completeness analysis',
  '一致性分析': 'Consistency analysis',
  '可测性分析': 'Testability analysis',
  '可行性分析': 'Feasibility analysis',
  '清晰度分析': 'Clarity analysis',
  '逻辑分析': 'Logic analysis',
  '总体评价': 'Overall assessment',
  '分析总结': 'Analysis summary',
  '总分': 'Total score',
  '分': 'pts',
  '个': '',
  '个问题': 'issues',
  '个模块': 'modules',
  // Rating text
  '优秀': 'Excellent',
  '良好': 'Good',
  '中等': 'Fair',
  '需改进': 'Needs improvement',
  '较差': 'Poor',
  // ReviewReportView labels
  '模块内容': 'Module content',
  '模块评级': 'Module rating',
  '相关问题': 'Related issues',
  '推荐': 'Recommended',
  '级别': 'Level',

  // ── 测试用例详情（TestCaseDetail）──
  '测试用例详情': 'Test case details',
  '测试步骤': 'Test steps',
  '备注': 'Remarks',
  '上传截图': 'Upload screenshots',
  '暂无截图': 'No screenshots',
  '无法加载测试用例详情': 'Failed to load test case details',
  '标题（可选）': 'Title (optional)',
  '为这批截图添加标题': 'Add a title for these screenshots',
  '描述（可选）': 'Description (optional)',
  '描述截图内容': 'Describe the screenshot content',
  '步骤编号（可选）': 'Step number (optional)',
  '关联步骤': 'Related step',
  '页面URL（可选）': 'Page URL (optional)',
  '截图页面地址': 'Screenshot page URL',
  '点击选择图片或拖拽到此处': 'Click to select images or drag them here',
  '支持 JPG、PNG、GIF 格式，最多上传10张，单个文件不超过 10MB': 'Supports JPG, PNG, GIF. Up to 10 files, max 10 MB each.',
  '点击预览': 'Click to preview',
  '图片加载失败': 'Failed to load image',
  '图片信息': 'Image info',
  '所有图片': 'All images',
  '图片预览': 'Image preview',

  // ── 拆分配置（SplitOptionsModal）──
  '模块拆分配置': 'Module split settings',
  '拆分级别': 'Split level',
  '字数拆分': 'Split by word count',
  '按字数拆分 - 适合没有明确标题结构的文档': 'Split by word count — for documents without clear heading structure',
  '拆分配置': 'Split settings',
  '包含上下文（包含上级标题作为上下文）': 'Include context (include parent headings as context)',
  '文档结构分析': 'Document structure analysis',
  '拆分建议：': 'Split recommendations:',
  'H1标题：': 'H1 headings:',
  'H2标题：': 'H2 headings:',
  'H3标题：': 'H3 headings:',
  'H4标题：': 'H4 headings:',
  'H5标题：': 'H5 headings:',
  'H6标题：': 'H6 headings:',

  // ── 模块管理面板（ModuleManagementPanel）──
  '添加根模块': 'Add root module',
  '添加子模块': 'Add child module',
  '删除模块': 'Delete module',
  '删除模块失败': 'Failed to delete module',
  '删除模块时发生错误': 'An error occurred while deleting the module',
  '确认删除': 'Confirm deletion',

  // ── 审核状态 ──
  '待审核': 'Pending',
  '优化': 'Optimize',
  '优化待审核': 'Re-review',
  '不可用': 'N/A',

  // ── 需求文档状态 ──
  '已上传': 'Uploaded',
  '处理中': 'Processing',
  '模块拆分中': 'Splitting modules',
  '用户调整中': 'User reviewing',
  '待评审': 'Ready for review',
  '评审中': 'Reviewing',
  '评审完成': 'Review completed',
  '处理失败': 'Failed',
  ...API_TESTING_LEGACY_EXACT_EN_MAP,
};

const LEGACY_EXACT_ZH_MAP = Object.entries(LEGACY_EXACT_EN_MAP).reduce<Record<string, string>>((result, [zh, en]) => {
  if (!(en in result)) {
    result[en] = zh;
  }

  return result;
}, {
  ...API_TESTING_LEGACY_EXACT_ZH_OVERRIDES,
});

const REQUIREMENT_ANALYSIS_STEP_EN_MAP: Record<string, string> = {
  '完整性': 'Completeness',
  '一致性': 'Consistency',
  '可测性': 'Testability',
  '可行性': 'Feasibility',
  '清晰度': 'Clarity',
  '逻辑': 'Logic',
};

const REQUIREMENT_ANALYSIS_STEP_ZH_MAP = Object.entries(REQUIREMENT_ANALYSIS_STEP_EN_MAP).reduce<Record<string, string>>((result, [zh, en]) => {
  result[en] = zh;
  return result;
}, {});

const LEGACY_REGEX_EN_MAP: Array<[RegExp, (...groups: string[]) => string]> = [
  // 操作日志：将 "动作 模块" 复合描述翻译为英文（如"列表查询 项目管理" → "List Project Management"）
  [/^([\u4e00-\u9fff]+)\s+([\u4e00-\u9fff\w][\u4e00-\u9fff\w\s\-\/()（）]*)$/, (action, module) => {
    const translatedAction = LEGACY_EXACT_EN_MAP[action] ?? action;
    const translatedModule = LEGACY_EXACT_EN_MAP[module] ?? module;
    return `${translatedAction} ${translatedModule}`;
  }],
  [/^已选择\s*(\d+)\s*张图片$/, (count) => `${count} image(s) selected`],
  [/^已粘贴\s*(\d+)\s*张图片$/, (count) => `${count} images pasted`],
  [/^工具\s+(.+)\s+已被设为始终拒绝，自动拒绝执行$/, (toolName) => `Tool ${toolName} is set to always deny and was rejected automatically`],
  [/^成功删除\s+(\d+)\s+个对话$/, (count) => `Deleted ${count} conversation(s) successfully`],
  [/^删除完成：成功\s+(\d+)\s+个，失败\s+(\d+)\s+个$/, (ok, failed) => `Delete completed: ${ok} succeeded, ${failed} failed`],
  [/^成功获取\s+(\d+)\s+个模型$/, (count) => `Fetched ${count} model(s) successfully`],
  [/^(.+)\s+已存在，无需重复上传$/, (fileName) => `${fileName} already exists and will not be uploaded again`],
  [/^已设置\s+(.+)\s+为始终允许$/, (name) => `Always allow set for ${name}`],
  [/^已设置\s+(.+)\s+为始终拒绝$/, (name) => `Always deny set for ${name}`],
  [/^操作失败:\s+(.+)$/, (detail) => `Action failed: ${detail}`],
  [/^加载失败:\s+(.+)$/, (detail) => `Load failed: ${detail}`],
  [/^保存失败:\s+(.+)$/, (detail) => `Save failed: ${detail}`],
  [/^删除失败:\s+(.+)$/, (detail) => `Delete failed: ${detail}`],
  [/^获取Key列表失败:\s+(.+)$/, (detail) => `Failed to fetch key list: ${detail}`],
  [/^操作失败:\s+(.+)$/, (detail) => `Action failed: ${detail}`],
  [/^开始批量执行\s+(\d+)\s+个用例$/, (count) => `Starting batch execution of ${count} case(s)`],
  [/^用例执行成功:\s+(\d+)\/(\d+)\s+步骤通过$/, (passed, total) => `Case execution succeeded: ${passed}/${total} steps passed`],
  [/^用例执行成功[:：]\s*通过\s*(\d+)\/(\d+)$/, (passed, total) => `Case execution succeeded: ${passed}/${total} passed`],
  [/^用例执行成功！通过\s*(\d+)\/(\d+)$/, (passed, total) => `Case execution succeeded! ${passed}/${total} passed`],
  [/^用例执行失败:\s+(.+)$/, (detail) => `Case execution failed: ${detail}`],
  [/^执行成功:\s+(\d+)\/(\d+)\s+步骤通过$/, (passed, total) => `Execution succeeded: ${passed}/${total} steps passed`],
  [/^执行失败:\s+(.+)$/, (detail) => `Execution failed: ${detail}`],
  [/^元素操作\s+(.+)\s+执行成功$/, (action) => `Element action ${action} executed successfully`],
  [/^断言操作\s+(.+)\s+执行成功$/, (action) => `Assertion action ${action} executed successfully`],
  [/^SQL操作\s+(.+)\s+执行成功$/, (action) => `SQL action ${action} executed successfully`],
  [/^自定义变量\s+(.+)\s+执行成功$/, (action) => `Custom variable action ${action} executed successfully`],
  [/^条件判断\s+(.+)\s+执行成功$/, (action) => `Condition action ${action} executed successfully`],
  [/^成功删除\s+(\d+)\s+个用例$/, (count) => `Deleted ${count} case(s) successfully`],
  [/^开始执行用例:\s+(.+)$/, (name) => `Starting case execution: ${name}`],
  [/^元素管理\s*-\s*(.*)$/, (name) => `Element Management - ${name}`.trim()],
  [/^步骤详情\s*-\s*(.*)$/, (name) => `Step Details - ${name}`.trim()],
  [/^用例步骤\s*-\s*(.*)$/, (name) => `Case Steps - ${name}`.trim()],
  [/^确定要删除模块\s+"(.+)"\s+吗？$/, (name) => `Delete module "${name}"?`],
  [/^确定要删除模块\s+"(.+)"\s+吗？此操作不可恢复。$/, (name) => `Delete module "${name}"? This action cannot be undone.`],
  [/^强制更新完成！更新了\s+(\d+)\s+个提示词$/, (count) => `Force update completed. Updated ${count} prompt(s).`],
  [/^初始化完成！创建了\s+(\d+)\s+个提示词，跳过\s+(\d+)\s+个$/, (created, skipped) => `Initialization completed. Created ${created} prompt(s) and skipped ${skipped}.`],
  [/^会话状态：(.+)$/, (value) => `Session status: ${value}`],
  [/^更新时间：(.+)$/, (value) => `Updated at: ${value}`],
  // Import modal — dynamic counts
  [/^发现\s*(\d+)\s*条同名用例$/, (count) => `Found ${count} duplicate case name(s)`],
  [/^(\d+)\s*条导入错误$/, (count) => `${count} import error(s)`],
  [/^.*还有\s*(\d+)\s*条$/, (count) => `... and ${count} more`],
  [/^已选择\s*(\d+)\s*条用例$/, (count) => `${count} case(s) selected`],
  // SplitOptionsModal — dynamic format recommendation
  [/^(.+)格式文档建议使用字数拆分$/, (fmt) => `${fmt} format documents are recommended to use word count splitting`],
  [/^文件不存在[:：]\s*([\s\S]+)$/u, (path) => `File not found: ${path}`],
  [/^(完整性|一致性|可测性|可行性|清晰度|逻辑)分析完成$/u, (name) => `${REQUIREMENT_ANALYSIS_STEP_EN_MAP[name] ?? name} analysis completed`],
  [/^(完整性|一致性|可测性|可行性|清晰度|逻辑)分析完成，评分[:：]\s*([^,，]+)(?:[，,]\s*问题数[:：]\s*(.+))?$/u, (name, score, issues) => issues
    ? `${REQUIREMENT_ANALYSIS_STEP_EN_MAP[name] ?? name} analysis completed, score: ${score}, issues: ${issues}`
    : `${REQUIREMENT_ANALYSIS_STEP_EN_MAP[name] ?? name} analysis completed, score: ${score}`],
  [/^(完整性|一致性|可测性|可行性|清晰度|逻辑)分析完成，一致性评分[:：]\s*(.+)$/u, (name, score) => `${REQUIREMENT_ANALYSIS_STEP_EN_MAP[name] ?? name} analysis completed, consistency score: ${score}`],
  [/^文档分析完成，总体评分[:：]\s*(.+)$/u, (score) => `Document analysis completed, overall score: ${score}`],
  [/^全局分析完成，总体评分[:：]\s*(.+)$/u, (score) => `Global analysis completed, overall score: ${score}`],
  [/^评审完成[:：]\s*(.+)[，,]\s*总体评分[:：]\s*(.+)$/u, (title, score) => `Review completed: ${title}, overall score: ${score}`],
  [/^Reranker 服务测试成功！\s*服务运行正常$/u, () => 'Reranker test passed! Service is running normally'],
  [/^Reranker 测试失败[:：]\s*(.+)$/u, (detail) => `Reranker test failed: ${detail}`],
  [/^无法连接到 Reranker 服务[:：]\s*(.+)$/u, (detail) => `Unable to connect to reranker service: ${detail}`],
  // SpecializedReportView — heading level label
  [/^(.+)级别$/, (level) => `${level} level`],
  // Image preview with count
  [/^图片预览\s*\((\d+)\/(\d+)\)$/, (cur, total) => `Image preview (${cur}/${total})`],
  [/^所有图片\s*\((\d+)\)$/, (count) => `All images (${count})`],
  ...API_TESTING_LEGACY_REGEX_EN_MAP,
];

const LEGACY_REGEX_ZH_MAP: Array<[RegExp, (...groups: string[]) => string]> = [
  [/^(Completeness|Consistency|Testability|Feasibility|Clarity|Logic) analysis completed$/u, (name) => `${REQUIREMENT_ANALYSIS_STEP_ZH_MAP[name] ?? name}分析完成`],
  [/^(Completeness|Consistency|Testability|Feasibility|Clarity|Logic) analysis completed, score:\s*([^,，]+)(?:,\s*issues:\s*(.+))?$/u, (name, score, issues) => issues
    ? `${REQUIREMENT_ANALYSIS_STEP_ZH_MAP[name] ?? name}分析完成，评分: ${score}, 问题数: ${issues}`
    : `${REQUIREMENT_ANALYSIS_STEP_ZH_MAP[name] ?? name}分析完成，评分: ${score}`],
  [/^(Completeness|Consistency|Testability|Feasibility|Clarity|Logic) analysis completed, consistency score:\s*(.+)$/u, (name, score) => `${REQUIREMENT_ANALYSIS_STEP_ZH_MAP[name] ?? name}分析完成，一致性评分: ${score}`],
  [/^Document analysis completed, overall score:\s*(.+)$/u, (score) => `文档分析完成，总体评分: ${score}`],
  [/^Global analysis completed, overall score:\s*(.+)$/u, (score) => `全局分析完成，总体评分: ${score}`],
  [/^Review completed:\s*(.+),\s*overall score:\s*(.+)$/u, (title, score) => `评审完成: ${title}, 总体评分: ${score}`],
  [/^Reranker test passed!\s*Service is running normally$/u, () => 'Reranker 服务测试成功！服务运行正常'],
  [/^Reranker test failed:\s*(.+)$/u, (detail) => `Reranker 测试失败: ${detail}`],
  [/^Unable to connect to reranker service:\s*(.+)$/u, (detail) => `无法连接到 Reranker 服务: ${detail}`],
  ...API_TESTING_LEGACY_REGEX_ZH_MAP,
];

export const translateLegacyText = (text: string, locale: AppLocale) => {
  const trimmed = text.trim();
  if (!trimmed) {
    return text;
  }

  const exactMap = locale === 'en-US' ? LEGACY_EXACT_EN_MAP : LEGACY_EXACT_ZH_MAP;
  const regexMap = locale === 'en-US' ? LEGACY_REGEX_EN_MAP : LEGACY_REGEX_ZH_MAP;

  const exact = exactMap[trimmed];
  if (exact) {
    return preserveWhitespace(text, exact);
  }

  for (const [pattern, resolver] of regexMap) {
    const match = trimmed.match(pattern);
    if (!match) {
      continue;
    }

    return preserveWhitespace(text, resolver(...match.slice(1)));
  }

  return text;
};

export const translateMaybeMessage = (
  value: string,
  locale: AppLocale,
  key?: AppMessageKey,
  params?: MessageParams,
) => {
  if (key) {
    return translate(locale, key, params);
  }

  return translateLegacyText(value, locale);
};
