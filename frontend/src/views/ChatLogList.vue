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
      @expand="onExpand"
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
          <span class="text-sm">{{ record.user_input }}</span>
        </template>
        <template v-if="column.key === 'final_answer'">
          <span class="text-sm text-[#8892a4] truncate max-w-[250px] inline-block">
            {{ (record.final_answer || '').slice(0, 80) }}{{ (record.final_answer || '').length > 80 ? '...' : '' }}
          </span>
        </template>
        <template v-if="column.key === 'created_at'">
          {{ fmtTime(record.created_at) }}
        </template>
        <template v-if="column.key === 'actions'">
          <a-button
            size="small"
            type="link"
            @click="continueChat(record)"
            :disabled="!record.app_id || !record.session_id"
          >
            继续对话
          </a-button>
        </template>
      </template>

      <!-- Expanded row -->
      <template #expandedRowRender="{ record }">
        <div v-if="expandedId === record.id" class="expanded-panel">
          <a-spin v-if="loadingSession" size="small" class="flex justify-center py-4" />
          <template v-else>
            <!-- Q&A -->
            <div class="mb-3">
              <div class="exp-label">用户问题</div>
              <div class="exp-bubble exp-bubble--user">{{ record.user_input }}</div>
            </div>
            <div class="mb-3">
              <div class="exp-label">最终回复</div>
              <div class="exp-bubble exp-bubble--assistant">
                {{ record.final_answer || '(空)' }}
              </div>
            </div>

            <!-- Session history -->
            <div v-if="sessionMessages.length > 0" class="mb-3">
              <div class="exp-label">会话历史 ({{ sessionMessages.length }} 条)</div>
              <div class="exp-session">
                <div
                  v-for="(msg, i) in sessionMessages"
                  :key="i"
                  class="exp-msg"
                  :class="msg.role === 'user' ? 'exp-msg--user' : 'exp-msg--bot'"
                >
                  <span class="exp-msg-role">{{ msg.role === 'user' ? 'U' : 'A' }}</span>
                  <span class="exp-msg-text">{{ msg.content }}</span>
                </div>
              </div>
            </div>

            <!-- Trace -->
            <div>
              <div class="exp-label">执行追踪</div>
              <div v-if="traceList.length > 0" class="exp-trace">
                <div v-for="(evt, i) in traceList" :key="i" class="exp-trace-item">
                  <span class="exp-trace-idx font-mono">#{{ i + 1 }}</span>
                  <span class="exp-trace-tag" :style="{ background: evt.color + '22', color: evt.color, borderColor: evt.color + '44' }">
                    {{ evt.label }}
                  </span>
                  <span class="exp-trace-text">{{ evt.text }}</span>
                </div>
              </div>
              <div v-else class="text-xs text-[#535b6e]">无追踪信息</div>
            </div>
          </template>
        </div>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { chatLogsApi } from '@/api/chatLogs'
import { appsApi } from '@/api/apps'
import client from '@/api/client'

const router = useRouter()

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

const expandedId = ref<number | null>(null)
const loadingSession = ref(false)
const sessionMessages = ref<any[]>([])

const tableColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '用户问题', key: 'user_input', width: 200 },
  { title: '回复', key: 'final_answer', ellipsis: true },
  { title: '耗时', key: 'duration', width: 80 },
  { title: '状态', key: 'status', width: 72 },
  { title: 'Agent 数', dataIndex: 'agent_count', key: 'agent_count', width: 72 },
  { title: '时间', key: 'created_at', width: 160 },
  { title: '', key: 'actions', width: 90 },
]

const traceList = ref<any[]>([])

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

function buildTraceList(trace: any[]): any[] {
  return (trace || []).map((evt: any) => {
    const type = evt.type || ''
    let text = ''
    if (type === 'supervisor_route') text = `→ ${evt.target || 'end'}`
    else if (type === 'supervisor_start') text = `第 ${evt.round} 轮`
    else if (type === 'agent_start') text = `${evt.agent} 执行`
    else if (type === 'agent_end') text = `${evt.agent} 完成 (${fmtDuration(evt.elapsed_ms)})`
    else if (type === 'agent_result') text = `${evt.agent} 输出`
    else if (type === 'agent_call') text = `调用 ${evt.agent}`
    else text = evt.content || ''
    return {
      label: TRACE_LABELS[type] || type,
      color: TRACE_COLORS[type] || '#6b7280',
      text,
    }
  })
}

async function onExpand(expanded: boolean, record: LogItem) {
  if (!expanded) { expandedId.value = null; return }
  expandedId.value = record.id
  traceList.value = buildTraceList(record.trace_summary || [])

  // Load session messages
  if (record.session_id) {
    loadingSession.value = true
    try {
      const res = await client.get(`/chat/sessions/${record.session_id}`)
      sessionMessages.value = res.data.data?.messages || []
    } catch { sessionMessages.value = [] }
    finally { loadingSession.value = false }
  } else {
    sessionMessages.value = []
  }
}

function continueChat(record: LogItem) {
  if (!record.app_id || !record.session_id) return
  router.push(`/monitor/chat-test?app_id=${record.app_id}&session_id=${record.session_id}`)
}

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
.expanded-panel {
  padding: 16px 20px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 10px;
  max-height: 500px;
  overflow-y: auto;
}
.exp-label {
  font-size: 11px;
  font-weight: 600;
  color: #535b6e;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 6px;
}
.exp-bubble {
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}
.exp-bubble--user {
  background: rgba(0, 180, 224, 0.1);
  border: 1px solid rgba(0, 180, 224, 0.2);
  color: #e4e7ee;
}
.exp-bubble--assistant {
  background: rgba(12, 16, 27, 0.6);
  border: 1px solid #1e2538;
  color: #e4e7ee;
}

/* Session messages */
.exp-session {
  max-height: 200px;
  overflow-y: auto;
  border-radius: 8px;
  border: 1px solid #1e2538;
}
.exp-msg {
  display: flex;
  gap: 8px;
  padding: 6px 10px;
  border-bottom: 1px solid #1e2538;
  font-size: 12px;
}
.exp-msg:last-child { border-bottom: none; }
.exp-msg--user { background: rgba(0, 180, 224, 0.04); }
.exp-msg--bot { background: transparent; }
.exp-msg-role {
  width: 20px;
  height: 20px;
  min-width: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
}
.exp-msg--user .exp-msg-role { background: #009fd4; }
.exp-msg--bot .exp-msg-role { background: #5b6abf; }
.exp-msg-text {
  flex: 1;
  color: #c0c5ce;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.4;
}

/* Trace */
.exp-trace {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.exp-trace-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  padding: 2px 0;
}
.exp-trace-idx { color: #535b6e; width: 22px; font-size: 10px; }
.exp-trace-tag {
  padding: 0 8px;
  border-radius: 4px;
  font-size: 11px;
  line-height: 22px;
  border: 1px solid;
}
.exp-trace-text { color: #8892a4; }
</style>
