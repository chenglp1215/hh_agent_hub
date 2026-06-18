<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">对话日志</h1>
      <a-button @click="fetchList" :loading="loading">
        <template #icon><ReloadOutlined /></template>
        刷新
      </a-button>
    </div>

    <!-- 筛选栏 -->
    <div class="mb-4 flex flex-wrap gap-3">
      <a-input-search
        v-model:value="keyword"
        placeholder="搜索用户问题..."
        class="max-w-xs"
        @search="fetchList"
      />
      <a-select
        v-model:value="statusFilter"
        class="w-28"
        placeholder="状态"
        allow-clear
        @change="fetchList"
      >
        <a-select-option value="">全部状态</a-select-option>
        <a-select-option value="success">成功</a-select-option>
        <a-select-option value="error">失败</a-select-option>
      </a-select>
      <a-select
        v-model:value="appIdFilter"
        class="w-40"
        placeholder="应用"
        allow-clear
        @change="fetchList"
      >
        <a-select-option :value="undefined">全部应用</a-select-option>
        <a-select-option v-for="app in apps" :key="app.id" :value="app.id">
          {{ app.name }}
        </a-select-option>
      </a-select>
    </div>

    <!-- 日志列表 -->
    <a-table
      :dataSource="items"
      :columns="columns"
      rowKey="id"
      :loading="loading"
      :pagination="{
        current: page,
        pageSize: pageSize,
        total,
        showSizeChanger: true,
        showTotal: (t: number) => `共 ${t} 条`,
        onChange: (p: number, ps: number) => { page = p; pageSize = ps; fetchList(); },
      }"
      :expandable="{
        expandedRowRender,
        rowExpandable: () => true,
        expandRowByClick: true,
      }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'success' ? 'green' : 'red'">
            {{ record.status === 'success' ? '成功' : '失败' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'duration'">
          {{ formatDuration(record.duration_ms) }}
        </template>
        <template v-if="column.key === 'user_input'">
          <span class="text-sm truncate max-w-[200px] inline-block align-middle">
            {{ record.user_input }}
          </span>
        </template>
        <template v-if="column.key === 'final_answer'">
          <span class="text-sm truncate max-w-[250px] inline-block align-middle text-gray-400">
            {{ record.final_answer || '(空)' }}
          </span>
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatTime(record.created_at) }}
        </template>
      </template>
    </a-table>

    <!-- 详情抽屉 -->
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { chatLogsApi } from '@/api/chatLogs'
import { appsApi } from '@/api/apps'

interface ChatLogItem {
  id: number
  app_id: number
  session_id: string
  task_id: string
  user_input: string
  final_answer: string | null
  duration_ms: number | null
  status: string
  error_message: string | null
  agent_count: number
  trace_summary: any[] | null
  created_at: string | null
}

const loading = ref(false)
const items = ref<ChatLogItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// Filters
const keyword = ref('')
const statusFilter = ref('')
const appIdFilter = ref<number | undefined>(undefined)
const apps = ref<any[]>([])

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '用户问题', key: 'user_input', width: 200, ellipsis: true },
  { title: '回复', key: 'final_answer', ellipsis: true },
  { title: '耗时', key: 'duration', width: 80 },
  { title: '状态', key: 'status', width: 72 },
  { title: 'Agent 数', dataIndex: 'agent_count', key: 'agent_count', width: 72 },
  { title: '时间', key: 'created_at', width: 160 },
]

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const m = Math.floor(ms / 60000)
  const s = Math.floor((ms % 60000) / 1000)
  return `${m}m${s}s`
}

function formatTime(t: string | null): string {
  if (!t) return '-'
  const d = new Date(t)
  return d.toLocaleString('zh-CN', { hour12: false })
}

// 展开行显示简要追踪
function expandedRowRender(record: ChatLogItem) {
  const trace = record.trace_summary || []
  if (!trace.length) return '<span class="text-gray-500 text-xs">无追踪信息</span>'

  const colorMap: Record<string, string> = {
    supervisor_start: '#3b82f6',
    supervisor_route: '#8b5cf6',
    supervisor_end: '#6b7280',
    supervisor_greeting_shortcut: '#10b981',
    supervisor_force_end: '#ef4444',
    agent_start: '#06b6d4',
    agent_end: '#6366f1',
  }

  return trace.map((evt: any, i: number) => {
    const bg = colorMap[evt.type] || '#6b7280'
    return `<div class="flex items-center gap-2 text-xs font-mono py-0.5">
      <span class="text-gray-500 w-4">#${i + 1}</span>
      <span style="background:${bg}22;color:${bg};border:1px solid ${bg}44" class="px-1.5 py-0.5 rounded text-xs leading-5">${traceTagLabel(evt.type)}</span>
      <span class="text-gray-300">${traceEventText(evt)}</span>
    </div>`
  }).join('')
}

function traceTagColor(type: string): string {
  return {
    supervisor_start: 'blue',
    supervisor_route: 'purple',
    supervisor_end: 'default',
    supervisor_greeting_shortcut: 'green',
    agent_start: 'cyan',
    agent_end: 'geekblue',
  }[type] || 'default'
}

function traceTagLabel(type: string): string {
  return {
    supervisor_start: '调度',
    supervisor_route: '路由',
    supervisor_end: '结束',
    supervisor_greeting_shortcut: '问候',
    supervisor_force_end: '强制结束',
    agent_start: '执行',
    agent_end: '完成',
    agent_result: '结果',
    agent_call: '调用',
  }[type] || type
}

function traceTagClass(type: string): string {
function traceEventText(evt: any): string {
  if (evt.type === 'supervisor_route') return `→ ${evt.target || 'end'}`
  if (evt.type === 'supervisor_start') return `第 ${evt.round} 轮调度`
  if (evt.type === 'supervisor_greeting_shortcut') return '问候语直接回复'
  if (evt.type === 'agent_start') return `${evt.agent} 开始执行`
  if (evt.type === 'agent_end') return `${evt.agent} 完成 (${formatDuration(evt.elapsed_ms)})`
  if (evt.type === 'supervisor_force_end') return '已达最大轮次强制结束'
  if (evt.type === 'agent_result') return `${evt.agent} 输出`
  if (evt.type === 'agent_call') return `调用 ${evt.agent}`
  return JSON.stringify(evt)
}

async function fetchList() {
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (keyword.value) params.keyword = keyword.value
    if (statusFilter.value) params.status = statusFilter.value
    if (appIdFilter.value) params.app_id = appIdFilter.value

    const res = await chatLogsApi.list(params)
    const data = res.data.data || {}
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    console.error('Failed to fetch chat logs:', e)
  } finally {
    loading.value = false
  }
}

// Also fetch apps for the filter dropdown
async function fetchApps() {
  try {
    const res = await appsApi.list()
    apps.value = res.data.data || []
  } catch {}
}

onMounted(() => {
  fetchList()
  fetchApps()
})
</script>

<style scoped>
:deep(.ant-table-row-expand-icon-cell) {
  display: none;
}
</style>
