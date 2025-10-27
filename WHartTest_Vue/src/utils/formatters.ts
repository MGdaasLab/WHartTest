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