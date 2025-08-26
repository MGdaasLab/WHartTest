<template>
  <div :class="['message-wrapper', messageClass]">
    <div class="avatar">
      <div class="avatar-img" :class="avatarClass">
        {{ avatarText }}
      </div>
    </div>
    <div class="message-content">
      <div class="message-bubble">
        <div v-if="message.isLoading" class="typing-indicator">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div v-else-if="message.messageType === 'tool'" class="tool-message-content">
          <div
            :class="['tool-content', { 'collapsed': !message.isExpanded && shouldCollapse }]"
            :key="message.content"
            v-html="formattedContent"
          ></div>
          <div
            v-if="shouldCollapse"
            class="expand-button"
            @click="$emit('toggle-expand', message)"
          >
            {{ message.isExpanded ? '收起' : '展开' }}
            <i :class="message.isExpanded ? 'icon-up' : 'icon-down'"></i>
          </div>
        </div>

        <div
          v-else
          :key="message.content"
          :class="{ 'streaming-content': isStreamingMessage }"
          v-html="formattedContent"
        ></div>
      </div>
      <div class="message-time">{{ message.time }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import DOMPurify from 'dompurify';
import { marked } from 'marked';

// 配置marked以确保代码块正确渲染
marked.setOptions({
  breaks: true,
  gfm: true,
  highlight: null, // 不使用代码高亮，保持简单
  langPrefix: 'language-', // 为代码块添加语言前缀
  pedantic: false,
  sanitize: false, // 我们使用DOMPurify来净化
  smartLists: true,
  smartypants: false,
  xhtml: false
});

interface ChatMessage {
  content: string;
  isUser: boolean;
  time: string;
  isLoading?: boolean;
  messageType?: 'human' | 'ai' | 'tool' | 'system'; // 🆕 添加 system 类型
  isExpanded?: boolean;
  isStreaming?: boolean; // 新增：标识是否正在流式输出
}

interface Props {
  message: ChatMessage;
}

const props = defineProps<Props>();

defineEmits<{
  'toggle-expand': [message: ChatMessage];
}>();

// 消息样式类
const messageClass = computed(() => {
  if (props.message.isUser) return 'user-message';
  if (props.message.messageType === 'tool') return 'tool-message';
  return 'ai-message';
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
  if (props.message.messageType === 'tool') return '工具';
  return 'LLM';
});

// 判断是否为正在流式更新的消息
const isStreamingMessage = computed(() => {
  return props.message.messageType === 'ai' &&
         !props.message.isLoading &&
         props.message.isStreaming === true &&
         props.message.content.length > 0;
});

// 判断工具消息是否需要折叠
const shouldCollapse = computed(() => {
  if (props.message.messageType !== 'tool') return false;
  const lines = props.message.content.split('\n').length;
  return lines > 4;
});



// 格式化消息内容
const formattedContent = computed(() => {
  try {
    let processedContent = props.message.content;

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
    const htmlContent = marked(processedContent) as string;

    // 调试信息：查看Markdown解析结果
    if (props.message.messageType === 'ai' && processedContent.includes('```')) {
      console.log('📋 [Markdown解析] 代码块渲染调试:', {
        originalContent: processedContent.substring(0, 200) + '...',
        htmlOutput: htmlContent.substring(0, 300) + '...',
        hasPreTags: htmlContent.includes('<pre>'),
        hasCodeTags: htmlContent.includes('<code>'),
        isStreaming: props.message.isStreaming,
        isLoading: props.message.isLoading
      });
    }

    // 使用DOMPurify净化HTML防止XSS攻击
    const sanitizedContent = DOMPurify.sanitize(htmlContent);

    // 最终调试信息
    if (props.message.messageType === 'ai' && processedContent.includes('```')) {
      console.log('🎨 [最终渲染] 净化后的HTML:', {
        sanitizedContent: sanitizedContent.substring(0, 300) + '...',
        hasPreTags: sanitizedContent.includes('<pre>'),
        hasCodeTags: sanitizedContent.includes('<code>')
      });
    }

    return sanitizedContent;
  } catch (error) {
    console.error('Error parsing markdown:', error);
    return props.message.content;
  }
});



// 处理流式输出中的Markdown，确保代码块正确渲染
const handleStreamingMarkdown = (content: string) => {
  // 首先处理转义字符，将\\n转换为真正的换行符
  let processedContent = content
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\r/g, '\r');

  console.log('🔍 [流式Markdown] 处理代码块渲染:', {
    originalContent: content.substring(0, 100) + '...',
    processedContent: processedContent.substring(0, 100) + '...',
    hasCodeBlocks: processedContent.includes('```'),
    codeBlockCount: (processedContent.match(/```/g) || []).length,
    contentLength: processedContent.length,
    hasEscapedNewlines: content.includes('\\n')
  });

  // 计算```的出现次数（使用处理过的内容）
  const codeBlockMarkers = (processedContent.match(/```/g) || []).length;

  // 如果```出现偶数次，说明代码块是完整的（每个开始都有对应的结束）
  if (codeBlockMarkers > 0 && codeBlockMarkers % 2 === 0) {
    console.log('✅ [代码块完整] 直接返回处理后的内容');
    return processedContent;
  }

  // 如果```出现奇数次，说明有未闭合的代码块
  if (codeBlockMarkers % 2 === 1) {
    // 根据txt文件的实际情况，匹配代码块模式
    // 匹配最后一个```开始的代码块，支持语言标识
    const lastCodeBlockRegex = /```(\w*)\n?([\s\S]*)$/;
    const match = processedContent.match(lastCodeBlockRegex);

    if (match) {
      const language = match[1] || '';
      const codeContent = match[2] || '';

      console.log('🔧 [代码块修复] 发现不完整代码块:', {
        language: language || '无语言标识',
        codeContent: codeContent.substring(0, 50) + '...',
        codeLength: codeContent.length,
        needsClosing: true
      });

      // 对于流式输出，确保代码块格式正确
      // 关键：确保代码块前后都有空行，这样marked.js才能正确识别
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
      const result = `${processedBefore}\`\`\`${language}\n${codeContent}\n\`\`\`\n`;

      console.log('🔨 [代码块修复] 添加临时结尾标记:', {
        beforeLength: beforeCodeBlock.length,
        afterLength: result.length,
        addedClosing: true,
        hasProperSpacing: true,
        usedProcessedContent: true
      });

      return result;
    }

    // 检查是否有单独的```开头但没有内容（如txt文件中的情况）
    if (processedContent.endsWith('```') || processedContent.match(/```\w*\s*$/)) {
      console.log('🔧 [代码块修复] 添加空代码块结尾');
      return processedContent + '\n\n```';
    }

    // 检查是否有```语言标识但没有换行的情况
    const codeStartMatch = processedContent.match(/```(\w+)$/);
    if (codeStartMatch) {
      console.log('🔧 [代码块修复] 添加换行和结尾:', codeStartMatch[1]);
      return processedContent + '\n\n```';
    }
  }

  console.log('ℹ️ [无需处理] 直接返回处理后的内容');
  return processedContent;
};

// 检查代码内容是否看起来完整（根据txt文件中的实际代码格式优化）
const isCodeContentComplete = (codeContent: string, language: string): boolean => {
  const trimmedContent = codeContent.trim();

  // 如果内容为空，肯定不完整
  if (!trimmedContent) {
    return false;
  }

  // 对于Python代码（txt文件中的主要格式）
  if (language === 'python' || language === 'py') {
    // 检查是否有完整的函数定义
    if (trimmedContent.includes('def ')) {
      // 检查函数是否有完整的结构：def name(): 和缩进的内容
      const lines = trimmedContent.split('\n');
      let hasDefLine = false;
      let hasIndentedContent = false;

      for (const line of lines) {
        if (line.trim().startsWith('def ') && line.includes(':')) {
          hasDefLine = true;
        }
        if (hasDefLine && line.startsWith('    ') && line.trim()) {
          hasIndentedContent = true;
        }
      }

      // 如果有函数定义和缩进内容，认为相对完整
      return hasDefLine && hasIndentedContent;
    }

    // 对于简单的Python代码，检查是否有基本的语法结构
    const lines = trimmedContent.split('\n');
    if (lines.length > 1) {
      // 检查最后一行是否看起来是完整的
      const lastLine = lines[lines.length - 1].trim();
      // 如果最后一行不是明显的不完整状态，认为可能完整
      return !lastLine.endsWith(',') && !lastLine.endsWith('\\') && lastLine.length > 0;
    }
  }

  // 对于JSON格式，检查是否有完整的结构
  if (language === 'json') {
    try {
      // 检查是否以{开头}结尾，或者以[开头]结尾
      if ((trimmedContent.startsWith('{') && trimmedContent.endsWith('}')) ||
          (trimmedContent.startsWith('[') && trimmedContent.endsWith(']'))) {
        JSON.parse(trimmedContent);
        return true;
      }
    } catch (e) {
      // JSON解析失败，可能不完整
      return false;
    }
  }

  // 对于其他语言，基于txt文件的实际情况进行判断
  // 如果内容有多行且不以明显的不完整标记结尾，认为可能完整
  const lines = trimmedContent.split('\n');
  if (lines.length > 2) {
    const lastLine = lines[lines.length - 1].trim();
    const incompleteEndings = [',', '+', '-', '*', '/', '=', '&&', '||', '\\'];
    const endsWithIncomplete = incompleteEndings.some(ending => lastLine.endsWith(ending));

    return !endsWithIncomplete && lastLine.length > 0;
  }

  // 默认情况下，对于流式输出，我们倾向于认为内容不完整，以确保正确的代码块渲染
  return false;
};

// 格式化工具消息
const formatToolMessage = (content: string) => {
  try {
    // 尝试解析JSON
    const jsonData = JSON.parse(content);
    // 如果解析成功，格式化为带代码块的JSON
    const formattedJson = JSON.stringify(jsonData, null, 2);
    return `\`\`\`json\n${formattedJson}\n\`\`\``;
  } catch (error) {
    // 如果不是有效的JSON，检查是否已经是代码块格式
    if (content.includes('```')) {
      return content;
    }
    // 否则包装为代码块
    return `\`\`\`\n${content}\n\`\`\``;
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



.avatar {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
}

.avatar-img {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: white;
}

.user-avatar {
  background-color: #165dff;
}

.ai-avatar {
  background-color: #00b42a;
}

.tool-avatar {
  background-color: #ff7d00;
}



.message-content {
  display: flex;
  flex-direction: column;
  min-width: 0; /* 允许flex子项收缩 */
  flex: 1; /* 占用剩余空间 */
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
  background: linear-gradient(transparent, #fff7e6);
  pointer-events: none;
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
  border-left: 3px solid #ddd;
  margin: 8px 0;
  padding-left: 12px;
  color: #666;
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
</style>
