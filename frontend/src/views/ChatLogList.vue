<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">对话日志</h1>
      <a-button @click="loadData" :loading="loading">
        <template #icon><ReloadOutlined /></template>
        刷新
      </a-button>
    </div>

    <!-- 筛选栏 -->
    <div class="mb-4 flex flex-wrap gap-3">
      <a-input-search
        v-model:value="searchText"
        placeholder="搜索用户问题..."
        class="max-w-xs"
        @search="loadData"
      />
      <a-select v-model:value="currentStatus" class="w-28" placeholder="状态" allow-clear @change="loadData">
        <a-select-option value="">全部状态</a-select-option>
        <a-select-option value="success">成功</a-select-option>
        <a-select-option value="error">失败</a-select-option>
      </a-select>
      <a-select v-model:value="currentAppId" class="w-40" placeholder="应用" allow-clear @change="loadData">
        <a-select-option :value="undefined">全部应用</a-select-option>
        <a-select-option v-for="app in appList" :key="app.id" :value="app.id">
          {{ app.name }}
        </a-select-option>
      </a-select>
    </div>

    <!-- 日志列表 -->
    <a-table
      :dataSource="logItems"
      :columns="tableColumns"
      rowKey="id"
      :loading="loading"
      :pagination="{
        current: currentPage, pageSize: currentSize, total: totalCount,
        showSizeChanger: true,
        showTotal: (t: number) => `共 ${t} 条`,
        onChange: (p: number, s: number) => { currentPage = p; currentSize = s; loadData(); },
      }"
      :expandable="{
        expandedRowRender: renderTrace,
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
          {{ fmtDuration(record.duration_ms) }}
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
          {{ fmtTime(record.created_at) }}
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { chatLogsApi } from '@/api/chatLogs'
import { appsApi } from '@/api/apps'

interface LogItem {
  id: number; app_id: number; session_id: string; task_id: string
  user_input: string; final_answer: string | null
  duration_ms: number | null; status: string; error_message: string | null
  agent_count: number; trace_summary: any[] | null; created_at: string | null
}

const loading = ref(false)
const logItems = ref<LogItem[]>([])
const totalCount = ref(0)
const currentPage = ref(1)
const currentSize = ref(20)

const searchText = ref('')
const currentStatus = ref('')
const currentAppId = ref<number | undefined>(undefined)
const appList = ref<any[]>([])

const tableColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '用户问题', key: 'user_input', width: 200, ellipsis: true },
  { title: '回复', key: 'final_answer', ellipsis: true },
  { title: '耗时', key: 'duration', width: 80 },
  { title: '状态', key: 'status', width: 72 },
  { title: 'Agent 数', dataIndex: 'agent_count', key: 'agent_count', width: 72 },
  { title: '时间', key: 'created_at', width: 160 },
]

function fmtDuration(ms: number | null): string {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const m = Math.floor(ms / 60000)
  const s = Math.floor((ms % 60000) / 1000)
  return `${m}m${s}s`
}

function fmtTime(t: string | null): string {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN', { hour12: false })
}

const TRACE_LABELS: Record<string, string> = {
  supervisor_start: '调度', supervisor_route: '路由', supervisor_end: '结束',
  supervisor_greeting_shortcut: '问候', supervisor_force_end: '强制结束',
  agent_start: '执行', agent_end: '完成', agent_result: '结果', agent_call: '调用',
}

const TRACE_COLORS: Record<string, string> = {
  supervisor_start: '#3b82f6', supervisor_route: '#8b5cf6', supervisor_end: '#6b7280',
  supervisor_greeting_shortcut: '#10b981', supervisor_force_end: '#ef4444',
  agent_start: '#06b6d4', agent_end: '#6366f1',
}

function renderTrace(record: LogItem): string {
  const trace = record.trace_summary || []
  if (!trace.length) return '<span class="text-gray-500 text-xs">无追踪信息</span>'

  return trace.map((evt: any, i: number) => {
    const type = evt.type || ''
    const label = TRACE_LABELS[type] || type
    const color = TRACE_COLORS[type] || '#6b7280'

    let text = ''
    if (type === 'supervisor_route') text = `→ ${evt.target || 'end'}`
    else if (type === 'supervisor_start') text = `第 ${evt.round} 轮调度`
    else if (type === 'supervisor_greeting_shortcut') text = '问候语直接回复'
    else if (type === 'agent_start') text = `${evt.agent} 开始执行`
    else if (type === 'agent_end') text = `${evt.agent} 完成 (${fmtDuration(evt.elapsed_ms)})`
    else if (type === 'supervisor_force_end') text = '已达最大轮次强制结束'
    else if (type === 'agent_result') text = `${evt.agent} 输出`
    else if (type === 'agent_call') text = `调用 ${evt.agent}`
    else text = JSON.stringify(evt)

    const inlineStyle = `background:${color}22;color:${color};border:1px solid ${color}44`
    return `<div class="flex items-center gap-2 text-xs font-mono py-0.5">
      <span class="text-gray-500 w-4">#${i + 1}</span>
      <span style="${inlineStyle}" class="px-1.5 py-0.5 rounded text-xs leading-5">${label}</span>
      <span class="text-gray-300">${text}</span>
    </div>`
  }).join('')
}

async function loadData() {
  loading.value = true
  try {
    const params: any = { page: currentPage.value, page_size: currentSize.value }
    if (searchText.value) params.keyword = searchText.value
    if (currentStatus.value) params.status = currentStatus.value
    if (currentAppId.value) params.app_id = currentAppId.value

    const res = await chatLogsApi.list(params)
    const d = res.data.data || {}
    logItems.value = d.items || []
    totalCount.value = d.total || 0
  } catch (e) {
    console.error('Failed to fetch chat logs:', e)
  } finally {
    loading.value = false
  }
}

async function loadApps() {
  try {
    const res = await appsApi.list()
    appList.value = res.data.data || []
  } catch { /* ignore */ }
}

onMounted(() => {
  loadData()
  loadApps()
})
</script>

<style scoped>
:deep(.ant-table-row-expand-icon-cell) {
  display: none;
}
</style>
