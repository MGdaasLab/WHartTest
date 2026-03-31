<template>
  <div :class="['message-wrapper', messageClass]">
    <!-- Step Separator: 步骤分隔符 -->
    <template v-if="message.messageType === 'step_separator'">
      <div class="step-separator">
        <div class="step-separator-line"></div>
        <span class="step-separator-label">{{ message.content }}</span>
        <div class="step-separator-line"></div>
      </div>
    </template>

    <!-- Agent Step 消息：紧凑的进度指示器 -->
    <template v-else-if="message.messageType === 'agent_step'">
      <!-- ✅ 统一使用与历史记录相同的分隔线样式 -->
      <div class="step-separator">
        <div class="step-separator-line"></div>
        <span class="step-separator-label">{{ agentStepLabel }}</span>
        <div class="step-separator-line"></div>
      </div>
    </template>

    <!-- 其他消息类型：使用头像+气泡布局 -->
    <template v-else>
      <div class="avatar">
        <img v-if="message.messageType === 'ai'" :src="brandLogoUrl" alt="AI Avatar" class="avatar-img" />
        <div v-else class="avatar-img" :class="avatarClass">
          <icon-tool v-if="message.messageType === 'tool'" class="tool-avatar-icon" />
          <span v-else>{{ avatarText }}</span>
        </div>
      </div>
      <div class="message-content">
      <!-- 图片显示（在消息气泡之前） -->
      <div v-if="toolImageSrc && isThisImageFloating" class="tool-image-float-placeholder" @click="emit('float-tool-image', toolImageSrc)">
        <img :src="toolImageSrc" alt="工具截图" class="float-placeholder-thumb" />
        <span class="float-placeholder-label">悬浮预览中</span>
      </div>
      <div v-else-if="isToolImage" class="message-image-container">
        <img
          :src="toolImageSrc!"
          alt="上传的图片"
          class="message-image"
        />
        <div v-if="isToolImage" class="float-action-btn" @click="emit('float-tool-image', toolImageSrc!)">
          悬浮
        </div>
      </div>
      <div
        v-else-if="messageImageSrcList.length > 0"
        class="message-image-container"
        :class="{ 'message-image-grid': messageImageSrcList.length > 1 }"
      >
        <img
          v-for="(imageSrc, index) in messageImageSrcList"
          :key="`${imageSrc}-${index}`"
          :src="imageSrc"
          :alt="`上传的图片 ${index + 1}`"
          class="message-image"
          :class="{ 'message-image-multi': messageImageSrcList.length > 1 }"
        />
      </div>
      
      <div ref="messageBubbleRef" class="message-bubble">
        <div v-if="message.isLoading" class="typing-indicator">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div v-else-if="message.messageType === 'tool'" class="tool-message-content">
          <div v-if="message.toolName" class="tool-header">
            🔧 {{ message.toolName }}
          </div>
          <div
            :class="['tool-content', { 'collapsed': !message.isExpanded && shouldCollapse }]"
            :key="message.content"
            v-html="formattedContent"
          ></div>
          <div v-if="toolFileAttachments.length > 0" class="tool-file-list">
            <div v-for="file in toolFileAttachments" :key="`${file.url}-${file.name}`" class="tool-file-item">
              <div class="tool-file-main">
                <div class="tool-file-name">{{ file.name }}</div>
                <div class="tool-file-meta">
                  <span v-if="file.mimeType">{{ file.mimeType }}</span>
                  <span v-if="file.size !== undefined">{{ formatFileSize(file.size) }}</span>
                </div>
              </div>
              <div class="tool-file-actions">
                <a :href="file.url" target="_blank" rel="noopener noreferrer" class="tool-file-link">打开</a>
                <a :href="file.url" :download="file.name" class="tool-file-link">下载</a>
              </div>
            </div>
          </div>
          <div
            v-if="shouldCollapse"
            class="expand-button"
            @click="$emit('toggle-expand', message)"
          >
            {{ message.isExpanded ? '收起' : '展开' }}
            <i :class="message.isExpanded ? 'icon-up' : 'icon-down'"></i>
          </div>
          <div v-if="canPreviewDiagram || canPreviewHtml" class="diagram-preview-actions">
            <a-button v-if="canPreviewDiagram" type="outline" size="mini" class="diagram-preview-btn" @click="handlePreviewDiagram">
              <template #icon><icon-eye /></template>
              预览图表
            </a-button>
            <a-button v-if="canPreviewHtml" type="outline" size="mini" class="diagram-preview-btn" @click="handlePreviewHtml">
              <template #icon><icon-eye /></template>
              预览HTML
            </a-button>
            <a-button v-if="canPreviewDiagram" type="text" size="mini" class="diagram-preview-btn" @click="openDiagramInNewTab">
              新标签打开
            </a-button>
          </div>
        </div>

        <!-- 🎨 思考过程消息（可折叠） -->
        <div v-else-if="message.isThinkingProcess" class="thinking-process-content">
          <div class="thinking-header" @click="$emit('toggle-expand', message)">
            <span class="thinking-label">思考过程</span>
          </div>
          <div
            v-show="message.isThinkingExpanded"
            :key="message.content"
            class="thinking-body"
            v-html="formattedContent"
          ></div>
        </div>

        <!-- 普通AI消息 -->
        <div
          v-else
          :key="message.content"
          :class="{ 'streaming-content': isStreamingMessage }"
          v-html="formattedContent"
        ></div>
        <div v-if="canPreviewHtml && message.messageType === 'ai'" class="diagram-preview-actions">
          <a-button type="outline" size="mini" class="diagram-preview-btn" @click="handlePreviewHtml">
            <template #icon><icon-eye /></template>
            预览HTML
          </a-button>
        </div>
      </div>

      <!-- 消息操作按钮 -->
      <div v-if="showActions" class="message-actions">
        <a-tooltip content="复制" mini>
          <a-button type="text" size="mini" class="action-btn" @click="handleCopy">
            <template #icon><icon-copy /></template>
          </a-button>
        </a-tooltip>
        <a-tooltip v-if="canQuote" content="引用" mini>
          <a-button type="text" size="mini" class="action-btn" @click="$emit('quote', message)">
            <template #icon><icon-reply /></template>
          </a-button>
        </a-tooltip>
        <a-tooltip v-if="canRetry" content="重试" mini>
          <a-button type="text" size="mini" class="action-btn" @click="$emit('retry', message)">
            <template #icon><icon-refresh /></template>
          </a-button>
        </a-tooltip>
        <a-tooltip v-if="canDelete" content="删除" mini>
          <a-button type="text" size="mini" class="action-btn action-btn-danger" @click="$emit('delete', message)">
            <template #icon><icon-delete /></template>
          </a-button>
        </a-tooltip>
      </div>

      <div class="message-time">{{ message.time }}</div>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, onUpdated, ref, watch } from 'vue';
import { Button as AButton, Tooltip as ATooltip, Message } from '@arco-design/web-vue';
import { IconCopy, IconReply, IconRefresh, IconDelete, IconEye, IconTool } from '@arco-design/web-vue/es/icon';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { brandLogoUrl } from '@/utils/assetUrl';
import { extractDiagramToolPayload } from '../utils/diagramToolParser';
import { extractHtmlPreviewContent } from '../utils/htmlPreviewParser';
import type { ToolFileAttachment } from '../utils/toolResultParser';
import { parseToolResultDisplayPayload } from '../utils/toolResultParser';

// 配置marked以确保代码块正确渲染
// marked v5+ API发生了变化，许多选项被移除或更改。
// 此处我们依赖默认配置，并使用DOMPurify进行XSS净化。
/*
marked.setOptions({
  breaks: true,
  gfm: true,
  pedantic: false,
  smartLists: true,
  smartypants: false,
  xhtml: false
});
*/

interface ChatMessage {
  content: string;
  isUser: boolean;
  time: string;
  isLoading?: boolean;
  messageType?: 'human' | 'ai' | 'tool' | 'system' | 'agent_step' | 'step_separator';
  toolName?: string; // 工具名称
  isExpanded?: boolean;
  isStreaming?: boolean; // 标识是否正在流式输出
  imageBase64?: string; // 消息携带的图片(Base64)
  imageDataUrl?: string; // 完整的图片Data URL
  fileAttachments?: ToolFileAttachment[]; // 工具返回的可下载文件
  imageBase64List?: string[]; // 多张图片(Base64)
  imageDataUrls?: string[]; // 多张图片Data URL
  isThinkingProcess?: boolean; // 是否是思考过程
  isThinkingExpanded?: boolean; // 思考过程是否展开
  // Agent Step 专用字段
  stepNumber?: number;
  maxSteps?: number;
  stepStatus?: 'start' | 'complete' | 'error';
  // Step Separator 专用字段
  isStepSeparator?: boolean;
}

interface Props {
  message: ChatMessage;
  floatingToolImageSrc?: string | null;
}

const props = withDefaults(defineProps<Props>(), {
  floatingToolImageSrc: null,
});

const emit = defineEmits<{
  'toggle-expand': [message: ChatMessage];
  'quote': [message: ChatMessage];
  'retry': [message: ChatMessage];
  'delete': [message: ChatMessage];
  'preview-diagram': [payload: { xml: string; sourceMessage: ChatMessage }];
  'preview-html': [payload: { html: string; sourceMessage: ChatMessage }];
  'tool-image-detected': [src: string];
  'float-tool-image': [src: string];
}>();

// 工具图片相关
const toImageDataUrl = (base64?: string) => {
  return base64 ? `data:image/jpeg;base64,${base64}` : null;
};

const toolImageSrc = computed(() => {
  if (props.message.messageType !== 'tool') return null;
  return props.message.imageDataUrl || toImageDataUrl(props.message.imageBase64);
});

const isToolImage = computed(() => props.message.messageType === 'tool' && !!toolImageSrc.value);

const isThisImageFloating = computed(() => {
  return isToolImage.value && props.floatingToolImageSrc === toolImageSrc.value;
});

const messageImageSrcList = computed(() => {
  if (props.message.messageType === 'tool') {
    return [];
  }

  if (Array.isArray(props.message.imageDataUrls) && props.message.imageDataUrls.length > 0) {
    return props.message.imageDataUrls.filter((item): item is string => Boolean(item));
  }

  if (Array.isArray(props.message.imageBase64List) && props.message.imageBase64List.length > 0) {
    return props.message.imageBase64List
      .map((item) => toImageDataUrl(item))
      .filter((item): item is string => Boolean(item));
  }

  const singleImage = props.message.imageDataUrl || toImageDataUrl(props.message.imageBase64);
  return singleImage ? [singleImage] : [];
});

// 工具图片被检测到时通知父组件
onMounted(() => {
  if (toolImageSrc.value) emit('tool-image-detected', toolImageSrc.value);
});
watch(toolImageSrc, (src) => {
  if (src) emit('tool-image-detected', src);
});

// 操作按钮可见性
const showActions = computed(() => {
  const type = props.message.messageType;
  return !['step_separator', 'agent_step'].includes(type || '') && !props.message.isLoading;
});

const canQuote = computed(() => ['human', 'ai'].includes(props.message.messageType || ''));
const canRetry = computed(() => ['human', 'ai'].includes(props.message.messageType || '') && !props.message.isStreaming && !props.message.isLoading);
const canDelete = computed(() => props.message.messageType !== 'system' && showActions.value);

const htmlPreviewContent = computed(() => {
  if (props.message.isLoading) return null;
  return extractHtmlPreviewContent(props.message.content);
});

const canPreviewHtml = computed(() => {
  return Boolean(htmlPreviewContent.value);
});

const toolFileAttachments = computed(() => {
  if (props.message.messageType !== 'tool') return [];
  if (Array.isArray(props.message.fileAttachments) && props.message.fileAttachments.length > 0) {
    return props.message.fileAttachments;
  }
  return parseToolResultDisplayPayload(props.message.content).fileAttachments;
});

const formatFileSize = (size: number) => {
  if (!Number.isFinite(size) || size < 0) return '';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`;
};
const messageBubbleRef = ref<HTMLElement | null>(null);
let previewScrollRafId: number | null = null;

// 复制到剪贴板（兼容HTTP环境）
const handleCopy = async () => {
  try {
    // 优先使用 Clipboard API（HTTPS或localhost可用）
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(props.message.content);
      Message.success('复制成功');
      return;
    }
    
    // 回退方案：使用 document.execCommand（兼容HTTP）
    const textArea = document.createElement('textarea');
    textArea.value = props.message.content;
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    textArea.style.top = '-9999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    const successful = document.execCommand('copy');
    document.body.removeChild(textArea);
    
    if (successful) {
      Message.success('复制成功');
    } else {
      Message.error('复制失败，请手动复制');
    }
  } catch (error) {
    console.error('复制失败:', error);
    Message.error('复制失败，请手动复制');
  }
};

// 消息样式类
const messageClass = computed(() => {
  // ✅ agent_step 和 step_separator 使用相同的容器样式
  if (props.message.messageType === 'step_separator' || props.message.messageType === 'agent_step') {
    return 'step-separator-message';
  }
  if (props.message.isUser) return 'user-message';
  if (props.message.messageType === 'tool') return 'tool-message';
  return 'ai-message';
});

// Agent Step 标签文本 (与历史记录格式保持一致)
const agentStepLabel = computed(() => {
  const step = props.message.stepNumber;
  const max = props.message.maxSteps;
  
  // 优先使用 maxSteps，如果没有则默认为 500 (与后端默认值一致)
  const maxStepsDisplay = max !== undefined ? max : 500;
  
  if (step !== undefined) {
    return `步骤 ${step}/${maxStepsDisplay}`;
  }
  return '步骤';
});

// 头像样式类
const avatarClass = computed(() => {
  if (props.message.isUser) return 'user-avatar';
  if (props.message.messageType === 'tool') return 'tool-avatar';
  return 'ai-avatar';
});

// 头像文本
const avatarText = computed(() => {
  if (props.message.isUser) return '你';
  if (props.message.messageType === 'tool') return 'MCP';
  return ''; // AI消息使用图片，不需要文本
});

// 判断是否为正在流式更新的消息
const isStreamingMessage = computed(() => {
  return props.message.messageType === 'ai' &&
         !props.message.isLoading &&
         props.message.isStreaming === true &&
         props.message.content.length > 0;
});

// 从工具消息中提取图表XML（display_diagram/edit_diagram）
const diagramPayload = computed(() => {
  if (props.message.messageType !== 'tool') return null;
  return extractDiagramToolPayload(props.message.content);
});

// 判断工具消息是否需要折叠
const shouldCollapse = computed(() => {
  if (props.message.messageType !== 'tool') return false;

  // 图表工具结果（display/edit）默认折叠，避免大段JSON/XML占据聊天区
  if (diagramPayload.value?.action === 'display' || diagramPayload.value?.action === 'edit') {
    return true;
  }

  const lines = props.message.content.split('\n').length;
  return lines > 4;
});

const canPreviewDiagram = computed(() => {
  return Boolean(diagramPayload.value?.xml);
});

const shouldWrapCodeBlocks = computed(() => {
  return props.message.messageType === 'ai' && !props.message.isThinkingProcess;
});

const diagramPreviewUrl = computed(() => {
  if (!diagramPayload.value?.xml) return '';
  return `https://app.diagrams.net/?splash=0#R${encodeURIComponent(diagramPayload.value.xml)}`;
});

const handlePreviewDiagram = () => {
  if (!diagramPayload.value?.xml) return;
  emit('preview-diagram', {
    xml: diagramPayload.value.xml,
    sourceMessage: props.message
  });
};

const openDiagramInNewTab = () => {
  if (!diagramPreviewUrl.value) return;
  window.open(diagramPreviewUrl.value, '_blank', 'noopener,noreferrer');
};

const handlePreviewHtml = () => {
  if (!htmlPreviewContent.value) return;
  emit('preview-html', {
    html: htmlPreviewContent.value,
    sourceMessage: props.message
  });
};

const REQUIREMENT_DOC_ID_RE = /需求文档ID[:：]\s*([0-9a-fA-F-]{36})/;
const CODE_LANG_CLASS_RE = /\blanguage-([a-zA-Z0-9_+-]+)\b/;

const replaceDocImgPlaceholders = (content: string): string => {
  if (!content || !content.includes('docimg://')) return content;
  const match = content.match(REQUIREMENT_DOC_ID_RE);
  if (!match) return content;
  const documentId = match[1];
  return content.replace(/!\[(.*?)\]\(docimg:\/\/([^)]+)\)/g, (_m, alt, imageId) => {
    return `![${alt}](/api/requirements/documents/${documentId}/images/${imageId}/)`;
  });
};

// HTML转义函数
const escapeHtml = (text: string): string => {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
};

const getCodePreviewText = (preElement: HTMLElement, maxLines = 3, fromEnd = false): string => {
  const codeElement = preElement.querySelector('code');
  const rawCode = (codeElement?.textContent || preElement.textContent || '').replace(/\r\n/g, '\n');
  const lines = rawCode.split('\n');
  const previewLines = fromEnd ? lines.slice(-maxLines) : lines.slice(0, maxLines);
  const preview = previewLines.join('\n').trimEnd();
  return preview || '// ...';
};

const detectCodeLanguage = (preElement: HTMLElement): string => {
  const codeElement = preElement.querySelector('code');
  if (!codeElement?.className) return '';
  const match = codeElement.className.match(CODE_LANG_CLASS_RE);
  return match?.[1] || '';
};

const wrapCodeBlocksAsCollapsible = (html: string, isStreaming = false): string => {
  if (!html || !html.includes('<pre')) return html;

  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div id="__code_root__">${html}</div>`, 'text/html');
  const root = doc.getElementById('__code_root__');
  if (!root) return html;

  const preElements = root.querySelectorAll('pre');
  preElements.forEach((preNode) => {
    if (!(preNode instanceof HTMLElement)) return;
    if (preNode.closest('details.message-code-collapse')) return;

    const details = doc.createElement('details');
    details.className = isStreaming ? 'message-code-collapse is-streaming' : 'message-code-collapse';

    const summary = doc.createElement('summary');
    summary.className = 'message-code-toggle';

    const language = detectCodeLanguage(preNode);
    const header = doc.createElement('span');
    header.className = 'message-code-toggle-header';
    header.textContent = language ? `代码块 (${language})` : '代码块';
    summary.appendChild(header);

    if (isStreaming) {
      const previewViewport = doc.createElement('span');
      previewViewport.className = 'message-code-preview-viewport';

      const preview = doc.createElement('code');
      preview.className = 'message-code-preview message-code-preview-stream';
      preview.textContent = getCodePreviewText(preNode, 12, true);

      previewViewport.appendChild(preview);
      summary.appendChild(previewViewport);
    } else {
      const preview = doc.createElement('code');
      preview.className = 'message-code-preview';
      preview.textContent = getCodePreviewText(preNode, 3);
      summary.appendChild(preview);
    }

    const parent = preNode.parentNode;
    if (!parent) return;

    parent.insertBefore(details, preNode);
    details.appendChild(summary);
    details.appendChild(preNode);
  });

  return root.innerHTML;
};

// 格式化消息内容
const formattedContent = computed(() => {
  try {
    let processedContent = props.message.content;

    // 用户消息（human类型）：先转义HTML，确保用户发送的HTML代码能正确显示
    if (props.message.isUser || props.message.messageType === 'human') {
      // 转义HTML标签，使其显示为文本
      processedContent = escapeHtml(processedContent);
      // 将换行符转换为<br>标签，保持换行
      processedContent = processedContent.replace(/\n/g, '<br>');
      return processedContent;
    }

    // 将需求文档图片占位符转换为可访问的图片URL（用于Markdown渲染）
    processedContent = replaceDocImgPlaceholders(processedContent);

    // 如果是工具消息，尝试格式化JSON
    if (props.message.messageType === 'tool') {
      processedContent = formatToolMessage(processedContent);
    }

    // 对于AI消息，处理Markdown渲染
    if (props.message.messageType === 'ai') {
      // 如果是流式输出或者已完成的AI消息，都需要处理代码块
      if (props.message.isStreaming || !props.message.isLoading) {
        processedContent = handleStreamingMarkdown(processedContent);
      }
    }

    // 使用marked解析Markdown (同步版本)
    let htmlContent = marked(processedContent) as string;
    if (shouldWrapCodeBlocks.value) {
      htmlContent = wrapCodeBlocksAsCollapsible(htmlContent, Boolean(props.message.isStreaming));
    }

    // 使用DOMPurify净化HTML防止XSS攻击
    return DOMPurify.sanitize(htmlContent, {
      ADD_TAGS: ['img', 'details', 'summary'],
      ADD_ATTR: ['src', 'alt', 'title', 'class'],
    });
  } catch (error) {
    console.error('Error parsing markdown:', error);
    return props.message.content;
  }
});

const scrollStreamingCodePreviewToBottom = () => {
  if (!props.message.isStreaming || !messageBubbleRef.value) return;

  const viewports = messageBubbleRef.value.querySelectorAll('.message-code-preview-viewport');
  viewports.forEach((node) => {
    if (!(node instanceof HTMLElement)) return;
    node.scrollTop = node.scrollHeight;
  });
};

const scheduleStreamingPreviewScroll = () => {
  if (previewScrollRafId !== null) {
    cancelAnimationFrame(previewScrollRafId);
  }
  previewScrollRafId = requestAnimationFrame(() => {
    scrollStreamingCodePreviewToBottom();
    previewScrollRafId = null;
  });
};

onUpdated(() => {
  if (!props.message.isStreaming) return;
  nextTick(() => {
    scheduleStreamingPreviewScroll();
  });
});

onUnmounted(() => {
  if (previewScrollRafId !== null) {
    cancelAnimationFrame(previewScrollRafId);
    previewScrollRafId = null;
  }
});



// 处理流式输出中的Markdown，确保代码块正确渲染
const handleStreamingMarkdown = (content: string) => {
  // 首先处理转义字符，将\\n转换为真正的换行符
  let processedContent = content
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\r/g, '\r');

  // 计算```的出现次数（使用处理过的内容）
  const codeBlockMarkers = (processedContent.match(/```/g) || []).length;

  // 如果```出现偶数次，说明代码块是完整的（每个开始都有对应的结束）
  if (codeBlockMarkers > 0 && codeBlockMarkers % 2 === 0) {
    return processedContent;
  }

  // 如果```出现奇数次，说明有未闭合的代码块
  if (codeBlockMarkers % 2 === 1) {
    // 匹配最后一个```开始的代码块，支持语言标识
    const lastCodeBlockRegex = /```(\w*)\n?([\s\S]*)$/;
    const match = processedContent.match(lastCodeBlockRegex);

    if (match) {
      const language = match[1] || '';
      const codeContent = match[2] || '';

      // 对于流式输出，确保代码块格式正确
      const beforeCodeBlock = processedContent.substring(0, match.index);

      // 确保代码块前有空行
      let processedBefore = beforeCodeBlock;
      if (!processedBefore.endsWith('\n\n')) {
        if (processedBefore.endsWith('\n')) {
          processedBefore += '\n';
        } else {
          processedBefore += '\n\n';
        }
      }

      // 构建完整的代码块，确保格式正确
      return `${processedBefore}\`\`\`${language}\n${codeContent}\n\`\`\`\n`;
    }

    // 检查是否有单独的```开头但没有内容
    if (processedContent.endsWith('```') || processedContent.match(/```\w*\s*$/)) {
      return processedContent + '\n\n```';
    }

    // 检查是否有```语言标识但没有换行的情况
    const codeStartMatch = processedContent.match(/```(\w+)$/);
    if (codeStartMatch) {
      return processedContent + '\n\n```';
    }
  }

  return processedContent;
};

// 检查代码内容是否看起来完整（根据txt文件中的实际代码格式优化）


// 格式化工具消息
const formatToolMessage = (content: string) => {
  const parsedPayload = parseToolResultDisplayPayload(content);
  if (parsedPayload.fileAttachments.length > 0 || parsedPayload.imageDataUrl) {
    if (parsedPayload.content && parsedPayload.content.trim()) {
      return parsedPayload.content;
    }
    if (parsedPayload.fileAttachments.length > 0) {
      return `已生成 ${parsedPayload.fileAttachments.length} 个文件，可直接下载。`;
    }
  }

  try {
    // 先尝试解析为 JSON
    let jsonData = JSON.parse(content);
    
    // 处理 MCP 工具返回的数组格式: [{"type": "text", "text": "..."}]
    if (Array.isArray(jsonData) && jsonData.length > 0 && jsonData[0]?.type === 'text' && jsonData[0]?.text) {
      // 提取 text 字段的内容
      const textContent = jsonData[0].text;
      try {
        // 尝试解析 text 内容为 JSON
        const innerJson = JSON.parse(textContent);
        // 如果是数组，格式化为列表
        if (Array.isArray(innerJson)) {
          return innerJson.map((item: any) => `• ${item}`).join('\n');
        }
        // 对象格式化为 JSON 代码块
        const formattedJson = JSON.stringify(innerJson, null, 2);
        return `\`\`\`json\n${formattedJson}\n\`\`\``;
      } catch {
        // text 内容不是 JSON，直接显示
        return textContent;
      }
    }
    
    // 如果是简单数组，格式化为列表
    if (Array.isArray(jsonData) && jsonData.length > 0 && typeof jsonData[0] !== 'object') {
      return jsonData.map((item: any) => `• ${item}`).join('\n');
    }
    
    // 其他 JSON 格式化为代码块
    const formattedJson = JSON.stringify(jsonData, null, 2);
    return `\`\`\`json\n${formattedJson}\n\`\`\``;
  } catch {
    // 尝试修复 Python 格式的字符串（单引号转双引号）
    try {
      const fixedContent = content.replace(/'/g, '"');
      const jsonData = JSON.parse(fixedContent);
      
      // 处理 MCP 格式
      if (Array.isArray(jsonData) && jsonData.length > 0 && jsonData[0]?.type === 'text' && jsonData[0]?.text) {
        const textContent = jsonData[0].text;
        try {
          const innerJson = JSON.parse(textContent);
          if (Array.isArray(innerJson)) {
            return innerJson.map((item: any) => `• ${item}`).join('\n');
          }
          const formattedJson = JSON.stringify(innerJson, null, 2);
          return `\`\`\`json\n${formattedJson}\n\`\`\``;
        } catch {
          return textContent;
        }
      }
      
      if (Array.isArray(jsonData) && jsonData.length > 0 && typeof jsonData[0] !== 'object') {
        return jsonData.map((item: any) => `• ${item}`).join('\n');
      }
      
      const formattedJson = JSON.stringify(jsonData, null, 2);
      return `\`\`\`json\n${formattedJson}\n\`\`\``;
    } catch {
      // 如果不是 JSON,检查是否已经包含代码块标记
      if (content.includes('```')) {
        return content;
      }
      
      // 检测是否为纯数字或简单文本(少于 50 字符且无换行)
      const trimmedContent = content.trim();
      if (trimmedContent.length < 50 && !trimmedContent.includes('\n')) {
        // 简单文本直接显示,无需代码块
        return trimmedContent;
      }
      
      // 包含 Markdown 图片语法时，直接返回让 marked 渲染
      if (/!\[.*?\]\(.*?\)/.test(trimmedContent)) {
        return trimmedContent;
      }

      // 其他情况包装为代码块
      return `\`\`\`\n${content}\n\`\`\``;
    }
  }
};
</script>

<style scoped>
.message-wrapper {
  display: flex;
  gap: 12px;
  max-width: 85%;
}

.user-message {
  flex-direction: row-reverse;
  align-self: flex-end;
}

.ai-message {
  align-self: flex-start;
}

.tool-message {
  align-self: flex-start;
}

/* Step Separator 样式 - 步骤分隔符 */
.step-separator-message {
  max-width: 100%;
  align-self: center;
  margin: 20px 0;
}

.step-separator {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.step-separator-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(to right, transparent, #e5e6eb 20%, #e5e6eb 80%, transparent);
}

.step-separator-label {
  font-size: 13px;
  font-weight: 600;
  color: #165dff;
  background: linear-gradient(135deg, #e8f3ff 0%, #f2f5ff 100%);
  padding: 6px 16px;
  border-radius: 20px;
  border: 1px solid #d4e6ff;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(22, 93, 255, 0.08);
}

/* Agent Step 消息样式 - 紧凑的进度指示器 */
.agent-step-message {
  max-width: 100%;
  align-self: center;
}

.agent-step-indicator {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 12px;
  background-color: #f2f3f5;
  color: #86909c;
  transition: all 0.2s ease;
}

.agent-step-indicator.is-start {
  background-color: #e8f3ff;
  color: #165dff;
}

.agent-step-indicator.is-complete {
  background-color: #e8ffea;
  color: #00b42a;
}

.agent-step-indicator.is-error {
  background-color: #ffece8;
  color: #f53f3f;
}

.agent-step-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
}

.agent-step-icon svg {
  width: 16px;
  height: 16px;
}

.agent-step-icon .spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.agent-step-label {
  font-weight: 500;
}

.agent-step-summary {
  color: #4e5969;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-step-time {
  color: #c9cdd4;
  font-size: 11px;
}

.avatar {
  width: 35px;
  height: 35px;
  flex-shrink: 0;
}

.avatar-img {
  width: 35px;
  height: 35px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: white;
  object-fit: cover; /* 确保图片能被正确裁剪和缩放 */
}

.user-avatar {
  background-color: #165dff;
}

.ai-avatar {
  /* 当使用img标签时，这个类主要用于定位，背景色可以去掉 */
  background-color: transparent;
}

.tool-avatar {
  background-color: #ff7d00;
}

.tool-avatar-icon {
  font-size: 18px;
}



.message-content {
  display: flex;
  flex-direction: column;
  min-width: 0; /* 允许flex子项收缩 */
  flex: 1; /* 占用剩余空间 */
}

/* 图片容器样式 */
.message-image-container {
  margin-bottom: 8px;
  max-width: 100%;
  width: fit-content;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: center;
  position: relative;
}

.message-image-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  max-width: min(100%, 360px);
  width: min(100%, 360px);
  box-shadow: none;
  overflow: visible;
  background: transparent;
}

.float-action-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}
.message-image-container:hover .float-action-btn {
  opacity: 1;
}

/* 悬浮预览中的占位 */
.tool-image-float-placeholder {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  margin-bottom: 8px;
  border: 1px dashed #c9cdd4;
  border-radius: 8px;
  cursor: pointer;
  background: #f7f8fa;
  transition: background 0.2s;
}
.tool-image-float-placeholder:hover {
  background: #e8f3ff;
}
.float-placeholder-thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 4px;
}
.float-placeholder-label {
  font-size: 12px;
  color: #86909c;
}

.message-image {
  width: auto;
  height: auto;
  max-width: min(100%, 300px);
  display: block;
  cursor: pointer;
  transition: transform 0.2s ease;
  object-fit: contain;
}

.message-image-multi {
  width: 100%;
  max-width: none;
  aspect-ratio: 1 / 1;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  object-fit: cover;
}

.message-image:hover {
  transform: scale(1.02);
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  max-width: 100%;
  word-break: break-word;
  text-align: left;
  transition: all 0.2s ease;
}

/* 加载指示器样式 */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #c9cdd4;
  animation: typing-bounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: -0.16s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0s;
}

@keyframes typing-bounce {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.user-message .message-bubble {
  background-color: #165dff;
  color: white;
  border-top-right-radius: 2px;
}

.ai-message .message-bubble {
  background-color: white;
  color: #1d2129;
  border-top-left-radius: 2px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.tool-message .message-bubble {
  background-color: #fff7e6;
  color: #1d2129;
  border-top-left-radius: 2px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  /* 增强工具消息的文本换行 */
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-all;
  white-space: pre-wrap;
}



/* 工具消息折叠展开样式 */
.tool-message-content {
  position: relative;
}

.tool-header {
  font-size: 0.9em;
  font-weight: 600;
  color: var(--theme-text-secondary);
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(var(--theme-accent-rgb), 0.16);
}

.tool-content {
  transition: all 0.3s ease;
  /* 确保工具内容能够正确换行 */
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-all;
  max-width: 100%;
  overflow-x: hidden; /* 防止水平溢出 */
}

.tool-content.collapsed {
  max-height: 120px;
  overflow: hidden;
  position: relative;
}

.tool-content.collapsed::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40px;
  background: linear-gradient(transparent, color-mix(in srgb, var(--theme-surface) 78%, white 22%));
  pointer-events: none;
}

.tool-file-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  background: #f7f8fa;
}

.tool-file-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-file-name {
  font-size: 13px;
  font-weight: 600;
  color: #1d2129;
  word-break: break-all;
}

.tool-file-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #86909c;
  flex-wrap: wrap;
}

.tool-file-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.tool-file-link {
  font-size: 12px;
  color: #165dff;
  text-decoration: none;
}

.tool-file-link:hover {
  text-decoration: underline;
}



.expand-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 8px;
  padding: 4px 8px;
  background-color: rgba(255, 125, 0, 0.1);
  border: 1px solid rgba(255, 125, 0, 0.3);
  border-radius: 4px;
  color: #ff7d00;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.expand-button:hover {
  background-color: rgba(255, 125, 0, 0.2);
  border-color: rgba(255, 125, 0, 0.5);
}



.expand-button i {
  font-size: 10px;
}

.icon-up::before {
  content: '▲';
}

.icon-down::before {
  content: '▼';
}

.diagram-preview-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.diagram-preview-btn {
  border-radius: 6px !important;
}

/* 消息操作按钮 */
.message-actions {
  display: flex;
  gap: 2px;
  margin-top: 6px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.message-wrapper:hover .message-actions {
  opacity: 1;
}

.action-btn {
  padding: 4px 6px !important;
  height: 24px !important;
  min-width: 24px !important;
  border-radius: 4px !important;
  color: #86909c !important;
  transition: all 0.2s ease !important;
}

.action-btn:hover {
  background-color: #f2f3f5 !important;
  color: #165dff !important;
}

.action-btn-danger:hover {
  background-color: #ffece8 !important;
  color: #f53f3f !important;
}

.user-message .action-btn:hover {
  background-color: rgba(255, 255, 255, 0.2) !important;
  color: white !important;
}

.user-message .action-btn-danger:hover {
  background-color: rgba(245, 63, 63, 0.3) !important;
  color: white !important;
}

.message-time {
  font-size: 12px;
  color: #86909c;
  margin-top: 4px;
  text-align: center;
}

/* 打字指示器动画 */
.typing-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 0;
}

.typing-indicator span {
  height: 8px;
  width: 8px;
  background-color: #c9cdd4;
  border-radius: 50%;
  display: inline-block;
  margin: 0 2px;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(1) {
  animation-delay: 0s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
  100% {
    transform: translateY(0);
  }
}

/* 流式内容样式 */
.streaming-content {
  position: relative;
  border-left: 3px solid #00b42a;
  background: linear-gradient(90deg, rgba(0, 180, 42, 0.05) 0%, transparent 20%);
  padding-left: 8px;
}

.streaming-content::after {
  content: '';
  display: inline-block;
  width: 2px;
  height: 1.2em;
  background-color: #00b42a;
  margin-left: 2px;
  animation: blink 1s infinite;
  vertical-align: text-bottom;
}

/* 流式输出中的代码块特殊样式 */
.streaming-content :deep(pre) {
  background-color: #f2f3f5;
  border: 1px solid rgba(0, 180, 42, 0.2);
  border-left: 3px solid #00b42a;
}

.streaming-content :deep(code) {
  background-color: rgba(0, 180, 42, 0.1);
  color: #1d2129;
}

@keyframes blink {
  0%, 50% {
    opacity: 1;
  }
  51%, 100% {
    opacity: 0;
  }
}

/* 支持Markdown内容的样式 */
.message-bubble :deep(a) {
  color: inherit;
  text-decoration: underline;
}

.message-bubble :deep(pre) {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 8px 0;
}

.message-bubble :deep(details.message-code-collapse) {
  margin: 8px 0;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background-color: rgba(0, 0, 0, 0.02);
}

.message-bubble :deep(details.message-code-collapse > summary.message-code-toggle) {
  list-style: none;
  cursor: pointer;
  user-select: none;
  position: relative;
  padding: 8px 58px 10px 10px;
  font-size: 12px;
  color: #4e5969;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.message-bubble :deep(details.message-code-collapse > summary.message-code-toggle::-webkit-details-marker) {
  display: none;
}

.message-bubble :deep(details.message-code-collapse > summary.message-code-toggle::before) {
  content: '▶';
  position: absolute;
  top: 11px;
  left: 10px;
  font-size: 10px;
  color: #86909c;
}

.message-bubble :deep(details.message-code-collapse > summary.message-code-toggle::after) {
  content: '展开';
  position: absolute;
  top: 8px;
  right: 10px;
  font-size: 12px;
  color: #86909c;
}

.message-bubble :deep(.message-code-toggle-header) {
  font-weight: 600;
  padding-left: 16px;
  line-height: 1.4;
}

.message-bubble :deep(.message-code-preview) {
  display: block;
  margin-left: 16px;
  padding: 6px 8px;
  border-radius: 6px;
  background-color: rgba(0, 0, 0, 0.05);
  white-space: pre;
  line-height: 1.4;
  max-height: calc(1.4em * 3 + 12px);
  overflow: hidden;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  color: #4e5969;
}

.message-bubble :deep(.message-code-preview-viewport) {
  display: block;
  margin-left: 16px;
  border-radius: 6px;
  background-color: rgba(0, 0, 0, 0.05);
  max-height: calc(1.4em * 3 + 12px);
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.message-bubble :deep(.message-code-preview-viewport::-webkit-scrollbar) {
  display: none;
}

.message-bubble :deep(.message-code-preview-stream) {
  margin: 0;
  border-radius: 0;
  background-color: transparent;
  min-height: auto;
}

.message-bubble :deep(details.message-code-collapse[open] > summary.message-code-toggle) {
  border-bottom: 1px solid #e5e6eb;
}

.message-bubble :deep(details.message-code-collapse[open] > summary.message-code-toggle::before) {
  content: '▼';
}

.message-bubble :deep(details.message-code-collapse[open] > summary.message-code-toggle::after) {
  content: '收起';
}

.message-bubble :deep(details.message-code-collapse[open] > summary .message-code-preview) {
  display: none;
}

.message-bubble :deep(details.message-code-collapse[open] > summary .message-code-preview-viewport) {
  display: none;
}

.message-bubble :deep(details.message-code-collapse > pre) {
  margin: 0;
  border-radius: 0 0 8px 8px;
  border: none;
}

.message-bubble :deep(details.message-code-collapse.is-streaming[open] > pre) {
  position: relative;
  overflow: hidden;
}

.message-bubble :deep(details.message-code-collapse.is-streaming[open] > pre::after) {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: -100%;
  height: 100%;
  background: linear-gradient(to bottom, rgba(22, 93, 255, 0), rgba(22, 93, 255, 0.12), rgba(22, 93, 255, 0));
  animation: code-streaming-sweep 1.8s linear infinite;
  pointer-events: none;
}

@keyframes code-streaming-sweep {
  0% { transform: translateY(0); }
  100% { transform: translateY(200%); }
}

.ai-message .message-bubble :deep(pre) {
  background-color: #f2f3f5;
}

.user-message .message-bubble :deep(pre) {
  background-color: rgba(255, 255, 255, 0.2);
}

.tool-message .message-bubble :deep(pre) {
  background-color: rgba(255, 125, 0, 0.1);
  /* 工具消息代码块强制换行，防止溢出 */
  word-break: break-all;
  overflow-wrap: break-word;
  white-space: pre-wrap;
  overflow-x: hidden; /* 禁用水平滚动 */
  max-width: 100%; /* 确保不超出容器 */
}



.message-bubble :deep(code) {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  background-color: rgba(0, 0, 0, 0.1);
  padding: 2px 4px;
  border-radius: 3px;
  font-size: 0.9em;
}

.message-bubble :deep(pre code) {
  background-color: transparent;
  padding: 0;
  border-radius: 0;
}

.message-bubble :deep(p) {
  margin: 8px 0;
  line-height: 1.6;
}

.message-bubble :deep(p:first-child) {
  margin-top: 0;
}

.message-bubble :deep(p:last-child) {
  margin-bottom: 0;
}

.message-bubble :deep(ul), .message-bubble :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
  line-height: 1.6;
}

.message-bubble :deep(li) {
  margin: 4px 0;
}

.message-bubble :deep(h1), .message-bubble :deep(h2), .message-bubble :deep(h3),
.message-bubble :deep(h4), .message-bubble :deep(h5), .message-bubble :deep(h6) {
  margin: 12px 0 8px 0;
  font-weight: bold;
}

.message-bubble :deep(h1) { font-size: 1.5em; }
.message-bubble :deep(h2) { font-size: 1.3em; }
.message-bubble :deep(h3) { font-size: 1.1em; }

.message-bubble :deep(blockquote) {
  border-left: 3px solid var(--theme-border);
  margin: 8px 0;
  padding-left: 12px;
  color: var(--theme-text-secondary);
}

.message-bubble :deep(img) {
  max-width: min(100%, 400px);
  height: auto;
  border-radius: 4px;
}

/* 用户消息中的引用样式 - 适配蓝色背景 */
.user-message .message-bubble :deep(blockquote) {
  border-left-color: rgba(255, 255, 255, 0.5);
  color: rgba(255, 255, 255, 0.85);
  background-color: rgba(255, 255, 255, 0.1);
  padding: 8px 12px;
  border-radius: 0 6px 6px 0;
  margin-bottom: 12px;
}

.message-bubble :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}

.message-bubble :deep(th), .message-bubble :deep(td) {
  border: 1px solid #ddd;
  padding: 6px 8px;
  text-align: left;
}

.message-bubble :deep(th) {
  background-color: rgba(0, 0, 0, 0.05);
  font-weight: bold;
}

/* 工具消息特殊内容处理 */
.tool-message .message-bubble :deep(p) {
  /* 确保段落内容能够正确换行 */
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-all;
}

.tool-message .message-bubble :deep(code) {
  /* 内联代码保持适当的换行 */
  word-break: break-all;
  white-space: pre-wrap;
}

.tool-message .message-bubble :deep(pre code) {
  /* 工具消息代码块内的代码也要强制换行 */
  word-break: break-all;
  white-space: pre-wrap;
  overflow-wrap: break-word;
}

/* 🎨 思考过程样式 */
.thinking-process-content {
  width: 100%;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background-color: #f7f8fa;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s ease;
  user-select: none;
}

/* 响应式图片尺寸调整 */
@media (max-width: 768px) {
  .message-image {
    max-width: min(100%, 320px);
  }

  .message-image-grid {
    max-width: min(100%, 300px);
    width: min(100%, 300px);
  }
}

@media (max-width: 480px) {
  .message-image {
    max-width: min(100%, 240px);
  }

  .message-image-grid {
    grid-template-columns: 1fr 1fr;
    max-width: min(100%, 240px);
    width: min(100%, 240px);
  }
}

/* 确保消息气泡内的图片不会超出容器 */
.message-bubble :deep(img) {
  max-width: min(100%, 400px);
  height: auto;
  display: block;
  margin: 8px 0;
}

/* 用户消息中的图片样式 */
.user-message .message-image-container {
  display: flex;
  justify-content: flex-end; /* 用户消息的图片靠右对齐 */
}

.user-message .message-image-container.message-image-grid {
  margin-left: auto;
}

.user-message .message-image {
  max-width: min(100%, 400px);
}

/* AI消息中的图片样式 */
.ai-message .message-image-container {
  display: flex;
  justify-content: flex-start; /* AI消息的图片靠左对齐 */
}

.ai-message .message-image-container.message-image-grid {
  margin-right: auto;
}

.thinking-header:hover {
  background-color: #ebeef5;
}

.thinking-label {
  font-weight: 500;
  color: #4e5969;
  flex: 1;
}

.thinking-body {
  margin-top: 8px;
  padding: 12px;
  background-color: #f9fafb;
  border-radius: 8px;
  border-left: 3px solid #165dff;
}
</style>
