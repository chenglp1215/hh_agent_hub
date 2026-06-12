<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">{{ isEdit ? '编辑' : '创建' }} 工作流</h1>
      <a-space>
        <a-button @click="$router.back()">取消</a-button>
        <a-button type="primary" @click="handleSave" :loading="saving">保存</a-button>
      </a-space>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- 基本信息 -->
      <a-card title="基本信息" class="lg:col-span-2">
        <a-form layout="vertical" class="max-w-lg">
          <a-form-item label="名称" required>
            <a-input v-model:value="name" placeholder="如：需求分析流水线" />
          </a-form-item>
          <a-form-item label="描述">
            <a-textarea v-model:value="description" :rows="2" placeholder="可选" />
          </a-form-item>
          <a-form-item label="工作流模式" required>
            <a-radio-group v-model:value="flowType" button-style="solid" @change="onModeChange">
              <a-radio-button value="sequential">顺序模式</a-radio-button>
              <a-radio-button value="supervisor">监督者模式</a-radio-button>
            </a-radio-group>
          </a-form-item>
        </a-form>
      </a-card>

      <!-- 顺序模式 -->
      <a-card v-if="flowType === 'sequential'" title="Agent 执行顺序" class="lg:col-span-2">
        <div class="mb-4 flex gap-4 items-end">
          <a-form-item label="添加 Agent" class="flex-1 mb-0">
            <a-select
              v-model:value="selectedAgent"
              placeholder="选择要加入的 Agent..."
              :options="availableAgentOptions"
              show-search
              filter-option
              @change="addAgent"
            />
          </a-form-item>
        </div>

        <div v-if="orderedAgents.length === 0" class="text-gray-400 text-center py-8">
          尚未添加 Agent，从上方选择添加
        </div>

        <div v-else class="space-y-2">
          <div
            v-for="(agent, idx) in orderedAgents"
            :key="agent.id"
            class="flex items-center gap-3 p-3 bg-[#1a1a1c] border border-[#1e1e20] rounded"
          >
            <span class="text-sm text-gray-500 w-6 text-center font-mono">{{ idx + 1 }}</span>
            <div class="flex-1">
              <div class="font-medium">{{ agent.display_name || agent.name }}</div>
              <div class="text-xs text-gray-500">{{ agentTypeLabel(agent.agent_type) }}</div>
            </div>
            <a-button size="small" :disabled="idx === 0" @click="moveUp(idx)">
              <template #icon><ArrowUpOutlined /></template>
            </a-button>
            <a-button size="small" :disabled="idx === orderedAgents.length - 1" @click="moveDown(idx)">
              <template #icon><ArrowDownOutlined /></template>
            </a-button>
            <a-button size="small" danger @click="removeAgent(idx)">
              <template #icon><DeleteOutlined /></template>
            </a-button>
          </div>
        </div>
      </a-card>

      <!-- 监督者模式 -->
      <template v-if="flowType === 'supervisor'">
        <a-card title="主管 Agent" class="lg:col-span-2">
          <a-form-item label="选择主管" required>
            <a-select
              v-model:value="supervisorAgentId"
              placeholder="选择监督者 Agent..."
              :options="availableAgentOptions"
              show-search
              filter-option
              allow-clear
            />
          </a-form-item>
          <a-divider />
          <a-button size="small" @click="showCreateSupervisor = true">
            <PlusOutlined /> 快捷创建新主管 Agent
          </a-button>
        </a-card>

        <a-card title="工作者 Agent" class="lg:col-span-2">
          <a-form-item label="选择工作者">
            <a-select
              v-model:value="workerIds"
              mode="multiple"
              placeholder="选择多个工作者 Agent..."
              :options="availableAgentOptions"
              show-search
              filter-option
              class="w-full"
            />
          </a-form-item>
          <div v-if="workerIds.length > 0" class="mt-4">
            <div class="text-sm text-gray-400 mb-2">已选 {{ workerIds.length }} 个工作者：</div>
            <a-space wrap>
              <a-tag
                v-for="wid in workerIds"
                :key="wid"
                closable
                @close="removeWorker(wid)"
              >
                {{ getAgentName(wid) }}
              </a-tag>
            </a-space>
          </div>
        </a-card>
      </template>

      <!-- 高级设置 -->
      <a-card title="高级设置" class="lg:col-span-2">
        <a-form layout="vertical" class="max-w-lg">
          <a-form-item label="错误策略">
            <a-radio-group v-model:value="errorStrategy" button-style="solid">
              <a-radio-button value="fail_fast">快速失败</a-radio-button>
              <a-radio-button value="skip_continue">跳过继续</a-radio-button>
            </a-radio-group>
          </a-form-item>
          <a-form-item label="Agent 超时(秒)">
            <a-input-number v-model:value="agentTimeout" :min="5" :max="600" />
          </a-form-item>
          <a-form-item label="工作流超时(秒)">
            <a-input-number v-model:value="workflowTimeout" :min="10" :max="3600" />
          </a-form-item>
        </a-form>
      </a-card>
    </div>

    <!-- 快捷创建主管 Agent 的抽屉 -->
    <a-drawer
      title="快捷创建主管 Agent"
      :open="showCreateSupervisor"
      @close="showCreateSupervisor = false"
      :width="480"
    >
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="quickAgentName" placeholder="如 supervisor-main" />
        </a-form-item>
        <a-form-item label="显示名称">
          <a-input v-model:value="quickAgentDisplayName" placeholder="如 主管Agent" />
        </a-form-item>
        <a-form-item label="模型">
          <a-select v-model:value="quickAgentModel" placeholder="选择LLM模型">
            <a-select-option value="gpt-4o-mini">GPT-4o-mini</a-select-option>
            <a-select-option value="gpt-4o">GPT-4o</a-select-option>
            <a-select-option value="claude-3-haiku">Claude Haiku</a-select-option>
            <a-select-option value="claude-3-sonnet">Claude Sonnet</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="系统提示">
          <a-textarea v-model:value="quickAgentPrompt" :rows="4" placeholder="你是一个工作流主管..." />
        </a-form-item>
        <a-button type="primary" block :loading="creatingAgent" @click="handleCreateSupervisor">
          创建并选用
        </a-button>
      </a-form>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, ArrowUpOutlined, ArrowDownOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { workflowsApi } from '@/api/workflows'
import { agentsApi } from '@/api/agents'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const saving = ref(false)

// --- 基本信息 ---
const name = ref('')
const description = ref('')
const flowType = ref('sequential')
const errorStrategy = ref('fail_fast')
const agentTimeout = ref(60)
const workflowTimeout = ref(300)

// --- Agent 列表 ---
const agents = ref<any[]>([])
const availableAgentOptions = computed(() =>
  agents.value.map(a => ({ value: a.id, label: a.display_name || a.name }))
)

function agentTypeLabel(type: string) {
  const map: Record<string, string> = { local: '本地 ReAct', http: 'HTTP 远程', claudecode: 'Claude Code' }
  return map[type] || type
}

// --- 顺序模式 ---
const selectedAgent = ref<number | null>(null)
const orderedAgents = ref<any[]>([])

function addAgent(id: number) {
  if (!id) return
  if (orderedAgents.value.some(a => a.id === id)) {
    message.warning('该 Agent 已在列表中')
    selectedAgent.value = null
    return
  }
  const agent = agents.value.find(a => a.id === id)
  if (agent) orderedAgents.value.push(agent)
  selectedAgent.value = null
}

function removeAgent(idx: number) { orderedAgents.value.splice(idx, 1) }
function moveUp(idx: number) {
  if (idx === 0) return
  const arr = orderedAgents.value
  ;[arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]]
}
function moveDown(idx: number) {
  if (idx === orderedAgents.value.length - 1) return
  const arr = orderedAgents.value
  ;[arr[idx], arr[idx + 1]] = [arr[idx + 1], arr[idx]]
}

// --- 监督者模式 ---
const supervisorAgentId = ref<number | null>(null)
const workerIds = ref<number[]>([])

function removeWorker(id: number) { workerIds.value = workerIds.value.filter(w => w !== id) }
function getAgentName(id: number) {
  return agents.value.find(a => a.id === id)?.display_name || agents.value.find(a => a.id === id)?.name || `#${id}`
}

function onModeChange() {
  orderedAgents.value = []
  supervisorAgentId.value = null
  workerIds.value = []
}

// --- 快捷创建主管 Agent ---
const showCreateSupervisor = ref(false)
const creatingAgent = ref(false)
const quickAgentName = ref('')
const quickAgentDisplayName = ref('')
const quickAgentModel = ref('gpt-4o-mini')
const quickAgentPrompt = ref('')

async function handleCreateSupervisor() {
  if (!quickAgentName.value) {
    message.warning('请输入名称')
    return
  }
  creatingAgent.value = true
  try {
    const res = await agentsApi.create({
      name: quickAgentName.value,
      display_name: quickAgentDisplayName.value || quickAgentName.value,
      agent_type: 'local',
      role: 'supervisor',
      system_prompt: quickAgentPrompt.value,
      llm_config: { provider: quickAgentModel.value.startsWith('claude') ? 'anthropic' : 'openai', model: quickAgentModel.value, temperature: 0.3 },
    })
    supervisorAgentId.value = res.data.data.id
    showCreateSupervisor.value = false
    message.success('主管 Agent 已创建')
    // 刷新 Agent 列表
    const listRes = await agentsApi.list({ status: 'active' })
    agents.value = listRes.data.data || []
  } catch (e: any) {
    message.error(e.response?.data?.message || '创建失败')
  } finally {
    creatingAgent.value = false
  }
}

// --- 保存 ---
async function handleSave() {
  if (!name.value.trim()) { message.warning('请输入工作流名称'); return }

  saving.value = true
  try {
    const data: Record<string, any> = {
      name: name.value.trim(),
      description: description.value,
      flow_type: flowType.value,
      error_strategy: errorStrategy.value,
      agent_timeout_seconds: agentTimeout.value,
      workflow_timeout_seconds: workflowTimeout.value,
    }

    if (flowType.value === 'sequential') {
      data.worker_agent_ids = orderedAgents.value.map(a => a.id)
    } else {
      data.supervisor_agent_id = supervisorAgentId.value
      data.worker_agent_ids = workerIds.value
    }

    if (isEdit.value) {
      await workflowsApi.update(Number(route.params.id), data)
    } else {
      await workflowsApi.create(data)
    }
    message.success('保存成功')
    router.push('/workflows')
  } catch (e: any) {
    message.error(e.response?.data?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// --- 加载 ---
onMounted(async () => {
  try {
    const res = await agentsApi.list({ status: 'active' })
    agents.value = res.data.data || []
  } catch { /* optional */ }

  if (isEdit.value) {
    try {
      const res = await workflowsApi.get(Number(route.params.id))
      const w = res.data.data
      name.value = w.name
      description.value = w.description || ''
      flowType.value = w.flow_type
      errorStrategy.value = w.error_strategy || 'fail_fast'
      agentTimeout.value = w.agent_timeout_seconds || 60
      workflowTimeout.value = w.workflow_timeout_seconds || 300

      if (w.flow_type === 'supervisor') {
        supervisorAgentId.value = w.supervisor_agent_id
        workerIds.value = w.worker_agent_ids || []
      } else {
        // 顺序模式：按 worker_agent_ids 顺序重建列表
        const ids = w.worker_agent_ids || []
        orderedAgents.value = ids.map((id: number) => agents.value.find(a => a.id === id) || { id, name: `#${id}` })
      }
    } catch {
      message.error('加载工作流失败')
    }
  }
})
</script>
