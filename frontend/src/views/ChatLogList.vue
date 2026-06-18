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
    <a-drawer
      v-model:open="drawerOpen"
      :title="'对话详情 #' + detailId"
      placement="right"
      width="640"
    >
      <template v-if="detail">
        <div class="space-y-4">
          <div>
            <h3 class="text-sm font-semibold text-gray-400 mb-1">用户问题</h3>
            <div class="bg-gray-900 rounded-lg p-3 text-sm whitespace-pre-wrap">{{ detail.user_input }}</div>
          </div>
          <div>
            <h3 class="text-sm font-semibold text-gray-400 mb-1">回复内容</h3>
            <div class="bg-gray-900 rounded-lg p-3 text-sm whitespace-pre-wrap">{{ detail.final_answer || '(无)' }}</div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <span class="text-xs text-gray-500">耗时</span>
              <div class="text-sm font-mono">{{ formatDuration(detail.duration_ms) }}</div>
            </div>
            <div>
              <span class="text-xs text-gray-500">Agent 数</span>
              <div class="text-sm">{{ detail.agent_count }}</div>
            </div>
            <div>
              <span class="text-xs text-gray-500">状态</span>
              <a-tag :color="detail.status === 'success' ? 'green' : 'red'">
                {{ detail.status === 'success' ? '成功' : '失败' }}
              </a-tag>
            </div>
            <div>
              <span class="text-xs text-gray-500">时间</span>
              <div class="text-sm">{{ formatTime(detail.created_at) }}</div>
            </div>
          </div>
          <div v-if="detail.error_message">
            <h3 class="text-sm font-semibold text-red-400 mb-1">错误信息</h3>
            <div class="bg-red-900/30 rounded-lg p-3 text-sm text-red-300">{{ detail.error_message }}</div>
          </div>
          <div v-if="detail.trace_summary && detail.trace_summary.length">
            <h3 class="text-sm font-semibold text-gray-400 mb-1">执行追踪</h3>
            <div class="bg-gray-900 rounded-lg p-3 space-y-1">
              <div v-for="(evt, i) in detail.trace_summary" :key="i"
                   class="flex items-center gap-2 text-xs font-mono py-0.5">
                <span class="text-gray-500 w-4">#{{ i + 1 }}</span>
                <a-tag :color="traceTagColor(evt.type)" class="!text-xs !px-1.5 !py-0 !min-w-0 !leading-5">
                  {{ traceTagLabel(evt.type) }}
                </a-tag>
                <span class="text-gray-300">{{ traceEventText(evt) }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </a-drawer>
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

// Drawer detail
const drawerOpen = ref(false)
const detailId = ref(0)
const detail = ref<ChatLogItem | null>(null)

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
  return trace.length
    ? trace.map((evt: any, i: number) =>
        `<div class="flex items-center gap-2 text-xs font-mono py-0.5">
          <span class="text-gray-500 w-4">#${i + 1}</span>
          <span class="${traceTagClass(evt.type)} px-1.5 py-0.5 rounded text-xs">${traceTagLabel(evt.type)}</span>
          <span class="text-gray-300">${traceEventText(evt)}</span>
        </div>`
      ).join('')
    : '<span class="text-gray-500 text-xs">无追踪信息</span>'
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
  const colors: Record<string, string> = {
    supervisor_start: 'bg-blue-500/20 text-blue-300',
    supervisor_route: 'bg-purple-500/20 text-purple-300',
    supervisor_end: 'bg-gray-500/20 text-gray-400',
    supervisor_greeting_shortcut: 'bg-green-500/20 text-green-300',
    supervisor_force_end: 'bg-red-500/20 text-red-300',
    agent_start: 'bg-cyan-500/20 text-cyan-300',
    agent_end: 'bg-geekblue-500/20 text-geekblue-300',
  }
  return colors[type] || 'bg-gray-500/20 text-gray-400'
}

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

// 打开抽屉查看详情
async function openDetail(id: number) {
  detailId.value = id
  drawerOpen.value = true
  try {
    const res = await chatLogsApi.get(id)
    detail.value = res.data.data || null
  } catch {
    detail.value = null
  }
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
