<template>
  <div class="mindmap-wrapper">
    <!-- 工具栏 -->
    <div class="mindmap-toolbar">
      <div class="toolbar-left">
        <a-space>
          <a-button-group size="medium">
            <a-button @click="handleZoomIn" :disabled="loading">
              <template #icon><icon-zoom-in /></template>
              <span class="btn-text">放大</span>
            </a-button>
            <a-button @click="handleZoomOut" :disabled="loading">
              <template #icon><icon-zoom-out /></template>
              <span class="btn-text">缩小</span>
            </a-button>
            <a-button @click="handleFit" :disabled="loading">
              <template #icon><icon-refresh /></template>
              <span class="btn-text">自适应</span>
            </a-button>
          </a-button-group>

          <a-dropdown @select="handleThemeChange" trigger="click">
            <a-button type="outline" :disabled="loading">
              <template #icon><icon-skin /></template>
              主题: {{ activeThemeLabel }}
            </a-button>
            <template #content>
              <a-doption v-for="t in themeOptions" :key="t.value" :value="t.value">
                {{ t.label }}
              </a-doption>
            </template>
          </a-dropdown>

          <a-dropdown @select="handleExport" trigger="click">
            <a-button type="outline" :loading="exporting">
              <template #icon><icon-download /></template>
              导出为...
            </a-button>
            <template #content>
              <a-doption value="png">PNG 图片 (.png)</a-doption>
              <a-doption value="json">JSON 脑图数据 (.json)</a-doption>
            </template>
          </a-dropdown>
        </a-space>
      </div>

      <div class="toolbar-right">
        <div class="tip-text">
          <icon-info-circle-fill class="tip-icon" />
          <span><b>操作提示：</b>单击选中 | 双击重命名 | 叶子节点右侧 + 可直接新增 | 左键框选节点 | 右键拖动画布/右键点按打开菜单 | 拖动调整模块</span>
        </div>
      </div>
    </div>

    <!-- 脑图容器 -->
    <div class="mindmap-canvas-container">
      <div
        ref="mindMapContainerRef"
        class="mindmap-container"
        v-show="!loading && hasData"
      ></div>

      <!-- 加载中 -->
      <div v-if="loading" class="state-overlay">
        <a-spin :size="40" tip="脑图正在生成中..." />
      </div>

      <!-- 空白状态 -->
      <div v-else-if="!hasData" class="state-overlay">
        <a-empty description="请先选择项目后查看测试用例脑图" />
      </div>
    </div>



    <div
      v-if="contextMenuVisible"
      class="node-context-menu"
      :style="contextMenuStyle"
      @click.stop
    >
      <button
        type="button"
        class="context-menu-item"
        :disabled="!isModuleOrRootSelected"
        @click="handleContextMenuAction('create-submodule')"
      >
        新建子模块
      </button>
      <button
        type="button"
        class="context-menu-item"
        :disabled="selectedNodeType !== 'module'"
        @click="handleContextMenuAction('create-case')"
      >
        新建用例
      </button>
      <button
        type="button"
        class="context-menu-item"
        :disabled="!isCaseSelected || hasPreconditionSelected"
        @click="handleContextMenuAction('create-precondition')"
      >
        新建前置条件
      </button>
      <button
        type="button"
        class="context-menu-item"
        :disabled="!isCaseSelected"
        @click="handleContextMenuAction('create-step')"
      >
        新建步骤
      </button>
      <button
        type="button"
        class="context-menu-item"
        :disabled="!isCaseSelected || hasNotesSelected"
        @click="handleContextMenuAction('create-notes')"
      >
        新建备注
      </button>
      <button
        type="button"
        class="context-menu-item"
        :disabled="!isStepSelected"
        @click="handleContextMenuAction('create-expected')"
      >
        新建预期
      </button>
      <button
        v-if="contextMenuMode === 'default'"
        type="button"
        class="context-menu-item danger"
        :disabled="!isDeletableSelected"
        @click="handleContextMenuAction('delete')"
      >
        {{ selectedNodeType === 'expected' ? '清除预期' : (selectedNodeType === 'precondition' ? '删除前置条件' : (selectedNodeType === 'notes' ? '删除备注' : '删除节点')) }}
      </button>

      <!-- 复制与粘贴节点 -->
      <div v-if="contextMenuMode === 'default'" class="context-menu-divider"></div>
      <button
        v-if="contextMenuMode === 'default'"
        type="button"
        class="context-menu-item"
        :disabled="!selectedNode || selectedNodeType === 'root'"
        @click="handleContextMenuAction('copy-node')"
      >
        复制节点 (Copy)
      </button>
      <button
        v-if="contextMenuMode === 'default'"
        type="button"
        class="context-menu-item"
        :disabled="!clipboardNode || !selectedNode"
        @click="handleContextMenuAction('paste-node')"
      >
        粘贴节点 (Paste)
      </button>

      <!-- 优先级选择标签 (仅在选中用例时显示) -->
      <div v-if="isCaseSelected" class="context-menu-divider"></div>
      <div v-if="isCaseSelected" class="context-menu-priority-section">
        <div class="priority-title">设为优先级：</div>
        <div class="priority-options">
          <span
            v-for="lvl in ['P0', 'P1', 'P2', 'P3']"
            :key="lvl"
            class="priority-tag-btn"
            :class="[lvl.toLowerCase(), { active: currentSelectedCaseLevel === lvl }]"
            @click="handleSetPriority(lvl)"
          >
            {{ lvl }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, computed, nextTick } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import MindMap from 'simple-mind-map';
import Drag from 'simple-mind-map/src/plugins/Drag.js';
import Export from 'simple-mind-map/src/plugins/Export.js';
import KeyboardNavigation from 'simple-mind-map/src/plugins/KeyboardNavigation.js';
import Select from 'simple-mind-map/src/plugins/Select.js';
import 'simple-mind-map/dist/simpleMindMap.esm.css';
import { useThemeStore } from '@/store/themeStore';

import type { TestCaseModule } from '@/services/testcaseModuleService';
import type { TestCase } from '@/services/testcaseService';

// 注册插件
MindMap.usePlugin(Drag)
  .usePlugin(Export)
  .usePlugin(KeyboardNavigation)
  .usePlugin(Select);

// 脑图主题配色色值映射表，用于动态计算节点 customStyles
const themeColorMap: Record<string, {
  primary: string;
  secondary: string;
  text: string;
  caseFill: string;
  caseText: string;
  stepFill: string;
  stepBorder: string;
  stepText: string;
}> = {
  classic: { primary: '#165dff', secondary: '#e8f3ff', text: '#165dff', caseFill: '#ffffff', caseText: '#1d2129', stepFill: '#f2f3f5', stepBorder: '#e5e6eb', stepText: '#86909c' },
  freshGreen: { primary: '#00b42a', secondary: '#e8ffea', text: '#00b42a', caseFill: '#ffffff', caseText: '#1d2129', stepFill: '#f0faf1', stepBorder: '#d3f4d6', stepText: '#4e7a53' },
  morandi: { primary: '#8a9ba8', secondary: '#e1e8ed', text: '#5c7080', caseFill: '#ffffff', caseText: '#1d2129', stepFill: '#f5f8fa', stepBorder: '#d8e1e8', stepText: '#657b83' },
  blackGold: { primary: '#d4b26f', secondary: '#262626', text: '#d4b26f', caseFill: '#1f1f1f', caseText: '#e0d6c3', stepFill: '#1a1a1a', stepBorder: '#3d3525', stepText: '#8c826e' },
  dark: { primary: '#306cff', secondary: '#232733', text: '#a5c2ff', caseFill: '#181b22', caseText: '#e5e6eb', stepFill: '#12141a', stepBorder: '#2e3340', stepText: '#86909c' }
};

// 批量注册所有脑图自定义主题
const registerAllThemes = () => {
  const themesToRegister = {
    classic: {
      backgroundColor: '#f5f7fa',
      lineColor: '#165dff',
      second: { borderColor: '#165dff' }
    },
    freshGreen: {
      backgroundColor: '#f4f9f4',
      lineColor: '#00b42a',
      second: { borderColor: '#00b42a' }
    },
    morandi: {
      backgroundColor: '#f3f4f6',
      lineColor: '#8a9ba8',
      second: { borderColor: '#8a9ba8' }
    },
    blackGold: {
      backgroundColor: '#141414',
      lineColor: '#d4b26f',
      second: { borderColor: '#d4b26f' }
    },
    dark: {
      backgroundColor: '#1d2129',
      lineColor: '#3c4858',
      second: { borderColor: '#3c4858' }
    }
  };

  Object.entries(themesToRegister).forEach(([name, config]) => {
    try {
      (MindMap as any).defineTheme(name, config);
    } catch (e) {
      console.warn(`[TestCaseMindmap] Theme ${name} registration skipped or already exists:`, e);
    }
  });
};

registerAllThemes();

const props = defineProps<{
  currentProjectId: number | null;
  selectedModuleId: number | null;
  modules: TestCaseModule[];
  testCases: TestCase[];
  loading: boolean;
  projectName?: string;
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'view-case', id: number): void;
  (e: 'update-case-module', caseId: number, moduleId: number | null): void;
  (e: 'update-module-parent', moduleId: number, parentId: number | null): void;
  (e: 'rename-case', caseId: number, newName: string): void;
  (e: 'rename-module', moduleId: number, newName: string): void;
  (e: 'create-module', parentModuleId: number | null, name: string): void;
  (e: 'create-case', moduleId: number | null, name: string): void;
  (e: 'create-step', caseId: number, step: { description: string; expectedResult: string }): void;
  (e: 'update-step-desc', caseId: number, stepNumber: number, description: string): void;
  (e: 'update-step-expected', caseId: number, stepNumber: number, expectedResult: string): void;
  (e: 'delete-node', type: 'module' | 'case', rawId: number): void;
  (e: 'delete-step', caseId: number, stepNumber: number): void;
  (e: 'update-precondition', caseId: number, precondition: string): void;
  (e: 'update-notes', caseId: number, notes: string): void;
  (e: 'update-case-level', caseId: number, level: string): void;
  (e: 'copy-case', caseId: number, targetModuleId: number | null): void;
  (e: 'copy-module', moduleId: number, targetParentId: number | null): void;
  (e: 'copy-step', sourceCaseId: number, stepNumber: number, targetCaseId: number): void;
  (e: 'delete-nodes', items: { type: string; rawId: number; extraId?: number }[]): void;
}>();

const mindMapContainerRef = ref<HTMLDivElement | null>(null);
const mindMapInstance = ref<MindMap | null>(null);
const exporting = ref(false);
const isInitializing = ref(false);

const themeStore = useThemeStore();
const activeTheme = ref(themeStore.theme === 'black' ? 'dark' : 'classic');

const themeOptions = [
  { value: 'classic', label: '经典蓝 (Classic)' },
  { value: 'freshGreen', label: '清新绿 (Fresh Green)' },
  { value: 'morandi', label: '莫兰迪 (Morandi)' },
  { value: 'blackGold', label: '黑金色 (Black Gold)' },
  { value: 'dark', label: '暗黑风 (Dark)' }
];

const activeThemeLabel = computed(() => {
  const opt = themeOptions.find(o => o.value === activeTheme.value);
  return opt ? opt.label : activeTheme.value;
});

const hasData = computed(() => {
  return Boolean(props.currentProjectId);
});

// 节点编辑/创建/删除双向操作支持
const selectedNode = ref<any>(null);
const clipboardNode = ref<any>(null);
const pendingEditUid = ref<string | null>(null);
const contextMenuVisible = ref(false);
const contextMenuPosition = ref({ x: 0, y: 0 });
const contextMenuMode = ref<'default' | 'create-only'>('default');

const ignoreNextPropsUpdate = ref(false);
const isPasting = ref(false);
const lastCopiedCaseExpandMap = ref<Map<string, boolean> | null>(null);
const newCaseExpandStates = ref<Map<string, boolean>>(new Map());

const captureSourceExpandStates = (sourceCaseId: number) => {
  const currentExpands = getMindmapExpandStates();
  const statesToCopy = new Map<string, boolean>();

  // 1. Capture the case itself
  const caseUid = `case-${sourceCaseId}`;
  if (currentExpands[caseUid] !== undefined) {
    statesToCopy.set('case', currentExpands[caseUid]);
  } else {
    const sourceCase = props.testCases.find(c => c.id === sourceCaseId);
    const hasChildren = sourceCase ? (sourceCase.precondition?.trim() || sourceCase.notes?.trim() || (sourceCase.steps && sourceCase.steps.length > 0)) : false;
    statesToCopy.set('case', !hasChildren);
  }

  // 2. Capture its steps
  const sourceCase = props.testCases.find(c => c.id === sourceCaseId);
  if (sourceCase && Array.isArray(sourceCase.steps)) {
    sourceCase.steps.forEach(step => {
      const stepUid = `step-${sourceCaseId}-${step.step_number}`;
      if (currentExpands[stepUid] !== undefined) {
        statesToCopy.set(`step-${step.step_number}`, currentExpands[stepUid]);
      } else {
        statesToCopy.set(`step-${step.step_number}`, true);
      }
    });
  }

  return statesToCopy;
};

const updateSelectedNodeReference = () => {
  const renderer = (mindMapInstance.value as any)?.renderer;
  const rootNode = renderer?.renderTree;
  if (!rootNode || !selectedNode.value) return;

  const currentUid = getNodeUid(selectedNode.value);
  if (currentUid) {
    const targetNode = findNodeByUid(rootNode, currentUid);
    if (targetNode) {
      selectedNode.value = targetNode;
    } else {
      selectedNode.value = null;
    }
  }
};

const contextMenuStyle = computed(() => ({
  left: `${contextMenuPosition.value.x}px`,
  top: `${contextMenuPosition.value.y}px`
}));

const getNodePayload = (node: any) => {
  if (!node) return null;
  if (typeof node.getData === 'function') {
    return node.getData() || null;
  }
  return node.data?.data || node.data || null;
};

const getNodeUid = (node: any) => {
  return getNodePayload(node)?.uid || null;
};

const getDefaultNodeUid = () => {
  return props.selectedModuleId ? `module-${props.selectedModuleId}` : 'root';
};

const findNodeByUid = (node: any, uid: string): any => {
  if (!node) return null;

  if (getNodeUid(node) === uid) {
    return node;
  }

  const children = Array.isArray(node.children) ? node.children : [];
  for (const child of children) {
    const matchedNode = findNodeByUid(child, uid);
    if (matchedNode) {
      return matchedNode;
    }
  }

  return null;
};

const activateNode = (node: any) => {
  if (!node) return;

  if (typeof node.active === 'function') {
    node.active();
    return;
  }

  selectedNode.value = node;
};

const activateDefaultNode = (preferredUid?: string | null) => {
  const renderer = (mindMapInstance.value as any)?.renderer;
  const rootNode = renderer?.renderTree;
  if (!rootNode) return;

  const targetUid = preferredUid || getNodeUid(selectedNode.value) || getDefaultNodeUid();
  const targetNode = targetUid ? findNodeByUid(rootNode, targetUid) : null;
  const nextNode = targetNode || rootNode;

  selectedNode.value = nextNode;
  activateNode(nextNode);

  // 如果有刚刚创建好的节点，自动激活就地（inline）编辑模式，避免用户双击
  if (pendingEditUid.value && nextNode && getNodeUid(nextNode) === pendingEditUid.value) {
    const textEdit = renderer?.textEdit;
    if (textEdit && typeof textEdit.show === 'function') {
      setTimeout(() => {
        textEdit.show({ node: nextNode, isInserting: true });
        pendingEditUid.value = null; // 消费后重置
      }, 50); // 给 50ms 延迟，确保 SVG 渲染就绪
    }
  }
};

const scheduleActivateDefaultNode = (preferredUid?: string | null) => {
  nextTick(() => {
    setTimeout(() => {
      activateDefaultNode(preferredUid);
    }, 0);
  });
};

const getMindmapExpandStates = (): Record<string, boolean> => {
  const states: Record<string, boolean> = {};
  if (!mindMapInstance.value) return states;
  try {
    const rootNode = (mindMapInstance.value as any)?.renderer?.renderTree;
    const traverse = (node: any) => {
      const nodeData = getNodePayload(node);
      const uid = nodeData?.uid;
      if (uid && nodeData?.expand !== undefined) {
        states[uid] = nodeData.expand;
      }
      if (Array.isArray(node?.children)) {
        node.children.forEach(traverse);
      }
    };
    if (rootNode) {
      traverse(rootNode);
    }
  } catch (e) {
    console.warn('[TestCaseMindmap] Failed to extract expand states:', e);
  }
  return states;
};

const refreshMindmapData = (preferredUid?: string | null) => {
  if (!mindMapInstance.value) return;

  const expandStates = getMindmapExpandStates();
  const newData = buildMindmapTree(expandStates);

  // Smooth incremental data update
  mindMapInstance.value.updateData(newData);

  if (preferredUid) {
    // For addition: focus and start editing the newly added node
    scheduleActivateDefaultNode(preferredUid);
  } else {
    // For deletion/renames/priority updates: sync selectedNode reference in memory without layout centering/focusing
    updateSelectedNodeReference();
  }
};

const closeContextMenu = () => {
  contextMenuVisible.value = false;
  contextMenuMode.value = 'default';
};

const showContextMenuAt = (
  node: any,
  position: { x: number; y: number },
  mode: 'default' | 'create-only' = 'default'
) => {
  selectedNode.value = node;
  contextMenuMode.value = mode;

  const menuWidth = 160;
  const menuHeight = mode === 'create-only' ? 120 : 280;
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  contextMenuPosition.value = {
    x: Math.min(position.x, viewportWidth - menuWidth - 12),
    y: Math.min(position.y, viewportHeight - menuHeight - 12)
  };
  contextMenuVisible.value = true;
};

const openContextMenu = (event: MouseEvent, node: any) => {
  showContextMenuAt(node, { x: event.clientX, y: event.clientY }, 'default');
};

const getNodeMenuPosition = (node: any) => {
  const rect = typeof node?.getRect === 'function' ? node.getRect() : null;
  if (rect) {
    const left = rect.x ?? rect.left ?? 0;
    const top = rect.y ?? rect.top ?? 0;
    const width = rect.width ?? rect.w ?? 0;
    const height = rect.height ?? rect.h ?? 0;

    return {
      x: left + width + 10,
      y: top + Math.max(height / 2 - 16, 0)
    };
  }

  const containerRect = mindMapContainerRef.value?.getBoundingClientRect();
  return {
    x: containerRect ? containerRect.left + 40 : window.innerWidth / 2,
    y: containerRect ? containerRect.top + 40 : window.innerHeight / 2
  };
};

const selectedNodeType = computed(() => {
  return getNodePayload(selectedNode.value)?.type || null;
});

const isModuleOrRootSelected = computed(() => {
  const type = selectedNodeType.value;
  return type === 'module' || type === 'root';
});

const isDeletableSelected = computed(() => {
  const type = selectedNodeType.value;
  return type === 'module' || type === 'case' || type === 'step' || type === 'expected' || type === 'precondition' || type === 'notes';
});

const isCaseSelected = computed(() => {
  return selectedNodeType.value === 'case';
});

const isStepSelected = computed(() => {
  return selectedNodeType.value === 'step';
});

const hasPreconditionSelected = computed(() => {
  if (!isCaseSelected.value || !selectedNode.value) return false;
  const caseId = getNodePayload(selectedNode.value).rawId;
  const targetCase = props.testCases.find(c => c.id === caseId);
  return Boolean(targetCase?.precondition?.trim());
});

const hasNotesSelected = computed(() => {
  if (!isCaseSelected.value || !selectedNode.value) return false;
  const caseId = getNodePayload(selectedNode.value).rawId;
  const targetCase = props.testCases.find(c => c.id === caseId);
  return Boolean(targetCase?.notes?.trim());
});

const currentSelectedCaseLevel = computed(() => {
  if (!isCaseSelected.value || !selectedNode.value) return null;
  const caseId = getNodePayload(selectedNode.value).rawId;
  const targetCase = props.testCases.find(c => c.id === caseId);
  return targetCase ? targetCase.level : null;
});

const handleSetPriority = (level: string) => {
  if (!isCaseSelected.value || !selectedNode.value) return;
  const caseId = getNodePayload(selectedNode.value).rawId;
  emit('update-case-level', caseId, level);
  closeContextMenu();
};

const getSelectedModuleParentId = () => {
  const selectedData = getNodePayload(selectedNode.value);
  return selectedData?.type === 'module' ? selectedData.rawId : null;
};

const getParentModuleId = (node: any) => {
  const parentData = getNodePayload(node?.parent);
  if (parentData?.type === 'module') {
    return parentData.rawId;
  }

  const nodeData = getNodePayload(node);
  if (nodeData?.type === 'module' && nodeData.rawId != null) {
    const currentModule = props.modules.find(module => module.id === nodeData.rawId);
    return currentModule?.parent ?? currentModule?.parent_id ?? null;
  }

  if (nodeData?.type === 'case' && nodeData.rawId != null) {
    const currentCase = props.testCases.find(testCase => testCase.id === nodeData.rawId);
    return currentCase?.module_id ?? null;
  }

  return null;
};

const buildDefaultNodeName = (type: 'module' | 'case') => {
  const baseName = type === 'module' ? '新建模块' : '新建用例';
  const existingNames = new Set(
    (type === 'module' ? props.modules : props.testCases).map(item => item.name)
  );

  if (!existingNames.has(baseName)) {
    return baseName;
  }

  let index = 2;
  while (existingNames.has(`${baseName} ${index}`)) {
    index += 1;
  }

  return `${baseName} ${index}`;
};

const getTypeBadgeLabel = (nodeData: any) => {
  if (!nodeData?.uid) return null;

  if (nodeData.type === 'module') return '模块';
  if (nodeData.type === 'case') return nodeData.level || 'P2';
  if (nodeData.type === 'root') return '项目';
  if (nodeData.type === 'precondition') return '前置条件';
  if (nodeData.type === 'notes') return '备注';
  if (nodeData.type === 'step') return '步骤';
  if (nodeData.type === 'expected') return '预期';

  return null;
};

const isExternalTypeBadgeNode = (nodeData: any) => {
  return false;
};

const buildTypeBadgeStyle = (nodeData: any) => {
  const themeCfg = themeColorMap[activeTheme.value] || themeColorMap.classic;
  const isDark = activeTheme.value === 'dark' || activeTheme.value === 'blackGold';

  if (nodeData?.type === 'case') {
    const levelColors: Record<string, { background: string; color: string; border: string }> = {
      'P0': { background: '#fff2f0', color: '#ff4d4f', border: '#ffccc7' },
      'P1': { background: '#fff7e6', color: '#ff7a45', border: '#ffd591' },
      'P2': { background: '#e6f7ff', color: '#1890ff', border: '#91d5ff' },
      'P3': { background: '#f5f5f5', color: '#8c8c8c', border: '#d9d9d9' }
    };
    const darkLevelColors: Record<string, { background: string; color: string; border: string }> = {
      'P0': { background: 'rgba(255, 77, 79, 0.15)', color: '#ff7875', border: 'rgba(255, 77, 79, 0.3)' },
      'P1': { background: 'rgba(255, 122, 69, 0.15)', color: '#ff9c6e', border: 'rgba(255, 122, 69, 0.3)' },
      'P2': { background: 'rgba(24, 144, 255, 0.15)', color: '#69c0ff', border: 'rgba(24, 144, 255, 0.3)' },
      'P3': { background: 'rgba(140, 140, 140, 0.15)', color: '#bfbfbf', border: 'rgba(140, 140, 140, 0.3)' }
    };
    const level = nodeData.level || 'P2';
    return isDark ? darkLevelColors[level] : levelColors[level];
  }

  if (nodeData?.type === 'root') {
    return {
      background: themeCfg.secondary,
      color: themeCfg.text,
      border: themeCfg.primary
    };
  }

  if (nodeData?.type === 'module') {
    return {
      background: themeCfg.secondary,
      color: themeCfg.text,
      border: themeCfg.primary
    };
  }

  if (nodeData?.type === 'precondition') {
    if (isDark) {
      return {
        background: 'rgba(255, 156, 26, 0.15)',
        color: '#ffb042',
        border: 'rgba(255, 156, 26, 0.3)'
      };
    }
    return {
      background: '#fff7e6',
      color: '#ff9c1a',
      border: '#ffecc4'
    };
  }

  if (nodeData?.type === 'notes') {
    if (isDark) {
      return {
        background: '#282828',
        color: '#a6a6a6',
        border: '#3e3e3e'
      };
    }
    return {
      background: '#f2f3f5',
      color: '#86909c',
      border: '#e5e6eb'
    };
  }

  if (nodeData?.type === 'step') {
    if (isDark) {
      return {
        background: 'rgba(0, 180, 42, 0.15)',
        color: '#4cd263',
        border: 'rgba(0, 180, 42, 0.3)'
      };
    }
    return {
      background: '#e8ffea',
      color: '#00b42a',
      border: '#d3f4d6'
    };
  }

  if (nodeData?.type === 'expected') {
    if (isDark) {
      return {
        background: 'rgba(159, 64, 255, 0.15)',
        color: '#c084fc',
        border: 'rgba(159, 64, 255, 0.3)'
      };
    }
    return {
      background: '#f3e6ff',
      color: '#9f40ff',
      border: '#eed9ff'
    };
  }

  return {
    background: themeCfg.secondary,
    color: themeCfg.text,
    border: themeCfg.primary
  };
};

const createBadgeContent = (
  badgeLabel: string,
  badgeStyle: { background: string; color: string; border: string },
  {
    pointerEvents = 'auto',
    safePaddingY = 0,
    gapAfter = 0
  }: { pointerEvents?: string; safePaddingY?: number; gapAfter?: number } = {}
) => {
  const badgeHeight = 20;
  const outerHeight = badgeHeight + safePaddingY * 2;
  const badgeWidthPadding = 16;
  const shell = document.createElement('div');
  shell.style.cssText = [
    'display:flex',
    'align-items:center',
    `height:${outerHeight}px`,
    `padding:${safePaddingY}px ${gapAfter}px ${safePaddingY}px 0`,
    'box-sizing:border-box',
    'overflow:visible',
    `pointer-events:${pointerEvents}`
  ].join(';');

  const wrapper = document.createElement('div');
  wrapper.style.cssText = [
    'display:inline-flex',
    'align-items:center',
    'justify-content:center',
    `height:${badgeHeight}px`,
    'padding:0 8px',
    `border:1px solid ${badgeStyle.border}`,
    'border-radius:4px',
    `background:${badgeStyle.background}`,
    `color:${badgeStyle.color}`,
    'font-size:11px',
    'font-weight:600',
    `line-height:${badgeHeight}px`,
    'box-sizing:border-box',
    'user-select:none',
    'white-space:nowrap',
    `pointer-events:${pointerEvents}`
  ].join(';');

  const text = document.createElement('span');
  text.textContent = badgeLabel;
  text.style.cssText = [
    'display:block',
    `line-height:${badgeHeight}px`,
    'transform:translateY(0.5px)',
    'white-space:nowrap'
  ].join(';');
  wrapper.appendChild(text);
  shell.appendChild(wrapper);

  const isChinese = /[\u4e00-\u9fa5]/.test(badgeLabel);
  const charWidth = isChinese ? 12 : 7;
  const badgeWidth = Math.ceil(badgeLabel.length * charWidth) + badgeWidthPadding;

  return {
    el: shell,
    width: badgeWidth + gapAfter,
    height: outerHeight
  };
};

const createNodeTypeBadge = (node: any) => {
  const nodeData = getNodePayload(node);
  const badgeLabel = getTypeBadgeLabel(nodeData);
  if (!badgeLabel || isExternalTypeBadgeNode(nodeData)) return null;

  const badgeStyle = buildTypeBadgeStyle(nodeData);
  return createBadgeContent(badgeLabel, badgeStyle, { safePaddingY: 1, gapAfter: 6 });
};

const createExternalNodeTypeBadge = (node: any) => {
  const nodeData = getNodePayload(node);
  const badgeLabel = getTypeBadgeLabel(nodeData);
  if (!badgeLabel || !isExternalTypeBadgeNode(nodeData)) return null;

  const badgeStyle = buildTypeBadgeStyle(nodeData);
  return createBadgeContent(badgeLabel, badgeStyle, { pointerEvents: 'none', safePaddingY: 1 });
};

const formatModuleText = (name: string) => name;

const formatCaseText = (testCase: TestCase) => testCase.name;

const formatRootText = (name: string) => name;

const buildStepNode = (
  caseId: number,
  step: { step_number?: number; description: string; expected_result: string },
  styleConfig: {
    fillColor: string;
    borderColor: string;
    textColor: string;
    expectedFillColor: string;
    expectedBorderColor: string;
    expectedTextColor: string;
  },
  expandStates?: Record<string, boolean>
) => {
  const stepNumber = step.step_number || 0;
  const stepDescription = step.description?.trim() || '未填写';
  const expectedResult = step.expected_result?.trim() || '';
  const stepUid = `step-${caseId}-${stepNumber}`;

  return {
    data: {
      text: `步骤 ${stepNumber}: ${stepDescription}`,
      uid: stepUid,
      type: 'step',
      rawId: caseId,
      expand: (expandStates && expandStates[stepUid] !== undefined)
        ? expandStates[stepUid]
        : (newCaseExpandStates.value.has(stepUid)
          ? newCaseExpandStates.value.get(stepUid)
          : true),
      customStyles: {
        fillColor: styleConfig.fillColor,
        fontSize: '11px',
        borderColor: styleConfig.borderColor,
        borderWidth: '1px',
        color: styleConfig.textColor
      }
    },
    children: expectedResult
      ? [
          {
            data: {
              text: `预期：${expectedResult}`,
              uid: `expected-${caseId}-${stepNumber}`,
              type: 'expected',
              rawId: caseId,
              customStyles: {
                fillColor: styleConfig.expectedFillColor,
                fontSize: '11px',
                borderColor: styleConfig.expectedBorderColor,
                borderWidth: '1px',
                color: styleConfig.expectedTextColor
              }
            },
            children: []
          }
        ]
      : []
  };
};

const stripModuleLabel = (text: string) => {
  return text.trim();
};

const stripCaseLabel = (text: string) => {
  return text
    .replace(/^\[P\d\]\s*/, '')
    .trim();
};

const stripStepLabel = (text: string, stepNumber: number) => {
  const prefix = `步骤 ${stepNumber}:`;
  if (text.startsWith(prefix)) {
    return text.substring(prefix.length).trim();
  }
  return text.replace(/^步骤\s*\d+\s*:\s*/, '').trim();
};

const stripExpectedLabel = (text: string) => {
  const prefix = `预期：`;
  if (text.startsWith(prefix)) {
    return text.substring(prefix.length).trim();
  }
  return text.replace(/^预期\s*：\s*/, '').trim();
};

const stripPreconditionLabel = (text: string) => {
  const prefix = `前置条件：`;
  if (text.startsWith(prefix)) {
    return text.substring(prefix.length).trim();
  }
  return text.replace(/^前置条件\s*：\s*/, '').trim();
};

const stripNotesLabel = (text: string) => {
  const prefix = `备注：`;
  if (text.startsWith(prefix)) {
    return text.substring(prefix.length).trim();
  }
  return text.replace(/^备注\s*：\s*/, '').trim();
};

const getCaseNodeFromStepLikeNode = (node: any) => {
  const nodeData = getNodePayload(node);
  if (!nodeData) return null;

  if (nodeData.type === 'case') {
    return node;
  }

  if (nodeData.type === 'step' && getNodePayload(node.parent)?.type === 'case') {
    return node.parent;
  }

  if (nodeData.type === 'expected') {
    const stepNode = node.parent;
    if (getNodePayload(stepNode)?.type === 'step' && getNodePayload(stepNode.parent)?.type === 'case') {
      return stepNode.parent;
    }
  }

  return null;
};

const openDirectCreateMenu = (node: any) => {
  showContextMenuAt(node, getNodeMenuPosition(node), 'create-only');
};

const handleDirectChildCreate = (node: any) => {
  const nodeData = getNodePayload(node);
  if (!nodeData) return;

  if (nodeData.type === 'root') {
    // 选中根节点时，快速新增子模块，因为测试用例不能直接放在根节点下（后端限制必选模块）
    emit('create-module', null, buildDefaultNodeName('module'));
    return;
  }

  if (nodeData.type === 'module') {
    // 选中模块时，快速新增用例，免弹窗
    emit('create-case', nodeData.rawId, buildDefaultNodeName('case'));
    return;
  }

  if (nodeData.type === 'case') {
    const caseId = nodeData.rawId;
    const targetCase = props.testCases.find(c => c.id === caseId);
    if (!targetCase) return;

    const hasPrecondition = Boolean(targetCase.precondition?.trim());
    const hasSteps = Boolean(targetCase.steps && targetCase.steps.length > 0);
    const hasNotes = Boolean(targetCase.notes?.trim());

    if (!hasPrecondition) {
      // 1. 没有前置条件，优先添加前置条件
      emit('update-precondition', caseId, '新前置条件');
      pendingEditUid.value = `precondition-${caseId}`;
    } else if (!hasSteps) {
      // 2. 有前置条件但没有步骤，添加第一个步骤（和预期一起出来）
      emit('create-step', caseId, {
        description: '新步骤',
        expectedResult: '新预期结果'
      });
      pendingEditUid.value = `step-${caseId}-1`;
    } else if (!hasNotes) {
      // 3. 有步骤但没有备注，添加备注
      emit('update-notes', caseId, '新备注');
      pendingEditUid.value = `notes-${caseId}`;
    } else {
      // 4. 都有了，则继续追加步骤
      const nextStepNumber = targetCase.steps.length + 1;
      emit('create-step', caseId, {
        description: '新步骤',
        expectedResult: '新预期结果'
      });
      pendingEditUid.value = `step-${caseId}-${nextStepNumber}`;
    }
    return;
  }

  if (nodeData.type === 'step') {
    // 选中步骤时，新建预期子节点，免弹窗
    const caseId = nodeData.rawId;
    const stepNumber = parseInt(nodeData.uid.split('-')[2], 10);
    emit('update-step-expected', caseId, stepNumber, '新预期结果');
    pendingEditUid.value = `expected-${caseId}-${stepNumber}`;
    return;
  }
};

const handleDirectSiblingCreate = (node: any) => {
  const nodeData = getNodePayload(node);
  if (!nodeData) return;

  if (nodeData.type === 'module') {
    emit('create-module', getParentModuleId(node), buildDefaultNodeName('module'));
    return;
  }

  if (nodeData.type === 'case') {
    emit('create-case', getParentModuleId(node), buildDefaultNodeName('case'));
    return;
  }

  if (nodeData.type === 'precondition') {
    // 选中前置条件按回车，新建第一个步骤，免弹窗
    const caseId = nodeData.rawId;
    emit('create-step', caseId, {
      description: '新步骤',
      expectedResult: '新预期结果'
    });
    pendingEditUid.value = `step-${caseId}-1`;
    return;
  }

  if (nodeData.type === 'step') {
    // 选中步骤时按回车，直接创建同级步骤，免弹窗
    const caseId = nodeData.rawId;
    const targetCase = props.testCases.find(c => c.id === caseId);
    const nextStepNumber = (targetCase?.steps?.length || 0) + 1;
    emit('create-step', caseId, {
      description: '新步骤',
      expectedResult: '新预期结果'
    });
    pendingEditUid.value = `step-${caseId}-${nextStepNumber}`;
    return;
  }

  if (nodeData.type === 'expected') {
    // 选中预期结果时按回车，新建同级步骤，免弹窗
    const caseNode = getCaseNodeFromStepLikeNode(node);
    if (caseNode) {
      const caseId = getNodePayload(caseNode).rawId;
      const targetCase = props.testCases.find(c => c.id === caseId);
      const nextStepNumber = (targetCase?.steps?.length || 0) + 1;
      emit('create-step', caseId, {
        description: '新步骤',
        expectedResult: '新预期结果'
      });
      pendingEditUid.value = `step-${caseId}-${nextStepNumber}`;
    }
    return;
  }

  if (nodeData.type === 'root') {
    openDirectCreateMenu(node);
  }
};

const isNodeDeletable = (node: any): boolean => {
  const payload = getNodePayload(node);
  const type = payload?.type;
  return type === 'module' || type === 'case' || type === 'step' || type === 'expected' || type === 'precondition' || type === 'notes';
};

const handleDirectCreateShortcut = (key: string, nodeList: any[]) => {
  const textEdit = (mindMapInstance.value as any)?.renderer?.textEdit;
  if (typeof textEdit?.isShowTextEdit === 'function' && textEdit.isShowTextEdit()) {
    if ((key === 'Tab' || key === 'Enter') && typeof textEdit.hideEditTextBox === 'function') {
      textEdit.hideEditTextBox();
      return true;
    }
    return key === 'Insert' || key === 'Shift+Tab';
  }

  const lowerKey = key.toLowerCase();

  // 0. 拦截并处理 Ctrl+C / Ctrl+V / Ctrl+X 快捷键，保证复制粘贴状态的一致性，防止前端直接本地渲染出临时节点导致闪烁/展开抖动
  if (lowerKey === 'control+c' || lowerKey === 'meta+c') {
    const activeNode = nodeList.length === 1 ? nodeList[0] : selectedNode.value;
    if (!activeNode) return true;
    const payload = getNodePayload(activeNode);
    if (!payload || payload.type === 'root') {
      Message.warning('不能复制根节点');
      return true;
    }
    clipboardNode.value = JSON.parse(JSON.stringify(payload));
    Message.success(`已复制节点: ${payload.text}`);
    return true; // 拦截组件默认行为
  }

  if (lowerKey === 'control+v' || lowerKey === 'meta+v') {
    if (!clipboardNode.value) {
      Message.warning('剪贴板为空，请先复制节点');
      return true;
    }
    const activeNode = nodeList.length === 1 ? nodeList[0] : selectedNode.value;
    if (!activeNode) return true;

    const parentData = getNodePayload(activeNode);
    const clipData = clipboardNode.value;
    const clipType = clipData.type;
    const clipRawId = clipData.rawId;

    if (clipType === 'case') {
      if (parentData?.type !== 'module') {
        Message.warning('用例只能粘贴到模块节点下');
        return true;
      }
      const targetModuleId = parentData.rawId;
      console.log(`[Mindmap Shortcut Paste] case: sourceId=${clipRawId}, targetModuleId=${targetModuleId}`);
      lastCopiedCaseExpandMap.value = captureSourceExpandStates(clipRawId);
      isPasting.value = true;
      emit('copy-case', clipRawId, targetModuleId);
    } else if (clipType === 'module') {
      const targetParentId = parentData?.type === 'module' ? parentData.rawId : null;
      console.log(`[Mindmap Shortcut Paste] module: sourceId=${clipRawId}, targetParentId=${targetParentId}`);
      isPasting.value = true;
      emit('copy-module', clipRawId, targetParentId);
    } else if (clipType === 'step') {
      if (parentData?.type === 'case') {
        const targetCaseId = parentData.rawId;
        let stepNum = 1;
        if (clipData.uid?.startsWith('step-')) {
          stepNum = parseInt(clipData.uid.split('-')[2], 10);
        } else {
          const match = clipData.text?.match(/^步骤\s*(\d+):/);
          if (match) {
            stepNum = parseInt(match[1], 10);
          }
        }
        console.log(`[Mindmap Shortcut Paste] step: sourceCaseId=${clipRawId}, stepNum=${stepNum}, targetCaseId=${targetCaseId}`);
        emit('copy-step', clipRawId, stepNum, targetCaseId);
      } else {
        Message.warning('步骤只能粘贴到用例节点下');
      }
    } else if (clipType === 'precondition') {
      if (parentData?.type === 'case') {
        const targetCaseId = parentData.rawId;
        const text = stripPreconditionLabel(clipData.text);
        console.log(`[Mindmap Shortcut Paste] precondition: targetCaseId=${targetCaseId}, text=${text}`);
        emit('update-precondition', targetCaseId, text);
      } else {
        Message.warning('前置条件只能粘贴到用例节点下');
      }
    } else if (clipType === 'notes') {
      if (parentData?.type === 'case') {
        const targetCaseId = parentData.rawId;
        const text = stripNotesLabel(clipData.text);
        console.log(`[Mindmap Shortcut Paste] notes: targetCaseId=${targetCaseId}, text=${text}`);
        emit('update-notes', targetCaseId, text);
      } else {
        Message.warning('备注只能粘贴到用例节点下');
      }
    } else if (clipType === 'expected') {
      if (parentData?.type === 'step') {
        const targetCaseId = parentData.rawId;
        let targetStepNumber = 1;
        if (parentData.uid?.startsWith('step-')) {
          targetStepNumber = parseInt(parentData.uid.split('-')[2], 10);
        } else {
          const match = parentData.text?.match(/^步骤\s*(\d+):/);
          if (match) {
            targetStepNumber = parseInt(match[1], 10);
          }
        }
        const text = stripExpectedLabel(clipData.text);
        console.log(`[Mindmap Shortcut Paste] expected: targetCaseId=${targetCaseId}, stepNum=${targetStepNumber}, text=${text}`);
        emit('update-step-expected', targetCaseId, targetStepNumber, text);
      } else {
        Message.warning('预期结果只能粘贴到步骤节点下');
      }
    }
    return true; // 拦截组件默认行为
  }

  if (lowerKey === 'control+x' || lowerKey === 'meta+x') {
    Message.info('暂不支持剪切操作，您可以使用复制后删除来代替');
    return true; // 拦截组件默认行为
  }

  // 1. 优先捕获并拦截删除键 (Delete / Backspace)，防止组件在多选时直接在前端本地渲染中删掉节点而没有保存后端
  if (key === 'Delete' || key === 'Del' || key === 'Backspace') {
    const deletableNodes = nodeList.filter(node => isNodeDeletable(node));
    if (deletableNodes.length > 0) {
      handleDeleteSelectedNode(deletableNodes);
      return true; // 拦截组件默认行为
    }
    return false;
  }

  // 2. 多选情况下，拦截其他新增相关的快捷键并提示
  if (nodeList.length > 1) {
    if (key === 'Tab' || key === 'Insert' || key === 'Enter' || key === 'Shift+Tab') {
      Message.info('当前暂不支持多选直接新增，请先选中单个节点');
      return true;
    }
    return false;
  }

  const activeNode = nodeList.length === 1 ? nodeList[0] : selectedNode.value;
  if (!activeNode) return false;

  if (key === 'Tab' || key === 'Insert') {
    handleDirectChildCreate(activeNode);
    return true;
  }

  if (key === 'Enter') {
    handleDirectSiblingCreate(activeNode);
    return true;
  }

  if (key === 'Shift+Tab') {
    Message.info('当前暂不支持直接插入父节点，可先创建模块后再拖拽调整层级');
    return true;
  }

  return false;
};

const handleCreateSubmodule = () => {
  if (!isModuleOrRootSelected.value) return;
  closeContextMenu();
  emit('create-module', getSelectedModuleParentId(), buildDefaultNodeName('module'));
};

const handleCreateTestCase = () => {
  if (selectedNodeType.value !== 'module') return;
  closeContextMenu();
  emit('create-case', getSelectedModuleParentId(), buildDefaultNodeName('case'));
};

const handleCreatePrecondition = () => {
  if (!isCaseSelected.value || !selectedNode.value) return;
  closeContextMenu();
  const caseId = getNodePayload(selectedNode.value).rawId;
  emit('update-precondition', caseId, '新前置条件');
  pendingEditUid.value = `precondition-${caseId}`;
};

const handleCreateNotes = () => {
  if (!isCaseSelected.value || !selectedNode.value) return;
  closeContextMenu();
  const caseId = getNodePayload(selectedNode.value).rawId;
  emit('update-notes', caseId, '新备注');
  pendingEditUid.value = `notes-${caseId}`;
};

const handleCreateStep = () => {
  if (!isCaseSelected.value || !selectedNode.value) return;
  closeContextMenu();
  const caseId = getNodePayload(selectedNode.value).rawId;
  const targetCase = props.testCases.find(c => c.id === caseId);
  const nextStepNumber = (targetCase?.steps?.length || 0) + 1;
  emit('create-step', caseId, {
    description: '新步骤',
    expectedResult: '新预期结果'
  });
  pendingEditUid.value = `step-${caseId}-${nextStepNumber}`;
};

const handleCreateExpected = () => {
  if (!isStepSelected.value || !selectedNode.value) return;
  closeContextMenu();
  const nodeData = getNodePayload(selectedNode.value);
  const caseId = nodeData.rawId;
  const stepNumber = parseInt(nodeData.uid.split('-')[2], 10);
  emit('update-step-expected', caseId, stepNumber, '新预期结果');
  pendingEditUid.value = `expected-${caseId}-${stepNumber}`;
};

const handleDeleteSelectedNode = (customNodes?: any[]) => {
  const nodes = customNodes || (selectedNode.value ? [selectedNode.value] : []);
  if (nodes.length === 0) return;
  closeContextMenu();

  // 1. 过滤出最顶层的被选中删除节点（如果父节点和其子节点同时被选中，只用删除父节点，避免冲突）
  const topNodesToDelete = nodes.filter(node => {
    let ancestor = node.parent;
    while (ancestor) {
      if (nodes.includes(ancestor)) {
        return false;
      }
      ancestor = ancestor.parent;
    }
    return true;
  });

  if (topNodesToDelete.length === 0) return;

  // 2. 构造需要删除的具体实体列表
  const itemsToDelete = topNodesToDelete.map(node => {
    const payload = getNodePayload(node);
    const type = payload?.type;
    const rawId = payload?.rawId;
    let extraId: number | undefined = undefined;

    if (type === 'step' || type === 'expected') {
      if (payload.uid?.startsWith('step-') || payload.uid?.startsWith('expected-')) {
        extraId = parseInt(payload.uid.split('-')[2], 10);
      }
    }

    return {
      node,
      type,
      rawId,
      extraId,
      name: payload?.text || ''
    };
  }).filter(item => item.type && item.rawId != null);

  if (itemsToDelete.length === 0) return;

  // 3. 根据删除节点的数量，进行确认弹窗
  if (itemsToDelete.length === 1) {
    const item = itemsToDelete[0];
    let contentText = '';

    if (item.type === 'module') {
      contentText = `确定要删除模块“${item.name}”吗？此操作将同时删除其下的所有子模块与测试用例，且不可恢复！`;
    } else if (item.type === 'case') {
      contentText = `确定要删除测试用例“${item.name}”吗？此操作不可恢复！`;
    } else if (item.type === 'precondition') {
      contentText = `确定要删除该前置条件吗？此操作不可恢复！`;
    } else if (item.type === 'step') {
      contentText = `确定要删除该测试步骤吗？此操作不可恢复！`;
    } else if (item.type === 'expected') {
      contentText = `确定要清除该测试步骤的预期结果吗？此操作不可恢复！`;
    } else if (item.type === 'notes') {
      contentText = `确定要删除该备注信息吗？此操作不可恢复！`;
    } else {
      return;
    }

    Modal.warning({
      title: '删除确认',
      content: contentText,
      hideCancel: false,
      okText: '确认删除',
      cancelText: '取消',
      onOk: () => {
        if (item.type === 'module' || item.type === 'case') {
          emit('delete-node', item.type as any, item.rawId);
        } else if (item.type === 'precondition') {
          emit('update-precondition', item.rawId, '');
        } else if (item.type === 'notes') {
          emit('update-notes', item.rawId, '');
        } else if (item.type === 'step') {
          emit('delete-step', item.rawId, item.extraId!);
        } else if (item.type === 'expected') {
          emit('update-step-expected', item.rawId, item.extraId!, '');
        }
        selectedNode.value = null; // 清空选择
      }
    });
  } else {
    // 多个节点批量删除
    Modal.warning({
      title: '批量删除确认',
      content: `确定要删除选中的 ${itemsToDelete.length} 个节点及其所有子节点吗？此操作不可恢复！`,
      hideCancel: false,
      okText: '确认批量删除',
      cancelText: '取消',
      onOk: () => {
        const payloadList = itemsToDelete.map(item => ({
          type: item.type!,
          rawId: item.rawId!,
          extraId: item.extraId
        }));
        emit('delete-nodes', payloadList);
        selectedNode.value = null; // 清空选择
      }
    });
  }
};

const handleContextMenuAction = (action: 'create-submodule' | 'create-case' | 'create-precondition' | 'create-step' | 'create-notes' | 'create-expected' | 'delete' | 'copy-node' | 'paste-node') => {
  if (action === 'create-submodule') {
    handleCreateSubmodule();
    return;
  }

  if (action === 'create-case') {
    handleCreateTestCase();
    return;
  }

  if (action === 'create-precondition') {
    handleCreatePrecondition();
    return;
  }

  if (action === 'create-step') {
    handleCreateStep();
    return;
  }

  if (action === 'create-notes') {
    handleCreateNotes();
    return;
  }

  if (action === 'create-expected') {
    handleCreateExpected();
    return;
  }

  if (action === 'copy-node') {
    if (!selectedNode.value) return;
    const payload = getNodePayload(selectedNode.value);
    if (!payload || payload.type === 'root') {
      Message.warning('不能复制根节点');
      return;
    }
    clipboardNode.value = JSON.parse(JSON.stringify(payload));
    Message.success(`已复制节点: ${payload.text}`);
    closeContextMenu();
    return;
  }

  if (action === 'paste-node') {
    if (!clipboardNode.value) {
      Message.warning('剪贴板为空，请先复制节点');
      return;
    }
    if (!selectedNode.value) return;

    const parentData = getNodePayload(selectedNode.value);
    const clipData = clipboardNode.value;
    const clipType = clipData.type;
    const clipRawId = clipData.rawId;

    if (clipType === 'case') {
      if (parentData?.type !== 'module') {
        Message.warning('用例只能粘贴到模块节点下');
        closeContextMenu();
        return;
      }
      const targetModuleId = parentData.rawId;
      console.log(`[Mindmap Context Menu Paste] case: sourceId=${clipRawId}, targetModuleId=${targetModuleId}`);
      lastCopiedCaseExpandMap.value = captureSourceExpandStates(clipRawId);
      isPasting.value = true;
      emit('copy-case', clipRawId, targetModuleId);
    } else if (clipType === 'module') {
      const targetParentId = parentData?.type === 'module' ? parentData.rawId : null;
      console.log(`[Mindmap Context Menu Paste] module: sourceId=${clipRawId}, targetParentId=${targetParentId}`);
      emit('copy-module', clipRawId, targetParentId);
    } else if (clipType === 'step') {
      if (parentData?.type === 'case') {
        const targetCaseId = parentData.rawId;
        let stepNum = 1;
        if (clipData.uid?.startsWith('step-')) {
          stepNum = parseInt(clipData.uid.split('-')[2], 10);
        } else {
          const match = clipData.text?.match(/^步骤\s*(\d+):/);
          if (match) {
            stepNum = parseInt(match[1], 10);
          }
        }
        console.log(`[Mindmap Context Menu Paste] step: sourceCaseId=${clipRawId}, stepNum=${stepNum}, targetCaseId=${targetCaseId}`);
        emit('copy-step', clipRawId, stepNum, targetCaseId);
      } else {
        Message.warning('步骤只能粘贴到用例节点下');
      }
    } else if (clipType === 'precondition') {
      if (parentData?.type === 'case') {
        const targetCaseId = parentData.rawId;
        const text = stripPreconditionLabel(clipData.text);
        console.log(`[Mindmap Context Menu Paste] precondition: targetCaseId=${targetCaseId}, text=${text}`);
        emit('update-precondition', targetCaseId, text);
      } else {
        Message.warning('前置条件只能粘贴到用例节点下');
      }
    } else if (clipType === 'notes') {
      if (parentData?.type === 'case') {
        const targetCaseId = parentData.rawId;
        const text = stripNotesLabel(clipData.text);
        console.log(`[Mindmap Context Menu Paste] notes: targetCaseId=${targetCaseId}, text=${text}`);
        emit('update-notes', targetCaseId, text);
      } else {
        Message.warning('备注只能粘贴到用例节点下');
      }
    } else if (clipType === 'expected') {
      if (parentData?.type === 'step') {
        const targetCaseId = parentData.rawId;
        let targetStepNumber = 1;
        if (parentData.uid?.startsWith('step-')) {
          targetStepNumber = parseInt(parentData.uid.split('-')[2], 10);
        } else {
          const match = parentData.text?.match(/^步骤\s*(\d+):/);
          if (match) {
            targetStepNumber = parseInt(match[1], 10);
          }
        }
        const text = stripExpectedLabel(clipData.text);
        console.log(`[Mindmap Context Menu Paste] expected: targetCaseId=${targetCaseId}, stepNum=${targetStepNumber}, text=${text}`);
        emit('update-step-expected', targetCaseId, targetStepNumber, text);
      } else {
        Message.warning('预期结果只能粘贴到步骤节点下');
      }
    }

    closeContextMenu();
    return;
  }

  handleDeleteSelectedNode();
};

const relayoutMindmap = () => {
  if (!mindMapInstance.value || !mindMapContainerRef.value) return;

  const rect = mindMapContainerRef.value.getBoundingClientRect();
  if (!rect.width || !rect.height) return;

  try {
    if (typeof (mindMapInstance.value as any).resize === 'function') {
      (mindMapInstance.value as any).resize();
    }
    if (mindMapInstance.value.view && typeof (mindMapInstance.value.view as any).fit === 'function') {
      (mindMapInstance.value.view as any).fit();
    }
  } catch (e) {
    console.error('[TestCaseMindmap] relayout error:', e);
  }
};

const scheduleMindmapRelayout = () => {
  nextTick(() => {
    [0, 80, 180, 320].forEach(delay => {
      setTimeout(() => {
        if (props.visible) {
          relayoutMindmap();
        }
      }, delay);
    });
  });
};

// 构建脑图树结构
const buildMindmapTree = (expandStates?: Record<string, boolean>): any => {
  const projName = props.projectName || '测试用例脑图';
  const themeCfg = themeColorMap[activeTheme.value] || themeColorMap.classic;
  const isDarkOrBlackGold = activeTheme.value === 'dark' || activeTheme.value === 'blackGold';

  // 递归处理模块
  const buildModuleNode = (mod: TestCaseModule): any => {
    // 过滤出该模块下的用例
    const cases = props.testCases.filter(c => c.module_id === mod.id);

    // 子用例节点
    const caseNodes = cases.map(tc => {
      const levelColors: Record<string, string> = {
        'P0': '#ff4d4f',
        'P1': '#ff7a45',
        'P2': '#1890ff',
        'P3': '#8c8c8c'
      };

      const stepNodes = (tc.steps || [])
        .sort((a, b) => (a.step_number || 0) - (b.step_number || 0))
        .map(step => buildStepNode(tc.id, step, {
          fillColor: themeCfg.stepFill,
          borderColor: themeCfg.stepBorder,
          textColor: themeCfg.stepText,
          expectedFillColor: themeCfg.caseFill,
          expectedBorderColor: themeCfg.stepBorder,
          expectedTextColor: themeCfg.caseText
        }, expandStates));

      const caseChildren: any[] = [];

      // 1. 前置条件节点
      if (tc.precondition?.trim()) {
        caseChildren.push({
          data: {
            text: `前置条件：${tc.precondition.trim()}`,
            uid: `precondition-${tc.id}`,
            type: 'precondition',
            rawId: tc.id,
            customStyles: {
              fillColor: themeCfg.secondary,
              borderColor: themeCfg.primary,
              borderWidth: '1px',
              color: themeCfg.text,
              fontSize: '11px'
            }
          },
          children: []
        });
      }

      // 2. 步骤节点
      caseChildren.push(...stepNodes);

      // 3. 备注节点
      if (tc.notes?.trim()) {
        caseChildren.push({
          data: {
            text: `备注：${tc.notes.trim()}`,
            uid: `notes-${tc.id}`,
            type: 'notes',
            rawId: tc.id,
            customStyles: {
              fillColor: themeCfg.secondary,
              borderColor: themeCfg.primary,
              borderWidth: '1px',
              color: themeCfg.text,
              fontSize: '11px'
            }
          },
          children: []
        });
      }

      const hasChildren = caseChildren.length > 0;
      const caseUid = `case-${tc.id}`;

      return {
        data: {
          text: formatCaseText(tc),
          uid: caseUid,
          type: 'case',
          rawId: tc.id,
          level: tc.level,
          expand: (expandStates && expandStates[caseUid] !== undefined)
            ? expandStates[caseUid]
            : (newCaseExpandStates.value.has(caseUid)
              ? newCaseExpandStates.value.get(caseUid)
              : !hasChildren),
          customStyles: {
            borderColor: levelColors[tc.level] || '#8c8c8c',
            borderWidth: '2px',
            fillColor: themeCfg.caseFill,
            color: themeCfg.caseText
          }
        },
        children: caseChildren
      };
    });

    // 子模块节点
    const subModules = props.modules.filter(m => m.parent === mod.id || m.parent_id === mod.id);
    const subModuleNodes = subModules.map(buildModuleNode);
    const moduleUid = `module-${mod.id}`;

    return {
      data: {
        text: formatModuleText(mod.name),
        uid: moduleUid,
        type: 'module',
        rawId: mod.id,
        expand: expandStates && expandStates[moduleUid] !== undefined ? expandStates[moduleUid] : true,
        customStyles: {
          fillColor: 'transparent',
          color: themeCfg.text,
          fontWeight: 'bold',
          borderColor: 'transparent',
          borderWidth: '0px'
        }
      },
      children: [...subModuleNodes, ...caseNodes]
    };
  };

  let rootText = projName;
  let topModules: TestCaseModule[] = [];

  if (props.selectedModuleId) {
    const selectedMod = props.modules.find(m => m.id === props.selectedModuleId);
    if (selectedMod) {
      rootText = selectedMod.name;
      topModules = props.modules.filter(m => m.parent === props.selectedModuleId || m.parent_id === props.selectedModuleId);
    }
  } else {
    // 项目根节点下的顶级模块
    topModules = props.modules.filter(m => !m.parent && !m.parent_id);
  }

  // 顶级用例（属于当前展示根节点、且不属于任何更深子模块的用例）
  const topCases = props.testCases.filter(c => {
    if (props.selectedModuleId) {
      return c.module_id === props.selectedModuleId;
    }
    return !c.module_id;
  });

  const topCaseNodes = topCases.map(tc => {
    const levelColors: Record<string, string> = {
      'P0': '#ff4d4f',
      'P1': '#ff7a45',
      'P2': '#1890ff',
      'P3': '#8c8c8c'
    };

    const stepNodes = (tc.steps || [])
      .sort((a, b) => (a.step_number || 0) - (b.step_number || 0))
      .map(step => buildStepNode(tc.id, step, {
        fillColor: isDarkOrBlackGold ? '#181b22' : '#f5f6f7',
        borderColor: isDarkOrBlackGold ? '#2e3340' : '#e5e6eb',
        textColor: '#86909c',
        expectedFillColor: isDarkOrBlackGold ? '#232733' : '#ffffff',
        expectedBorderColor: isDarkOrBlackGold ? '#2e3340' : '#e5e6eb',
        expectedTextColor: isDarkOrBlackGold ? '#e5e6eb' : '#4e5969'
      }, expandStates));

    const caseChildren: any[] = [];

    // 1. 前置条件节点
    if (tc.precondition?.trim()) {
      caseChildren.push({
        data: {
          text: `前置条件：${tc.precondition.trim()}`,
          uid: `precondition-${tc.id}`,
          type: 'precondition',
          rawId: tc.id,
          customStyles: {
            fillColor: isDarkOrBlackGold ? '#232733' : themeCfg.secondary,
            borderColor: themeCfg.primary,
            borderWidth: '1px',
            color: isDarkOrBlackGold ? '#e5e6eb' : themeCfg.text,
            fontSize: '11px'
          }
        },
        children: []
      });
    }

    // 2. 步骤节点
    caseChildren.push(...stepNodes);

    // 3. 备注节点
    if (tc.notes?.trim()) {
      caseChildren.push({
        data: {
          text: `备注：${tc.notes.trim()}`,
          uid: `notes-${tc.id}`,
          type: 'notes',
          rawId: tc.id,
          customStyles: {
            fillColor: isDarkOrBlackGold ? '#232733' : themeCfg.secondary,
            borderColor: themeCfg.primary,
            borderWidth: '1px',
            color: isDarkOrBlackGold ? '#e5e6eb' : themeCfg.text,
            fontSize: '11px'
          }
        },
        children: []
      });
    }

    const hasChildren = caseChildren.length > 0;
    const caseUid = `case-${tc.id}`;

    return {
      data: {
        text: formatCaseText(tc),
        uid: caseUid,
        type: 'case',
        rawId: tc.id,
        level: tc.level,
        expand: (expandStates && expandStates[caseUid] !== undefined)
          ? expandStates[caseUid]
          : (newCaseExpandStates.value.has(caseUid)
            ? newCaseExpandStates.value.get(caseUid)
            : !hasChildren),
        customStyles: {
          borderColor: levelColors[tc.level] || '#8c8c8c',
          borderWidth: '2px',
          fillColor: isDarkOrBlackGold ? '#232733' : '#ffffff',
          color: isDarkOrBlackGold ? '#e5e6eb' : '#1d2129'
        }
      },
      children: caseChildren
    };
  });

  const rootStyles = {
    fillColor: 'transparent',
    color: themeCfg.text,
    fontSize: '16px',
    fontWeight: 'bold',
    borderColor: 'transparent',
    borderWidth: '0px'
  };
  const rootUid = props.selectedModuleId ? `module-${props.selectedModuleId}` : 'root';

  return {
    data: {
      text: formatRootText(rootText),
      uid: rootUid,
      type: props.selectedModuleId ? 'module' : 'root',
      rawId: props.selectedModuleId,
      expand: expandStates && expandStates[rootUid] !== undefined ? expandStates[rootUid] : true,
      customStyles: rootStyles
    },
    children: [...topModules.map(buildModuleNode), ...topCaseNodes]
  };
};

// 初始化思维导图
const initMindmap = () => {
  if (!props.visible || !mindMapContainerRef.value || isInitializing.value) return;

  // 增加容器宽高物理检查，防止 simple-mind-map 渲染因宽高为0抛出 Error: 容器元素el的宽高不能为0 崩溃
  const rect = mindMapContainerRef.value.getBoundingClientRect();
  if (!rect || rect.width === 0 || rect.height === 0) {
    console.warn('[TestCaseMindmap] 容器元素el的实际宽高为0，跳过同步初始化，等待 ResizeObserver 自动装载');
    return;
  }

  isInitializing.value = true;

  try {
    const mindmapData = buildMindmapTree();

    if (mindMapInstance.value) {
      mindMapInstance.value.destroy();
      mindMapInstance.value = null;
    }

    mindMapInstance.value = new MindMap({
      el: mindMapContainerRef.value,
      data: mindmapData,
      theme: activeTheme.value,
      readonly: false,
      isShowCreateChildBtnIcon: true,
      createNodePrefixContent: (node: any) => {
        return createNodeTypeBadge(node);
      },
      addCustomContentToNode: {
        create: (node: any) => {
          return createExternalNodeTypeBadge(node);
        },
        handle: ({ content, element, node }: any) => {
          const badgeGap = 8;
          element
            .x(-(content.width + badgeGap))
            .y(Math.round((node.height - content.height) / 2));
        }
      },
      customQuickCreateChildBtnClick: (node: any) => {
        handleDirectChildCreate(node);
      },
      beforeShortcutRun: (key: string, nodeList: any[]) => {
        return handleDirectCreateShortcut(key, nodeList);
      },
      useLeftKeySelectionRightKeyDrag: true,
      mouseScaleCenterUseMousePosition: true,
      layout: 'logicalStructure' // 逻辑结构图
    } as any);

    // 绑定事件
    // 1. 点击节点仅保留脑图内选中行为，不再跳转到列表详情页
    mindMapInstance.value.on('node_click', (node: any) => {
      closeContextMenu();
    });

    // 2. 监听数据改变（包括拖拽模块、修改文字）
    mindMapInstance.value.on('data_change', (newData: any) => {
      handleTreeDataChange(newData);
    });

    // 3. 监听节点激活（选中）事件，更新 selectedNode 状态给右键菜单与后续操作
    mindMapInstance.value.on('node_active', (node: any, nodeList: any[]) => {
      closeContextMenu();
      selectedNode.value = nodeList && nodeList.length === 1 ? nodeList[0] : null;
    });

    // 4. 监听节点右键菜单，提供就地创建/删除入口
    mindMapInstance.value.on('node_contextmenu', (event: MouseEvent, node: any) => {
      openContextMenu(event, node);
    });

    scheduleActivateDefaultNode(getDefaultNodeUid());
    scheduleMindmapRelayout();

  } catch (error) {
    console.error('初始化思维导图失败:', error);
    Message.error('渲染思维导图时发生错误');
  } finally {
    isInitializing.value = false;
  }
};

// 判断节点是否具有符合数据库结构规律的标准UID
const isStandardUid = (uid: string, type: string, rawId: number): boolean => {
  if (!uid || !type) return true;
  if (type === 'root') return uid === 'root';
  if (type === 'module') return uid === `module-${rawId}`;
  if (type === 'case') return uid === `case-${rawId}`;
  if (type === 'precondition') return uid === `precondition-${rawId}`;
  if (type === 'notes') return uid === `notes-${rawId}`;
  if (type === 'step') {
    const parts = uid.split('-');
    return parts[0] === 'step' && parts[1] === String(rawId) && parts.length === 3 && !isNaN(Number(parts[2]));
  }
  if (type === 'expected') {
    const parts = uid.split('-');
    return parts[0] === 'expected' && parts[1] === String(rawId) && parts.length === 3 && !isNaN(Number(parts[2]));
  }
  return true;
};

// 被粘贴节点描述接口
interface PastedItem {
  node: any;
  parentNode: any;
  type: string;
  rawId: number;
  uid: string;
}

// 分析脑图树变化，更新到后端
const handleTreeDataChange = (newTree: any) => {
  if (!props.currentProjectId) return;

  // 0. 优先检测复制粘贴（包括键盘 Ctrl+V 和右键菜单）行为
  const occurrences = new Map<string, any[]>();
  const parentMap = new Map<any, any>();
  const collectNodes = (node: any, parentNode: any = null) => {
    if (!node || !node.data) return;
    if (parentNode) {
      parentMap.set(node, parentNode);
    }
    const uid = node.data.uid;
    if (uid) {
      if (!occurrences.has(uid)) {
        occurrences.set(uid, []);
      }
      occurrences.get(uid)!.push({ node, parentNode });
    }
    if (node.children && node.children.length > 0) {
      node.children.forEach((child: any) => collectNodes(child, node));
    }
  };
  collectNodes(newTree);

  const pastedItemsList: PastedItem[] = [];

  // 遍历所有 UID 分组，识别被粘贴克隆出的新节点
  for (const [uid, list] of occurrences.entries()) {
    if (list.length === 1) {
      // 只有一个节点对应此 UID。如果是粘贴产生的节点，为了保证唯一性，脑图组件可能会生成一个随机的全新 UID，
      // 但它的 data 里仍旧克隆保留了源节点的 rawId 与 type 属性。
      // 因此我们可以通过 UID 是否符合该 type 的标准格式来判定它是否是一个被克隆的新节点 (Case A)。
      const item = list[0];
      const type = item.node.data?.type;
      const rawId = item.node.data?.rawId;
      if (type && type !== 'root' && rawId !== undefined && rawId !== null) {
        if (!isStandardUid(uid, type, rawId)) {
          pastedItemsList.push({
            node: item.node,
            parentNode: item.parentNode,
            type,
            rawId,
            uid
          });
        }
      }
    } else {
      // 存在重复的 UID (Case B)。脑图复制时如果没有自动生成唯一 UID，可能会产生完全一样的 UID，
      // 我们需要通过它的父层级以及 props 里面的原始状态来识别出哪一个是“源头”，剩下所有的都是粘贴副本。
      const type = list[0].node.data.type;
      const rawId = list[0].node.data.rawId;
      let originalIndex = -1;

      if (type === 'case') {
        const originalCase = props.testCases.find(c => c.id === rawId);
        if (originalCase) {
          originalIndex = list.findIndex(item => {
            const parentData = getNodePayload(item.parentNode);
            const parentModId = parentData?.type === 'module' ? parentData.rawId : null;
            return parentModId === originalCase.module_id;
          });
        }
      } else if (type === 'module') {
        const originalMod = props.modules.find(m => m.id === rawId);
        if (originalMod) {
          originalIndex = list.findIndex(item => {
            const parentData = getNodePayload(item.parentNode);
            const parentModId = parentData?.type === 'module' ? parentData.rawId : null;
            return parentModId === originalMod.parent;
          });
        }
      } else if (type === 'step') {
        const parts = uid.split('-');
        const stepNum = parts.length >= 3 ? parseInt(parts[2], 10) : 1;
        const originalCase = props.testCases.find(c => c.id === rawId);
        const originalStep = originalCase?.steps?.find(s => s.step_number === stepNum);
        if (originalStep) {
          originalIndex = list.findIndex(item => {
            const parentData = getNodePayload(item.parentNode);
            return parentData?.type === 'case' && parentData.rawId === rawId;
          });
        }
      } else if (type === 'precondition' || type === 'notes') {
        originalIndex = list.findIndex(item => {
          const parentData = getNodePayload(item.parentNode);
          return parentData?.type === 'case' && parentData.rawId === rawId;
        });
      } else if (type === 'expected') {
        const parts = uid.split('-');
        const stepNum = parts.length >= 3 ? parseInt(parts[2], 10) : 1;
        originalIndex = list.findIndex(item => {
          const parentData = getNodePayload(item.parentNode);
          const isParentStep = parentData?.type === 'step';
          const parentStepNum = parentData?.uid ? parseInt(parentData.uid.split('-')[2], 10) : -1;
          return isParentStep && parentData.rawId === rawId && parentStepNum === stepNum;
        });
      }

      if (originalIndex === -1) {
        originalIndex = 0;
      }

      // 非源节点均视为被粘贴进来的克隆节点
      for (let i = 0; i < list.length; i++) {
        if (i === originalIndex) continue;
        pastedItemsList.push({
          node: list[i].node,
          parentNode: list[i].parentNode,
          type,
          rawId,
          uid
        });
      }
    }
  }

  // 3. 过滤出最外层的被粘贴节点（比如复制模块时，其子用例及用例下的子节点也会被收集到 pastedItemsList 中，
  // 我们只应触发最顶级节点的复制 API，其余子节点的复制由后端递归复制自动处理）
  const rootPastedItems = pastedItemsList.filter(pastedItem => {
    let ancestor = parentMap.get(pastedItem.node);
    while (ancestor) {
      const isAncestorPasted = pastedItemsList.some(item => item.node === ancestor);
      if (isAncestorPasted) {
        return false;
      }
      ancestor = parentMap.get(ancestor);
    }
    return true;
  });

  // 4. 触发后端保存/复制接口
  if (rootPastedItems.length > 0) {
    for (const pastedItem of rootPastedItems) {
      const parentData = getNodePayload(pastedItem.parentNode);
      const { type, rawId, uid } = pastedItem;

      if (type === 'case') {
        const targetModuleId = parentData?.type === 'module' ? parentData.rawId : null;
        console.log(`[Mindmap Copy] case: sourceId=${rawId}, targetModuleId=${targetModuleId}`);
        lastCopiedCaseExpandMap.value = captureSourceExpandStates(rawId);
        isPasting.value = true;
        emit('copy-case', rawId, targetModuleId);
      } else if (type === 'module') {
        const targetParentId = parentData?.type === 'module' ? parentData.rawId : null;
        console.log(`[Mindmap Copy] module: sourceId=${rawId}, targetParentId=${targetParentId}`);
        emit('copy-module', rawId, targetParentId);
      } else if (type === 'step') {
        if (parentData?.type === 'case') {
          const targetCaseId = parentData.rawId;
          let stepNum = 1;
          if (uid.startsWith('step-')) {
            stepNum = parseInt(uid.split('-')[2], 10);
          } else {
            const match = pastedItem.node.data.text?.match(/^步骤\s*(\d+):/);
            if (match) {
              stepNum = parseInt(match[1], 10);
            }
          }
          console.log(`[Mindmap Copy] step: sourceCaseId=${rawId}, stepNum=${stepNum}, targetCaseId=${targetCaseId}`);
          emit('copy-step', rawId, stepNum, targetCaseId);
        }
      } else if (type === 'precondition') {
        if (parentData?.type === 'case') {
          const targetCaseId = parentData.rawId;
          const text = stripPreconditionLabel(pastedItem.node.data.text);
          console.log(`[Mindmap Copy] precondition: targetCaseId=${targetCaseId}, text=${text}`);
          emit('update-precondition', targetCaseId, text);
        }
      } else if (type === 'notes') {
        if (parentData?.type === 'case') {
          const targetCaseId = parentData.rawId;
          const text = stripNotesLabel(pastedItem.node.data.text);
          console.log(`[Mindmap Copy] notes: targetCaseId=${targetCaseId}, text=${text}`);
          emit('update-notes', targetCaseId, text);
        }
      } else if (type === 'expected') {
        if (parentData?.type === 'step') {
          const targetCaseId = parentData.rawId;
          let targetStepNumber = 1;
          if (parentData.uid?.startsWith('step-')) {
            targetStepNumber = parseInt(parentData.uid.split('-')[2], 10);
          } else {
            const match = parentData.text?.match(/^步骤\s*(\d+):/);
            if (match) {
              targetStepNumber = parseInt(match[1], 10);
            }
          }
          const text = stripExpectedLabel(pastedItem.node.data.text);
          console.log(`[Mindmap Copy] expected: targetCaseId=${targetCaseId}, stepNum=${targetStepNumber}, text=${text}`);
          emit('update-step-expected', targetCaseId, targetStepNumber, text);
        }
      }
    }
    // 中断常规更新，等待数据刷新重新加载整个脑图
    return;
  }

  const caseParentMap = new Map<number, number | null>();
  const moduleParentMap = new Map<number, number | null>();
  const allNodes: any[] = [];

  // 遍历新树以计算节点拓扑
  const traverse = (node: any, parentNode: any = null) => {
    if (!node || !node.data) return;

    const current = {
      uid: node.data.uid,
      type: node.data.type,
      rawId: node.data.rawId,
      text: node.data.text,
      parentUid: parentNode?.data?.uid || null,
      parentType: parentNode?.data?.type || null,
      parentRawId: parentNode?.data?.rawId || null
    };
    allNodes.push(current);

    if (current.type === 'case') {
      // 记录用例的父节点模块 ID
      let parentModId: number | null = null;
      if (current.parentType === 'module') {
        parentModId = current.parentRawId;
      }
      caseParentMap.set(current.rawId, parentModId);
    } else if (current.type === 'module') {
      // 记录模块的父节点模块 ID
      let parentModId: number | null = null;
      if (current.parentType === 'module') {
        parentModId = current.parentRawId;
      }
      moduleParentMap.set(current.rawId, parentModId);
    }

    if (node.children && node.children.length > 0) {
      node.children.forEach((child: any) => traverse(child, node));
    }
  };

  traverse(newTree);

  // 1. 检测拖拽用例模块更改 (Drag and Drop of cases)
  for (const [caseId, newParentId] of caseParentMap.entries()) {
    const originalCase = props.testCases.find(c => c.id === caseId);
    if (originalCase) {
      const oldParentId = originalCase.module_id || null;
      if (oldParentId !== newParentId) {
        console.log(`用例 ${caseId} 模块被更改：${oldParentId} -> ${newParentId}`);
        ignoreNextPropsUpdate.value = true;
        emit('update-case-module', caseId, newParentId);
      }
    }
  }

  // 2. 检测拖拽模块层级更改 (Drag and Drop of modules)
  for (const [modId, newParentId] of moduleParentMap.entries()) {
    // 排除作为脑图根节点选中的模块
    if (props.selectedModuleId === modId) continue;

    const originalMod = props.modules.find(m => m.id === modId);
    if (originalMod) {
      const oldParentId = originalMod.parent || null;
      if (oldParentId !== newParentId) {
        console.log(`模块 ${modId} 父层级被更改：${oldParentId} -> ${newParentId}`);
        ignoreNextPropsUpdate.value = true;
        emit('update-module-parent', modId, newParentId);
      }
    }
  }

  // 3. 检测重命名更改 (Double click rename)
  allNodes.forEach(node => {
    if (node.type === 'case') {
      const originalCase = props.testCases.find(c => c.id === node.rawId);
      if (originalCase) {
        const cleanName = stripCaseLabel(node.text);
        if (cleanName !== originalCase.name && cleanName.length > 0) {
          ignoreNextPropsUpdate.value = true;
          emit('rename-case', node.rawId, cleanName);
        }
      }
    } else if (node.type === 'module') {
      const originalModule = props.modules.find(m => m.id === node.rawId);
      const cleanName = stripModuleLabel(node.text);
      if (originalModule && cleanName !== originalModule.name && cleanName.length > 0) {
        ignoreNextPropsUpdate.value = true;
        emit('rename-module', node.rawId, cleanName);
      }
    } else if (node.type === 'step') {
      const originalCase = props.testCases.find(c => c.id === node.rawId);
      if (originalCase) {
        const stepNum = parseInt(node.uid.split('-')[2], 10);
        const originalStep = originalCase.steps?.find(s => s.step_number === stepNum);
        if (originalStep) {
          const cleanDesc = stripStepLabel(node.text, stepNum);
          if (cleanDesc !== originalStep.description && cleanDesc.length > 0) {
            ignoreNextPropsUpdate.value = true;
            emit('update-step-desc', node.rawId, stepNum, cleanDesc);
          }
        }
      }
    } else if (node.type === 'expected') {
      const originalCase = props.testCases.find(c => c.id === node.rawId);
      if (originalCase) {
        const stepNum = parseInt(node.uid.split('-')[2], 10);
        const originalStep = originalCase.steps?.find(s => s.step_number === stepNum);
        if (originalStep) {
          const cleanExpected = stripExpectedLabel(node.text);
          if (cleanExpected !== originalStep.expected_result) {
            ignoreNextPropsUpdate.value = true;
            emit('update-step-expected', node.rawId, stepNum, cleanExpected);
          }
        }
      }
    } else if (node.type === 'precondition') {
      const originalCase = props.testCases.find(c => c.id === node.rawId);
      if (originalCase) {
        const cleanPrecondition = stripPreconditionLabel(node.text);
        if (cleanPrecondition !== originalCase.precondition && cleanPrecondition.length > 0) {
          ignoreNextPropsUpdate.value = true;
          emit('update-precondition', node.rawId, cleanPrecondition);
        }
      }
    } else if (node.type === 'notes') {
      const originalCase = props.testCases.find(c => c.id === node.rawId);
      if (originalCase) {
        const cleanNotes = stripNotesLabel(node.text);
        if (cleanNotes !== originalCase.notes && cleanNotes.length > 0) {
          ignoreNextPropsUpdate.value = true;
          emit('update-notes', node.rawId, cleanNotes);
        }
      }
    }
  });
};

// 脑图缩放与平移操作
const handleZoomIn = () => {
  (mindMapInstance.value?.view as any).enlarge();
};

const handleZoomOut = () => {
  (mindMapInstance.value?.view as any).narrow();
};

const handleFit = () => {
  (mindMapInstance.value?.view as any).fit();
};

// 脑图导出为图片或数据
const handleExport = async (value: string | number | Record<string, any> | undefined) => {
  if (!mindMapInstance.value) return;
  exporting.value = true;
  const format = String(value);

  try {
    if (format === 'png') {
      // 导出 PNG
      const name = props.projectName || '测试用例脑图';
      await mindMapInstance.value.export('png', true, name);
      Message.success('成功导出图片');
    } else if (format === 'json') {
      // 导出 JSON 数据
      const name = `${props.projectName || '测试用例脑图'}.json`;
      const data = mindMapInstance.value.getData(true);
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", name);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      Message.success('成功导出数据文件');
    }
  } catch (err) {
    console.error('导出脑图失败:', err);
    Message.error('导出文件失败，请重试');
  } finally {
    exporting.value = false;
  }
};

// 切换思维导图的主题
const handleThemeChange = (themeName: string | number | Record<string, any> | undefined) => {
  const selectedTheme = String(themeName);
  activeTheme.value = selectedTheme;
  if (mindMapInstance.value) {
    try {
      // 1. 设置底层内置/自定义主题
      mindMapInstance.value.setTheme(selectedTheme);

      // 2. 重新构建并热更新树数据，使 node 内部 customStyles 配合主题同步刷新
      refreshMindmapData();

      // 3. 同时自适应视口进行重绘对齐
      scheduleMindmapRelayout();
    } catch (e) {
      console.error('切换思维导图主题失败:', e);
    }
  }
};

// 监听系统/全局暗黑模式，自动进行对应的脑图主题切换适配
watch(
  () => themeStore.theme,
  (newTheme) => {
    const defaultTheme = newTheme === 'black' ? 'dark' : 'classic';
    handleThemeChange(defaultTheme);
  }
);

// 监听组件可见性变化，当从隐藏切换为显示时延迟初始化，避免el宽高为0
watch(
  () => props.visible,
  (newVisible) => {
    if (newVisible) {
      nextTick(() => {
        setTimeout(() => {
          if (!mindMapInstance.value) {
            initMindmap();
          } else {
            scheduleMindmapRelayout();
          }
        }, 150); // 给 150 毫秒延迟，确保 DOM 完全展开并算好宽高
      });
    }
  }
);

// 监听模块树和用例列表数据变化
watch(
  () => [props.modules, props.testCases, props.selectedModuleId] as const,
  (newVal, oldVal) => {
    if (!props.visible) return;

    if (ignoreNextPropsUpdate.value) {
      ignoreNextPropsUpdate.value = false;
      return;
    }

    let preferredUid: string | null = null;
    if (oldVal) {
      const [oldModules, oldCases] = oldVal;
      const [newModules, newCases] = newVal;

      // 1. 如果用例列表增加了一个，说明是刚刚新建的用例，自动跟踪并激活就地编辑
      if (newCases.length === oldCases.length + 1) {
        const oldIds = new Set(oldCases.map(c => c.id));
        const newCase = newCases.find(c => !oldIds.has(c.id));
        if (newCase) {
          preferredUid = `case-${newCase.id}`;
          if (isPasting.value && lastCopiedCaseExpandMap.value) {
            // 将新用例 ID 与复制的源状态进行关联映射
            const newCaseUid = `case-${newCase.id}`;
            const newCaseExpand = lastCopiedCaseExpandMap.value.get('case');
            if (newCaseExpand !== undefined) {
              newCaseExpandStates.value.set(newCaseUid, newCaseExpand);
            }
            if (Array.isArray(newCase.steps)) {
              newCase.steps.forEach(step => {
                const newStepUid = `step-${newCase.id}-${step.step_number}`;
                const stepExpand = lastCopiedCaseExpandMap.value!.get(`step-${step.step_number}`);
                if (stepExpand !== undefined) {
                  newCaseExpandStates.value.set(newStepUid, stepExpand);
                }
              });
            }
            isPasting.value = false;
            lastCopiedCaseExpandMap.value = null;
          } else {
            pendingEditUid.value = preferredUid;
          }
        }
      }
      // 2. 如果模块列表增加了一个，说明是刚刚新建的模块，自动跟踪并激活就地编辑
      else if (newModules.length === oldModules.length + 1) {
        const oldIds = new Set(oldModules.map(m => m.id));
        const newModule = newModules.find(m => !oldIds.has(m.id));
        if (newModule) {
          preferredUid = `module-${newModule.id}`;
          if (!isPasting.value) {
            pendingEditUid.value = preferredUid;
          } else {
            isPasting.value = false;
          }
        }
      }
    }

    if (!props.loading && hasData.value) {
      nextTick(() => {
        // 如果实例存在，我们直接热更新数据以保留视口平移缩放状态
        if (mindMapInstance.value) {
          refreshMindmapData(preferredUid);
        } else {
          initMindmap();
        }
      });
    }
  },
  { deep: false }
);

// 监听加载状态
watch(
  () => props.loading,
  (newLoading) => {
    if (!props.visible) return;
    if (!newLoading && hasData.value) {
      nextTick(() => {
        if (mindMapInstance.value) {
          refreshMindmapData();
          scheduleMindmapRelayout();
        } else {
          initMindmap();
        }
      });
    }
  }
);

let resizeObserver: any = null;

// 初始化 ResizeObserver 自动响应容器尺寸变化，保障画布能随时适应布局并处理初始宽高为0的问题
const initResizeObserver = () => {
  if (typeof window === 'undefined' || !window.ResizeObserver) return;

  if (resizeObserver) {
    resizeObserver.disconnect();
  }

  resizeObserver = new window.ResizeObserver((entries) => {
    for (const entry of entries) {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) {
        if (!mindMapInstance.value && !isInitializing.value && props.visible && !props.loading && hasData.value) {
          initMindmap();
        } else if (mindMapInstance.value) {
          relayoutMindmap();
        }
      }
    }
  });

  if (mindMapContainerRef.value) {
    resizeObserver.observe(mindMapContainerRef.value);
  }
};

onMounted(() => {
  document.addEventListener('click', closeContextMenu);
  window.addEventListener('resize', closeContextMenu);
  window.addEventListener('scroll', closeContextMenu, true);
  initResizeObserver();
  if (props.visible && !props.loading && hasData.value) {
    nextTick(() => {
      initMindmap();
    });
  }
});

onBeforeUnmount(() => {
  document.removeEventListener('click', closeContextMenu);
  window.removeEventListener('resize', closeContextMenu);
  window.removeEventListener('scroll', closeContextMenu, true);
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (mindMapInstance.value) {
    mindMapInstance.value.destroy();
    mindMapInstance.value = null;
  }
});
</script>

<style scoped>
.mindmap-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  position: relative;
  background-color: var(--theme-surface);
  border: 1px solid var(--theme-border);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
}

.mindmap-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: var(--theme-surface-soft);
  border-bottom: 1px solid var(--theme-border);
  z-index: 10;
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.btn-text {
  margin-left: 4px;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

.tip-text {
  font-size: 13px;
  color: var(--theme-text-secondary);
  display: flex;
  align-items: center;
}

.tip-icon {
  color: var(--theme-accent);
  margin-right: 6px;
  font-size: 15px;
}

.mindmap-canvas-container {
  flex: 1;
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.mindmap-container {
  width: 100%;
  height: 100%;
  outline: none;
}

.state-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(var(--theme-surface-rgb, 255, 255, 255), 0.85);
  z-index: 5;
}

.node-context-menu {
  position: fixed;
  z-index: 1000;
  min-width: 160px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background-color: var(--theme-surface);
  border: 1px solid var(--theme-border);
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.16);
}

.context-menu-item {
  border: none;
  border-radius: 6px;
  padding: 8px 10px;
  text-align: left;
  background: transparent;
  color: var(--theme-text);
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.context-menu-item:hover:not(:disabled) {
  background-color: var(--theme-surface-soft);
}

.context-menu-item:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.context-menu-item.danger {
  color: #f53f3f;
}

.context-menu-item.danger:hover:not(:disabled) {
  background-color: rgba(245, 63, 63, 0.08);
}

/* 兼容暗黑模式下脑图背景，使主题自定义背景样式生效 */
.mindmap-container :deep(.simple-mind-map-svg) {
  background-color: transparent !important;
}

/* 响应式适配 */
@media (max-width: 768px) {
  .btn-text {
    display: none;
  }
  .tip-text span {
    display: none;
  }
}

.context-menu-divider {
  height: 1px;
  background-color: var(--theme-border);
  margin: 6px 4px;
}

.context-menu-priority-section {
  padding: 4px 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.priority-title {
  font-size: 11px;
  color: var(--theme-text-secondary);
  font-weight: 600;
}

.priority-options {
  display: flex;
  gap: 4px;
}

.priority-tag-btn {
  flex: 1;
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 0;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

/* P0 Style */
.priority-tag-btn.p0 {
  background-color: var(--theme-surface-soft);
  color: #ff4d4f;
  border: 1px solid transparent;
}
.priority-tag-btn.p0:hover {
  background-color: #fff2f0;
  border-color: #ffccc7;
}
.priority-tag-btn.p0.active {
  background-color: #ff4d4f !important;
  color: #ffffff !important;
  border-color: #ff4d4f !important;
  box-shadow: 0 2px 6px rgba(255, 77, 79, 0.3);
}

/* P1 Style */
.priority-tag-btn.p1 {
  background-color: var(--theme-surface-soft);
  color: #ff7a45;
  border: 1px solid transparent;
}
.priority-tag-btn.p1:hover {
  background-color: #fff7e6;
  border-color: #ffd591;
}
.priority-tag-btn.p1.active {
  background-color: #ff7a45 !important;
  color: #ffffff !important;
  border-color: #ff7a45 !important;
  box-shadow: 0 2px 6px rgba(255, 122, 69, 0.3);
}

/* P2 Style */
.priority-tag-btn.p2 {
  background-color: var(--theme-surface-soft);
  color: #1890ff;
  border: 1px solid transparent;
}
.priority-tag-btn.p2:hover {
  background-color: #e6f7ff;
  border-color: #91d5ff;
}
.priority-tag-btn.p2.active {
  background-color: #1890ff !important;
  color: #ffffff !important;
  border-color: #1890ff !important;
  box-shadow: 0 2px 6px rgba(24, 144, 255, 0.3);
}

/* P3 Style */
.priority-tag-btn.p3 {
  background-color: var(--theme-surface-soft);
  color: #8c8c8c;
  border: 1px solid transparent;
}
.priority-tag-btn.p3:hover {
  background-color: #f5f5f5;
  border-color: #d9d9d9;
}
.priority-tag-btn.p3.active {
  background-color: #8c8c8c !important;
  color: #ffffff !important;
  border-color: #8c8c8c !important;
  box-shadow: 0 2px 6px rgba(140, 140, 140, 0.3);
}
</style>
