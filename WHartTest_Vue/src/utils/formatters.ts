export const formatDateTime = (dateString?: string): string => {
  if (!dateString) return '-';
  try {
    const date = new Date(dateString);
    // 检查日期是否有效
    if (isNaN(date.getTime())) {
      return '-';
    }
    // 使用 toLocaleString 来同时显示日期和时间
    return date.toLocaleString();
  } catch (error) {
    console.error("Error formatting datetime:", dateString, error);
    return '-';
  }
};

// 为了兼容旧代码，同时导出 formatDate
export const formatDate = formatDateTime;

export const getLevelColor = (level?: string): string => {
  if (!level) return 'default';
  switch (level) {
    case 'P0': return 'red';
    case 'P1': return 'orange';
    case 'P2': return 'blue';
    case 'P3': return 'green';
    default: return 'default';
  }
};

export const formatDuration = (seconds?: number): string => {
  if (seconds === undefined || seconds === null || isNaN(seconds)) {
    return '-';
  }
  if (seconds < 60) {
    return `${seconds.toFixed(1)}秒`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  if (remainingSeconds === 0) {
    return `${minutes}分`;
  }
  return `${minutes}分${remainingSeconds}秒`;
};

// 审核状态选项
export const REVIEW_STATUS_OPTIONS = [
  { value: 'pending_review', label: '待审核', color: 'orange' },
  { value: 'approved', label: '通过', color: 'green' },
  { value: 'needs_optimization', label: '优化', color: 'blue' },
  { value: 'optimization_pending_review', label: '优化待审核', color: 'cyan' },
  { value: 'unavailable', label: '不可用', color: 'red' },
] as const;

export const getReviewStatusLabel = (status?: string): string => {
  if (!status) return '待审核';
  const option = REVIEW_STATUS_OPTIONS.find(o => o.value === status);
  return option?.label || status;
};

export const getReviewStatusColor = (status?: string): string => {
  if (!status) return 'orange';
  const option = REVIEW_STATUS_OPTIONS.find(o => o.value === status);
  return option?.color || 'gray';
};

// 测试类型选项
export const TEST_TYPE_OPTIONS = [
  { value: 'smoke', label: '冒烟测试' },
  { value: 'functional', label: '功能测试' },
  { value: 'boundary', label: '边界测试' },
  { value: 'exception', label: '异常测试' },
  { value: 'permission', label: '权限测试' },
  { value: 'security', label: '安全测试' },
  { value: 'compatibility', label: '兼容性测试' },
] as const;

export const getTestTypeLabel = (testType?: string): string => {
  if (!testType) return '功能测试';
  const option = TEST_TYPE_OPTIONS.find(o => o.value === testType);
  return option?.label || testType;
};