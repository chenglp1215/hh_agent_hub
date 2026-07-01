<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">应用管理</h1>
      <a-button type="primary" @click="$router.push('/apps/create')"><PlusOutlined /> 创建应用</a-button>
    </div>

    <div class="mb-4">
      <a-input-search v-model:value="search" placeholder="搜索应用名称..." class="max-w-xs" allow-clear />
    </div>

    <a-spin :spinning="loading">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
        <a-card v-for="app in filteredApps" :key="app.id" class="hover:border-[#5e6ad2] transition-colors">
          <!-- Header: status + name + API doc -->
          <div class="flex items-start justify-between mb-2">
            <div class="flex items-center gap-2 min-w-0 flex-1">
              <a-tooltip :title="app.enabled ? '启用' : '禁用'">
                <span class="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0" :class="app.enabled ? 'bg-green-500' : 'bg-red-500'" />
              </a-tooltip>
              <h3 class="text-lg font-semibold truncate">{{ app.name }}</h3>
            </div>
            <a-button size="small" type="link" @click="openApiDoc(app)">API 文档</a-button>
          </div>

          <!-- Description -->
          <p class="text-gray-400 text-sm mb-3 truncate">{{ app.description || '暂无描述' }}</p>

          <!-- Info grid -->
          <div class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm mb-3">
            <div>
              <span class="text-gray-500">工作流：</span>
              <span class="text-gray-300">{{ app.workflow_name || '-' }}</span>
            </div>
            <div>
              <span class="text-gray-500">限流：</span>
              <span class="text-gray-300">{{ app.rate_limit }} 次/分</span>
            </div>
            <div class="col-span-2 flex items-center gap-1">
              <span class="text-gray-500">API Key：</span>
              <code class="text-xs px-1 rounded" style="background: #1a1a1c; color: #5e6ad2">{{ app.api_key }}</code>
              <a-button size="small" type="link" @click="copyKey(app.api_key)">复制</a-button>
            </div>
          </div>

          <!-- Expandable: workflow agents -->
          <div
            class="cursor-pointer flex items-center justify-center py-1 mt-1 transition-colors"
            :class="expandedApps.has(app.id) ? 'text-[#00d4ff]' : 'text-gray-500 hover:text-gray-300'"
            @click="toggleExpand(app)"
          >
            <DownOutlined class="text-lg transition-transform" :class="{ 'rotate-180': expandedApps.has(app.id) }" />
            <a-spin v-if="expandingApps.has(app.id)" size="small" class="ml-2" />
          </div>

          <template v-if="expandedApps.has(app.id)">
            <div v-if="workflowData[app.workflow_id]" class="border-t border-gray-700/50 pt-3 mt-1">
              <!-- Workflow type badge -->
              <div class="flex items-center gap-2 mb-3">
                <a-tag :color="flowTypeColor(workflowData[app.workflow_id].flow_type)">
                  {{ flowTypeLabel(workflowData[app.workflow_id].flow_type) }}
                </a-tag>
                <span class="text-gray-500 text-xs">v{{ workflowData[app.workflow_id].version }}</span>
              </div>

              <!-- Agent list -->
              <div class="space-y-2">
                <!-- Supervisor -->
                <div
                  v-if="agentMap[workflowData[app.workflow_id].supervisor_agent_id]"
                  class="flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors"
                  style="background: rgba(94, 106, 210, 0.08)"
                  @click="openAgentEdit(workflowData[app.workflow_id].supervisor_agent_id)"
                >
                  <span class="inline-block w-2 h-2 rounded-full bg-purple-500 flex-shrink-0" />
                  <div class="flex-1 min-w-0">
                    <span class="text-sm font-medium">{{ agentMap[workflowData[app.workflow_id].supervisor_agent_id].display_name || agentMap[workflowData[app.workflow_id].supervisor_agent_id].name }}</span>
                    <a-tag class="ml-2" color="purple" size="small">Supervisor</a-tag>
                  </div>
                  <span class="text-xs text-gray-500">{{ agentMap[workflowData[app.workflow_id].supervisor_agent_id].agent_type }}</span>
                </div>

                <!-- Workers -->
                <div
                  v-for="agentId in workflowData[app.workflow_id].worker_agent_ids"
                  :key="agentId"
                  class="flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors hover:bg-white/5"
                  @click="openAgentEdit(agentId)"
                >
                  <span class="inline-block w-2 h-2 rounded-full flex-shrink-0" :class="agentStatusColor(agentId)" />
                  <div class="flex-1 min-w-0">
                    <span class="text-sm font-medium">{{ agentMap[agentId]?.display_name || agentMap[agentId]?.name || `Agent #${agentId}` }}</span>
                    <a-tag class="ml-2" color="blue" size="small">Worker</a-tag>
                  </div>
                  <span class="text-xs text-gray-500">{{ agentMap[agentId]?.agent_type || '-' }}</span>
                </div>

                <a-empty v-if="!workflowData[app.workflow_id].supervisor_agent_id && workflowData[app.workflow_id].worker_agent_ids.length === 0" :image="null" description="暂无 Agent" />
              </div>

              <!-- Triggers -->
              <div v-if="triggersForApp(app.id).length > 0" class="mt-3 pt-3 border-t border-gray-700/50">
                <p class="text-gray-500 text-xs mb-2">关联触发器 ({{ triggersForApp(app.id).length }})</p>
                <div class="space-y-1">
                  <div
                    v-for="t in triggersForApp(app.id)"
                    :key="t.id"
                    class="flex items-center gap-2 px-2 py-1.5 rounded text-sm"
                  >
                    <span class="inline-block w-1.5 h-1.5 rounded-full flex-shrink-0" :class="t.enabled ? 'bg-green-500' : 'bg-gray-500'" />
                    <span class="font-medium truncate flex-1">{{ t.name }}</span>
                    <a-tag :color="triggerTypeColor(t.trigger_type)" size="small">{{ triggerTypeLabel(t.trigger_type) }}</a-tag>
                    <span class="text-xs text-gray-500">{{ triggerSchedule(t) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <!-- Card actions -->
          <template #actions>
            <a-button size="small" @click="$router.push(`/apps/${app.id}/edit`)">编辑</a-button>
            <a-button size="small" @click="handleRotate(app.id)">轮换密钥</a-button>
            <a-popconfirm title="确定删除？" @confirm="handleDelete(app.id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </a-card>
      </div>
      <a-empty v-if="!loading && filteredApps.length === 0" description="暂无应用" />
    </a-spin>

    <!-- Agent Edit Modal -->
    <AgentEditModal
      v-model:open="agentModalOpen"
      :agent-id="editingAgentId"
      @saved="onAgentSaved"
    />

    <!-- API 文档弹窗 -->
    <a-modal v-model:open="apiDocOpen" title="API 文档 - 触发应用对话" :footer="null" width="680px">
      <template v-if="selectedApp">
        <div class="mb-4">
          <h4 class="text-base font-semibold mb-2 text-white">应用信息</h4>
          <div class="text-sm" style="color: #c0c4cc">
            <span>名称：{{ selectedApp.name }}</span>
            <span class="ml-6">API Key：<code class="px-1 rounded text-xs" style="background: #1a1a1c; color: #5e6ad2">{{ selectedApp.api_key }}</code></span>
          </div>
        </div>
        <a-divider />
        <div class="mb-4">
          <h4 class="text-base font-semibold mb-2">接口信息</h4>
          <a-descriptions :column="1" size="small" bordered>
            <a-descriptions-item label="请求方式"><a-tag color="green">POST</a-tag></a-descriptions-item>
            <a-descriptions-item label="接口路径"><code>/api/v1/chat</code></a-descriptions-item>
            <a-descriptions-item label="认证方式"><code>X-API-Key</code> 请求头 或 <code>Authorization: Bearer &lt;key&gt;</code></a-descriptions-item>
            <a-descriptions-item label="Content-Type"><code>application/json</code></a-descriptions-item>
            <a-descriptions-item label="流式响应">设置 <code>stream: true</code> 启用 SSE 流式输出</a-descriptions-item>
          </a-descriptions>
        </div>
        <a-divider />
        <div class="mb-4">
          <h4 class="text-base font-semibold mb-2">请求参数</h4>
          <a-table :dataSource="paramColumns" :columns="apiParamTableColumns" rowKey="name" size="small" :pagination="false" bordered />
        </div>
        <a-divider />
        <div class="mb-4">
          <h4 class="text-base font-semibold mb-2">响应字段（非流式）</h4>
          <a-table :dataSource="responseFields" :columns="apiParamTableColumns" rowKey="name" size="small" :pagination="false" bordered />
        </div>
        <a-divider />
        <div class="mb-4">
          <h4 class="text-base font-semibold mb-2">请求示例</h4>
          <div class="relative">
            <a-button size="small" class="absolute top-2 right-2 z-10" @click="copyExample(selectedApp.api_key)">复制</a-button>
            <pre class="bg-gray-900 text-green-400 p-4 rounded text-xs overflow-x-auto"><code>{{ buildCurlExample(selectedApp.api_key) }}</code></pre>
          </div>
        </div>
        <a-divider />
        <div>
          <h4 class="text-base font-semibold mb-2">响应示例（非流式）</h4>
          <pre class="bg-gray-900 text-green-400 p-4 rounded text-xs overflow-x-auto"><code>{
  "code": 0,
  "message": "success",
  "data": {
    "session_id": "uuid-string",
    "message": "这是 AI 返回的回复内容...",
    "intermediate_results": {
      "AgentName": "该 Agent 的中间输出"
    },
    "duration_ms": 1234,
    "trace": [...]
  }
}</code></pre>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, DownOutlined } from '@ant-design/icons-vue'
import { appsApi } from '@/api/apps'
import { workflowsApi } from '@/api/workflows'
import { agentsApi } from '@/api/agents'
import { triggersApi } from '@/api/triggers'
import AgentEditModal from '@/components/AgentEditModal.vue'

const apps = ref<any[]>([])
const allTriggers = ref<any[]>([])
const loading = ref(false)
const search = ref('')

// Expand state
const expandedApps = ref(new Set<number>())
const expandingApps = ref(new Set<number>())
const workflowData = ref<Record<number, any>>({})
const agentMap = ref<Record<number, any>>({})

// Agent edit modal
const agentModalOpen = ref(false)
const editingAgentId = ref<number | null>(null)

// API doc modal
const apiDocOpen = ref(false)
const selectedApp = ref<any>(null)

const filteredApps = computed(() => {
  if (!search.value) return apps.value
  const q = search.value.toLowerCase()
  return apps.value.filter(a => a.name.toLowerCase().includes(q))
})

async function fetchList() {
  loading.value = true
  try {
    const res = await appsApi.list()
    apps.value = res.data.data || []
  } finally {
    loading.value = false
  }
}

async function toggleExpand(app: any) {
  if (expandedApps.value.has(app.id)) {
    expandedApps.value.delete(app.id)
    expandedApps.value = new Set(expandedApps.value)
    return
  }

  expandedApps.value.add(app.id)
  expandedApps.value = new Set(expandedApps.value)

  // Load workflow + agents if not cached
  if (!workflowData.value[app.workflow_id]) {
    expandingApps.value.add(app.id)
    expandingApps.value = new Set(expandingApps.value)
    try {
      const wfRes = await workflowsApi.get(app.workflow_id)
      const wf = wfRes.data.data
      workflowData.value[app.workflow_id] = wf

      // Fetch all agents in parallel
      const agentIds = [wf.supervisor_agent_id, ...wf.worker_agent_ids].filter(Boolean)
      const results = await Promise.allSettled(agentIds.map((id: number) => agentsApi.get(id)))
      for (const r of results) {
        if (r.status === 'fulfilled') {
          const agent = r.value.data.data
          agentMap.value[agent.id] = agent
        }
      }
    } catch {
      message.error('加载工作流详情失败')
    } finally {
      expandingApps.value.delete(app.id)
      expandingApps.value = new Set(expandingApps.value)
    }
  }
}

function openAgentEdit(agentId: number) {
  editingAgentId.value = agentId
  agentModalOpen.value = true
}

async function onAgentSaved() {
  // Refresh the agent data in cache
  if (editingAgentId.value) {
    try {
      const res = await agentsApi.get(editingAgentId.value)
      agentMap.value[editingAgentId.value] = res.data.data
    } catch { /* ignore */ }
  }
}

function agentStatusColor(agentId: number) {
  const agent = agentMap.value[agentId]
  if (!agent) return 'bg-gray-500'
  return agent.status === 'active' ? 'bg-green-500' : 'bg-red-500'
}

function flowTypeLabel(type: string) {
  const map: Record<string, string> = { supervisor: 'Supervisor 模式', sequential: '顺序执行', graph: '自定义图' }
  return map[type] || type
}

function flowTypeColor(type: string) {
  const map: Record<string, string> = { supervisor: 'purple', sequential: 'blue', graph: 'cyan' }
  return map[type] || 'default'
}

function triggersForApp(appId: number) {
  return allTriggers.value.filter(t => t.app_id === appId)
}

function triggerTypeLabel(type: string) {
  const map: Record<string, string> = { interval: '定时触发', cron: 'Cron 触发', wecom_bot: '企微机器人' }
  return map[type] || type
}

function triggerTypeColor(type: string) {
  const map: Record<string, string> = { interval: 'blue', cron: 'cyan', wecom_bot: 'green' }
  return map[type] || 'default'
}

function triggerSchedule(t: any) {
  if (t.trigger_type === 'interval') return `每 ${t.interval_value} ${t.interval_unit === 'minutes' ? '分钟' : t.interval_unit === 'hours' ? '小时' : '天'}`
  if (t.trigger_type === 'cron') return t.cron_expression
  if (t.trigger_type === 'wecom_bot') return t.wecom_chat_type === 'group' ? `群聊: ${t.wecom_chat_id}` : `用户: ${t.wecom_user_id}`
  return '-'
}

function copyKey(key: string) {
  navigator.clipboard.writeText(key)
  message.success('已复制到剪贴板')
}

async function handleRotate(id: number) {
  const res = await appsApi.rotateKey(id)
  message.success('密钥已轮换: ' + res.data.data.api_key)
  fetchList()
}

async function handleDelete(id: number) {
  await appsApi.delete(id)
  message.success('已删除')
  fetchList()
}

function openApiDoc(app: any) {
  selectedApp.value = app
  apiDocOpen.value = true
}

function buildCurlExample(apiKey: string) {
  return `curl -X POST "${window.location.origin}/api/v1/chat" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ${apiKey}" \\
  -d '{
    "app_id": ${selectedApp.value?.id},
    "message": "你好，请帮我...",
    "stream": false
  }'`
}

function copyExample(apiKey: string) {
  navigator.clipboard.writeText(buildCurlExample(apiKey))
  message.success('已复制到剪贴板')
}

const paramColumns = [
  { name: 'app_id', type: 'int', required: '是', description: '应用的 ID（与 API Key 二选一认证）' },
  { name: 'message', type: 'string', required: '是', description: '用户发送的消息内容' },
  { name: 'session_id', type: 'string (UUID)', required: '否', description: '会话 ID，不传则自动创建新会话' },
  { name: 'stream', type: 'boolean', required: '否', description: '是否启用 SSE 流式响应，默认 false' },
]

const responseFields = [
  { name: 'code', type: 'int', required: '-', description: '状态码，0 表示成功' },
  { name: 'message', type: 'string', required: '-', description: '状态描述' },
  { name: 'data.session_id', type: 'string', required: '-', description: '会话 ID，可用于后续查询历史' },
  { name: 'data.message', type: 'string', required: '-', description: 'AI 最终回复内容' },
  { name: 'data.intermediate_results', type: 'object', required: '-', description: '各 Agent 中间输出，key 为 Agent 名称' },
  { name: 'data.duration_ms', type: 'int', required: '-', description: '执行耗时（毫秒）' },
  { name: 'data.trace', type: 'array', required: '-', description: '执行追踪链路' },
]

const apiParamTableColumns = [
  { title: '字段名', dataIndex: 'name', key: 'name', width: 160 },
  { title: '类型', dataIndex: 'type', key: 'type', width: 120 },
  { title: '必填', dataIndex: 'required', key: 'required', width: 60 },
  { title: '说明', dataIndex: 'description', key: 'description' },
]

onMounted(async () => {
  await fetchList()
  try {
    const res = await triggersApi.list()
    allTriggers.value = res.data.data || []
  } catch { /* ignore */ }
})
</script>
