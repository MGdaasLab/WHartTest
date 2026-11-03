<script setup lang="ts">
/**
 * 接口参数约束预览（只读）。
 * 数据源：导入文档时平台固化的约束快照（ApiInterfaceConstraint），
 * 结构与 constraint_extractor 输出一致：params.{path,query,header}、
 * body_fields（嵌套点路径）、body_required、response。
 * 参考 MeterSphere 接口预览页：按区块折叠 + 参数表格（名称/必填/类型/约束/说明）。
 */
import { computed } from 'vue'
import type { ApiInterface } from '../../types/interface'

interface ConstraintField {
  name: string
  type: string
  required?: boolean
  constraints?: Record<string, any>
  default?: any
  description?: string
}

interface ConstraintSnapshot {
  matched: boolean
  format: string
  version: string
  document_name: string
  constraints: {
    params?: Record<'path' | 'query' | 'header', ConstraintField[]>
    body_fields?: ConstraintField[]
    body_required?: string[]
    response?: {
      success_code?: number | null
      success_codes?: number[]
      fields?: ConstraintField[]
      notes?: string[]
    }
    notes?: string[]
    truncated?: boolean
  }
  updated_at?: string
}

const props = defineProps<{
  interface?: ApiInterface | null
}>()

// constraint_snapshot 由后端 serializer 附带在接口详情上
const snapshot = computed<ConstraintSnapshot | null>(() => {
  return (props.interface as any)?.constraint_snapshot || null
})

const hasSnapshot = computed(() => !!snapshot.value?.matched)

const formatVersionText = computed(() => {
  const snap = snapshot.value
  if (!snap) return ''
  const parts: string[] = []
  if (snap.format) parts.push(snap.format.toUpperCase())
  if (snap.version) parts.push(snap.version)
  return parts.join(' / ')
})

const constraintText = (field: ConstraintField): string => {
  const entries = Object.entries(field.constraints || {})
  if (!entries.length) return '-'
  return entries.map(([key, value]) => {
    if (key === 'enum') return `enum: ${JSON.stringify(value)}`
    return `${key}: ${value}`
  }).join(', ')
}

const defaultText = (field: ConstraintField): string => {
  return field.default === undefined || field.default === null || field.default === ''
    ? '-'
    : JSON.stringify(field.default)
}

const descriptionText = (field: ConstraintField): string => field.description || '-'

const headerGroups = computed(() => {
  const params = (snapshot.value?.constraints?.params || {}) as Record<'path' | 'query' | 'header', ConstraintField[]>
  return [
    { key: 'path', title: 'Path 参数', fields: params.path || [] },
    { key: 'query', title: 'Query 参数', fields: params.query || [] },
    { key: 'header', title: '请求头', fields: params.header || [] },
  ].filter(group => group.fields.length > 0)
})

const bodyFields = computed(() => snapshot.value?.constraints?.body_fields || [])
const responseFields = computed(() => snapshot.value?.constraints?.response?.fields || [])
const successCode = computed(() => {
  const response = snapshot.value?.constraints?.response
  return response?.success_code ?? response?.success_codes?.[0] ?? null
})
const snapshotNotes = computed(() => snapshot.value?.constraints?.notes || [])

// 表格行通用构造（树形：嵌套 object/array 的子字段挂在 children，参考 MeterSphere schema 树）
type PreviewRow = {
  key: string
  name: string
  required: string
  type: string
  constraints: string
  default: string
  description: string
  children?: PreviewRow[]
}

const toRow = (field: ConstraintField, key: string, displayName: string): PreviewRow => ({
  key,
  name: displayName,
  required: field.required ? '是' : '否',
  type: field.type || 'string',
  constraints: constraintText(field),
  default: defaultText(field),
  description: descriptionText(field),
})

// 点路径行（name / crop.deptId / tags[]name）重建为嵌套树：
// 后缀为 "." 或 "[]" 的段视为容器段，其子行挂 children
const toTreeRows = (fields: ConstraintField[]): PreviewRow[] => {
  const roots: PreviewRow[] = []
  const findByKey = (rows: PreviewRow[], key: string): PreviewRow | undefined => {
    for (const row of rows) {
      if (row.key === key) return row
      if (row.children) {
        const found = findByKey(row.children, key)
        if (found) return found
      }
    }
    return undefined
  }

  for (const field of fields) {
    const fullName = field.name
    // 拆分段落：crop.deptId -> [crop, deptId]；tags[]name -> [tags, name]
    const segments: string[] = []
    let rest = fullName
    while (rest) {
      const dotIndex = rest.indexOf('.')
      const bracketIndex = rest.indexOf('[]')
      if (bracketIndex !== -1 && (dotIndex === -1 || bracketIndex < dotIndex)) {
        segments.push(rest.slice(0, bracketIndex))
        rest = rest.slice(bracketIndex + 2)
      } else if (dotIndex !== -1) {
        segments.push(rest.slice(0, dotIndex))
        rest = rest.slice(dotIndex + 1)
      } else {
        segments.push(rest)
        rest = ''
      }
    }

    let parentKey = ''
    let siblings = roots
    for (let i = 0; i < segments.length - 1; i += 1) {
      const segmentKey = parentKey ? `${parentKey}.${segments[i]}` : segments[i]
      let parent = findByKey(siblings, segmentKey)
      if (!parent) {
        // 容器段未单独成行（快照中被截断等），创建占位行保证层级完整
        parent = {
          key: segmentKey,
          name: segments[i],
          required: '-',
          type: 'object',
          constraints: '-',
          default: '-',
          description: '-',
          children: [],
        }
        siblings.push(parent)
      }
      if (!parent.children) parent.children = []
      parentKey = segmentKey
      siblings = parent.children
    }

    // 叶行：key 用完整路径（占位行 key 与叶 key 同构，保证覆盖命中），name 只显示裸段名
    const bareName = segments[segments.length - 1]
    const row = toRow(field, parentKey ? `${parentKey}.${bareName}` : bareName, bareName)
    const existing = findByKey(siblings, row.key)
    if (existing) {
      // 先有占位行后有真实行：用真实数据覆盖占位
      Object.assign(existing, row, { children: existing.children })
    } else {
      siblings.push(row)
    }
  }
  return roots
}

// 字段树默认全部收起（父子层级点击展开；Path/Query/Header/Body/响应区块本身默认展开）
const expandableFor = () => ({
  defaultExpandedRowKeys: [] as string[],
})

const toRows = (fields: ConstraintField[]): PreviewRow[] => toTreeRows(fields)

const columns = [
  { title: '参数名', dataIndex: 'name', ellipsis: true, tooltip: true },
  { title: '必填', dataIndex: 'required', width: 64 },
  { title: '类型', dataIndex: 'type', width: 96 },
  { title: '约束', dataIndex: 'constraints', ellipsis: true, tooltip: true },
  { title: '默认值', dataIndex: 'default', width: 100, ellipsis: true, tooltip: true },
  { title: '说明', dataIndex: 'description', ellipsis: true, tooltip: true },
]
</script>

<template>
  <div class="h-full overflow-y-auto p-4 space-y-3">
    <!-- 无约束快照：空态提示 -->
    <template v-if="!hasSnapshot">
      <a-empty description="暂无预览" class="h-full flex flex-col items-center justify-center">
        <template #image>
          <icon-file class="text-4xl text-gray-400" />
        </template>
      </a-empty>
    </template>

    <template v-else>
      <!-- 快照来源信息 -->
      <div class="flex items-center gap-2 text-xs text-gray-400 flex-wrap">
        <a-tag size="small" color="arcoblue">约束快照</a-tag>
        <span v-if="formatVersionText">{{ formatVersionText }}</span>
        <span v-if="snapshot?.document_name">来源文档：{{ snapshot.document_name }}</span>
        <a-tag v-if="snapshot?.constraints?.truncated" size="small" color="orange">字段较多已截断</a-tag>
      </div>

      <!-- Path / Query / Header 参数 -->
      <a-collapse
        v-if="headerGroups.length"
        :bordered="false"
        :default-active-key="headerGroups.map(group => group.key)"
      >
        <a-collapse-item v-for="group in headerGroups" :key="group.key" :header="`${group.title}（${group.fields.length}）`">
          <a-table
            :columns="columns"
            :data="toRows(group.fields)"
            :expandable="expandableFor()"
            :pagination="false"
            :bordered="{ cell: true }"
            size="small"
            class="preview-table"
          />
        </a-collapse-item>
      </a-collapse>

      <!-- Body 字段 -->
      <a-collapse :bordered="false" :default-active-key="['body']">
        <a-collapse-item v-if="bodyFields.length" key="body" :header="`Body 字段（${bodyFields.length}）`">
          <a-table
            :columns="columns"
            :data="toRows(bodyFields)"
            :expandable="expandableFor()"
            :pagination="false"
            :bordered="{ cell: true }"
            size="small"
            class="preview-table"
          />
          <div v-if="snapshot?.constraints?.body_required?.length" class="mt-2 text-xs text-gray-400">
            必填清单：{{ snapshot?.constraints?.body_required?.join('、') }}
          </div>
        </a-collapse-item>
        <a-collapse-item v-else key="body-empty" header="Body 字段">
          <div class="text-xs text-gray-400">该接口未声明请求体，无字段级约束信息</div>
        </a-collapse-item>
      </a-collapse>

      <!-- 响应结构 -->
      <a-collapse :bordered="false" :default-active-key="['response']">
        <a-collapse-item
          v-if="responseFields.length || successCode"
          key="response"
          :header="`响应结构${successCode ? `（成功状态码 ${successCode}）` : ''}`"
        >
          <a-table
            v-if="responseFields.length"
            :columns="columns"
            :data="toRows(responseFields)"
            :expandable="expandableFor()"
            :pagination="false"
            :bordered="{ cell: true }"
            size="small"
            class="preview-table"
          />
          <div v-else class="text-xs text-gray-400">文档未声明响应字段结构</div>
        </a-collapse-item>
      </a-collapse>
      <!-- 解析说明（嵌套折叠等） -->
      <div v-if="snapshotNotes.length" class="text-xs text-gray-400 space-y-1">
        <div v-for="(note, index) in snapshotNotes" :key="index">注：{{ note }}</div>
      </div>
    </template>
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
.preview-table :deep(.arco-table-th) {
  background-color: var(--color-fill-1);
  font-weight: 500;
}
</style>
