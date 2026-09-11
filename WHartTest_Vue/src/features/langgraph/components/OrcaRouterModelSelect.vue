<template>
  <div ref="rootRef" class="orca-model-select">
    <button
      type="button"
      class="orca-trigger"
      role="combobox"
      aria-haspopup="listbox"
      :aria-expanded="open ? 'true' : 'false'"
      aria-label="OrcaRouter model"
      data-testid="orca-model-select"
      @click="toggle"
      @keydown.escape="close"
    >
      <span class="orca-trigger-label" :class="{ 'is-placeholder': !modelValue }">
        {{ selectedLabel || placeholder }}
      </span>
      <icon-down class="orca-trigger-caret" />
    </button>

    <div
      v-if="open"
      ref="panelRef"
      class="orca-panel"
      role="listbox"
      data-testid="orca-model-listbox"
      :aria-busy="loading ? 'true' : 'false'"
    >
      <div class="orca-search">
        <a-input
          v-model="query"
          size="small"
          :placeholder="searchPlaceholder"
          data-testid="orca-model-search"
          allow-clear
        />
      </div>

      <div v-if="loading" class="orca-status" data-testid="orca-model-loading">
        {{ loadingText }}
      </div>
      <div v-else-if="filteredOptions.length === 0" class="orca-status" data-testid="orca-model-empty">
        {{ emptyText }}
      </div>
      <ul v-else class="orca-options">
        <li
          v-for="option in filteredOptions"
          :key="option.value"
          class="orca-option"
          role="option"
          :aria-selected="option.value === modelValue ? 'true' : 'false'"
          :data-value="option.value"
          @click="select(option.value)"
        >
          <span class="orca-option-label">{{ option.label }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { Input as AInput } from '@arco-design/web-vue';
import { IconDown } from '@arco-design/web-vue/es/icon';

interface ModelOption {
  label: string;
  value: string;
}

interface Props {
  modelValue?: string;
  options: ModelOption[];
  loading?: boolean;
  placeholder?: string;
  searchPlaceholder?: string;
  loadingText?: string;
  emptyText?: string;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  options: () => [],
  loading: false,
  placeholder: 'Select a model',
  searchPlaceholder: 'Search models',
  loadingText: 'Loading…',
  emptyText: 'No models',
});

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'open-change', open: boolean): void;
}>();

const rootRef = ref<HTMLElement | null>(null);
const panelRef = ref<HTMLElement | null>(null);
const open = ref(false);
const query = ref('');

const selectedLabel = computed(
  () => props.options.find((option) => option.value === props.modelValue)?.label || props.modelValue
);

const filteredOptions = computed(() => {
  const needle = query.value.trim().toLowerCase();
  if (!needle) {
    return props.options;
  }
  return props.options.filter(
    (option) =>
      option.value.toLowerCase().includes(needle) || option.label.toLowerCase().includes(needle)
  );
});

const toggle = () => {
  open.value = !open.value;
};

const close = () => {
  open.value = false;
};

const select = (value: string) => {
  emit('update:modelValue', value);
  open.value = false;
};

// Reset the search each time the panel is opened so the full filtered list is
// shown rather than a leftover query.
watch(open, (next) => {
  if (!next) {
    query.value = '';
  }
  emit('open-change', next);
});

const handleDocumentPointerDown = (event: MouseEvent) => {
  if (!open.value) {
    return;
  }
  const target = event.target as Node | null;
  if (rootRef.value && target && !rootRef.value.contains(target)) {
    close();
  }
};

watch(open, (next) => {
  if (next) {
    document.addEventListener('mousedown', handleDocumentPointerDown, true);
  } else {
    document.removeEventListener('mousedown', handleDocumentPointerDown, true);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleDocumentPointerDown, true);
});

defineExpose({ open, close, panelRef });
</script>

<style scoped>
.orca-model-select {
  position: relative;
  flex: 1;
  min-width: 0;
}

.orca-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--color-border-2);
  border-radius: var(--border-radius-small);
  background: var(--color-bg-2);
  color: var(--color-text-1);
  font-size: 14px;
  cursor: pointer;
  text-align: left;
}

.orca-trigger:hover {
  border-color: rgb(var(--primary-5));
}

.orca-trigger-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.orca-trigger-label.is-placeholder {
  color: var(--color-text-3);
}

.orca-trigger-caret {
  flex: none;
  color: var(--color-text-3);
}

/* The panel is right-aligned to the trigger so the two right edges coincide;
   the opaque background and visible border keep it readable over the form. */
.orca-panel {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 1000;
  width: 360px;
  max-width: 100%;
  padding: 8px;
  border: 1px solid var(--color-border-2);
  border-radius: var(--border-radius-small);
  background: var(--color-bg-popup);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
}

.orca-search {
  margin-bottom: 6px;
}

.orca-options {
  max-height: 240px;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}

.orca-option {
  padding: 6px 8px;
  border-radius: var(--border-radius-small);
  font-size: 13px;
  color: var(--color-text-1);
  cursor: pointer;
}

.orca-option:hover {
  background: var(--color-fill-2);
}

.orca-option[aria-selected='true'] {
  background: var(--color-fill-2);
  color: rgb(var(--primary-6));
  font-weight: 500;
}

.orca-option-label {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.orca-status {
  padding: 10px 8px;
  font-size: 13px;
  color: var(--color-text-3);
}
</style>
