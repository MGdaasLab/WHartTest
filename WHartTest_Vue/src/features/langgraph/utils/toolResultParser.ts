export interface ToolFileAttachment {
  name: string;
  url: string;
  path?: string;
  mimeType?: string;
  size?: number;
}

export interface ToolResultDisplayPayload {
  content: string;
  imageDataUrl?: string;
  fileAttachments: ToolFileAttachment[];
}

const safeStringify = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return '';
  try {
    return JSON.stringify(value);
  } catch {
    return '[无法序列化的数据]';
  }
};

const tryParseJsonString = (value: string): unknown | null => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
};

const toImageDataUrl = (item: Record<string, unknown>): string | undefined => {
  const rawBase64 = item.base64;
  if (typeof rawBase64 !== 'string' || !rawBase64.trim()) return undefined;
  const base64 = rawBase64.trim();
  if (base64.startsWith('data:image/')) return base64;

  const mimeType =
    (typeof item.mime_type === 'string' && item.mime_type.trim()) ||
    (typeof item.mimeType === 'string' && item.mimeType.trim()) ||
    'image/jpeg';

  return `data:${mimeType};base64,${base64}`;
};

const basenameFromPath = (value: string): string => {
  const normalized = value.replace(/\\/g, '/');
  const segments = normalized.split('/').filter(Boolean);
  return segments[segments.length - 1] || value;
};

const toFileAttachment = (item: Record<string, unknown>): ToolFileAttachment | null => {
  const url = typeof item.url === 'string' ? item.url.trim() : '';
  const path = typeof item.path === 'string' ? item.path.trim() : '';
  const nameCandidate =
    (typeof item.name === 'string' && item.name.trim()) ||
    (path ? basenameFromPath(path) : '') ||
    (url ? basenameFromPath(url.split('?')[0]) : '');

  if (!url || !nameCandidate) {
    return null;
  }

  const attachment: ToolFileAttachment = {
    name: nameCandidate,
    url,
  };

  if (path) {
    attachment.path = path;
  }

  const mimeType =
    (typeof item.mime_type === 'string' && item.mime_type.trim()) ||
    (typeof item.mimeType === 'string' && item.mimeType.trim()) ||
    '';
  if (mimeType) {
    attachment.mimeType = mimeType;
  }

  const sizeValue = item.size;
  if (typeof sizeValue === 'number' && Number.isFinite(sizeValue)) {
    attachment.size = sizeValue;
  }

  return attachment;
};

export const parseToolResultDisplayPayload = (rawToolOutput: unknown): ToolResultDisplayPayload => {
  let normalized: unknown = rawToolOutput;
  if (typeof normalized === 'string') {
    const parsed = tryParseJsonString(normalized);
    if (parsed !== null) {
      normalized = parsed;
    }
  }

  if (Array.isArray(normalized)) {
    let imageDataUrl: string | undefined;
    const textParts: string[] = [];
    const fileAttachments: ToolFileAttachment[] = [];

    normalized.forEach((item) => {
      if (item && typeof item === 'object') {
        const obj = item as Record<string, unknown>;
        const itemType = typeof obj.type === 'string' ? obj.type.toLowerCase() : '';

        if (!imageDataUrl && (itemType === 'image' || typeof obj.base64 === 'string')) {
          imageDataUrl = toImageDataUrl(obj) || imageDataUrl;
          if (itemType === 'image') {
            return;
          }
        }

        if (itemType === 'file') {
          const attachment = toFileAttachment(obj);
          if (attachment) {
            fileAttachments.push(attachment);
            return;
          }
        }

        if (typeof obj.text === 'string' && obj.text.trim()) {
          textParts.push(obj.text);
          return;
        }

        if (itemType !== 'image' && itemType !== 'file' && !('base64' in obj)) {
          const serialized = safeStringify(obj);
          if (serialized) {
            textParts.push(serialized);
          }
        }
        return;
      }

      if (typeof item === 'string') {
        textParts.push(item);
      } else {
        const serialized = safeStringify(item);
        if (serialized) {
          textParts.push(serialized);
        }
      }
    });

    const content = textParts.filter((part) => part && part.trim()).join('\n');
    return {
      content:
        content ||
        (fileAttachments.length > 0
          ? `已生成 ${fileAttachments.length} 个文件，可直接下载。`
          : imageDataUrl
            ? '[工具返回了图片]'
            : ''),
      imageDataUrl,
      fileAttachments,
    };
  }

  if (normalized && typeof normalized === 'object') {
    const obj = normalized as Record<string, unknown>;
    const itemType = typeof obj.type === 'string' ? obj.type.toLowerCase() : '';
    const imageDataUrl =
      itemType === 'image' || typeof obj.base64 === 'string'
        ? toImageDataUrl(obj)
        : undefined;

    const fileAttachments =
      itemType === 'file'
        ? [toFileAttachment(obj)].filter((item): item is ToolFileAttachment => Boolean(item))
        : [];

    const text =
      typeof obj.text === 'string' && obj.text.trim()
        ? obj.text
        : '';

    return {
      content:
        text ||
        (fileAttachments.length > 0
          ? `已生成 ${fileAttachments.length} 个文件，可直接下载。`
          : imageDataUrl
            ? '[工具返回了图片]'
            : safeStringify(normalized)),
      imageDataUrl,
      fileAttachments,
    };
  }

  return { content: safeStringify(normalized), fileAttachments: [] };
};
