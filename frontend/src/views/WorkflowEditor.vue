<template>
  <div class="wf-editor">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4" style="animation: fade-in-down 0.4s var(--ease-out)">
      <div class="flex items-center gap-3">
        <div class="w-1 h-6 rounded-full"
          style="background: linear-gradient(180deg, #00d4ff, #007acc); box-shadow: 0 0 12px #00d4ff66;" />
        <h1 class="text-xl font-bold font-display text-[#e4e7ee] tracking-wider">
          {{ isEdit ? '编辑' : '创建' }} 工作流
        </h1>
      </div>
      <a-space>
        <a-button @click="$router.back()">取消</a-button>
        <a-button type="primary" @click="handleSave" :loading="saving">
          <SaveOutlined v-if="!saving" /> 保存
        </a-button>
      </a-space>
    </div>

    <div class="wf-layout">
      <!-- ==================== LEFT: Form Panel ==================== -->
      <div class="wf-form-panel glass" style="animation: slide-in-left 0.4s var(--ease-out)">
        <div class="form-scroll">
          <!-- Workflow name -->
          <div class="form-section">
            <div class="form-label">工作流名称</div>
            <a-input v-model:value="name" placeholder="如：需求分析流水线" size="large" />
          </div>
          <div class="form-section">
            <div class="form-label">描述</div>
            <a-textarea v-model:value="description" :rows="2" placeholder="可选描述" />
          </div>

          <!-- Flow type -->
          <div class="form-section">
            <div class="form-label">工作流模式</div>
            <a-radio-group v-model:value="flowType" button-style="solid" size="small" @change="onModeChange">
              <a-radio-button value="sequential">顺序模式</a-radio-button>
              <a-radio-button value="supervisor">监督者模式</a-radio-button>
            </a-radio-group>
          </div>

          <!-- Supervisor mode config -->
          <template v-if="flowType === 'supervisor'">
            <div class="form-section">
              <div class="form-label">主管 Agent</div>
              <a-select
                v-model:value="supervisorAgentId"
                placeholder="选择主管 Agent..."
                :options="supervisorOpts"
                show-search
                filter-option
                allow-clear
                size="large"
                @change="syncCanvas"
              />
              <a-button size="small" type="link" class="!p-0 !mt-1" @click="showCreateSupervisor = true">
                + 快捷创建主管
              </a-button>
            </div>

            <div class="form-section">
              <div class="form-label">
                工作者 Agent
                <span class="text-xs text-[#535b6e] ml-1">（已选 {{ workerIds.length }}）</span>
              </div>
              <a-select
                v-model:value="workerIds"
                mode="multiple"
                placeholder="选择工作者 Agent..."
                :options="workerOpts"
                show-search
                filter-option
                size="large"
                class="w-full"
                @change="syncCanvas"
              />
              <div v-if="workerIds.length > 0" class="mt-3">
                <a-space wrap>
                  <a-tag
                    v-for="wid in workerIds"
                    :key="wid"
                    closable
                    @close="removeWorker(wid)"
                    color="blue"
                  >
                    {{ getAgentName(wid) }}
                  </a-tag>
                </a-space>
              </div>
            </div>
          </template>

          <!-- Sequential mode config -->
          <template v-if="flowType === 'sequential'">
            <div class="form-section">
              <div class="form-label">Agent 执行顺序</div>
              <a-select
                v-model:value="selectedAgent"
                placeholder="选择要加入的 Agent..."
                :options="availableAgentOpts"
                show-search
                filter-option
                size="large"
                @change="addAgent"
              />
            </div>

            <div v-if="orderedAgents.length === 0" class="text-[#535b6e] text-xs text-center py-4">
              从上方选择添加 Agent
            </div>

            <div v-else class="agent-list">
              <div
                v-for="(agent, idx) in orderedAgents"
                :key="agent.id"
                class="agent-list-item"
              >
                <span class="agent-list-idx font-mono">{{ idx + 1 }}</span>
                <div class="flex-1 min-w-0">
                  <div class="text-xs font-medium text-[#e4e7ee] truncate">
                    {{ agent.display_name || agent.name }}
                  </div>
                  <div class="text-[10px] text-[#535b6e]">
                    {{ typeLabel(agent.agent_type) }} · {{ agent.role }}
                  </div>
                </div>
                <a-button size="small" :disabled="idx === 0" @click="moveUp(idx)">
                  <ArrowUpOutlined />
                </a-button>
                <a-button size="small" :disabled="idx === orderedAgents.length - 1" @click="moveDown(idx)">
                  <ArrowDownOutlined />
                </a-button>
                <a-button size="small" danger @click="removeAgent(idx)">
                  <DeleteOutlined />
                </a-button>
              </div>
            </div>
          </template>

          <!-- Advanced settings -->
          <div class="form-section">
            <div class="form-label">高级设置</div>
            <div class="flex items-center gap-3 mb-2">
              <span class="text-xs text-[#535b6e] w-16 shrink-0">错误策略</span>
              <a-radio-group v-model:value="errorStrategy" button-style="solid" size="small">
                <a-radio-button value="fail_fast">快速失败</a-radio-button>
                <a-radio-button value="skip_continue">跳过继续</a-radio-button>
              </a-radio-group>
            </div>
            <div class="flex items-center gap-3 mb-2">
              <span class="text-xs text-[#535b6e] w-16 shrink-0">Agent超时</span>
              <a-input-number v-model:value="agentTimeout" :min="5" :max="600" size="small" class="!w-20" />
              <span class="text-xs text-[#535b6e]">秒</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-xs text-[#535b6e] w-16 shrink-0">工作流超时</span>
              <a-input-number v-model:value="workflowTimeout" :min="10" :max="3600" size="small" class="!w-20" />
              <span class="text-xs text-[#535b6e]">秒</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ==================== RIGHT: Canvas Preview ==================== -->
      <div class="wf-canvas-panel glass" style="animation: scale-in 0.5s var(--ease-out)">
        <div class="canvas-toolbar">
          <a-space size="small">
            <span class="w-2 h-2 rounded-full bg-[#00e676]" style="box-shadow: 0 0 6px #00e676;" />
            <span class="text-xs text-[#8892a4]">画布预览</span>
            <a-divider type="vertical" />
            <span class="text-xs text-[#535b6e] font-mono">
              {{ agentNodeCount }} 个 Agent
            </span>
          </a-space>
          <a-space size="small">
            <a-button size="small" @click="fitView">
              <ExpandOutlined /> 适应
            </a-button>
          </a-space>
        </div>

        <VueFlow
          ref="vueFlowRef"
          v-model:nodes="canvasNodes"
          v-model:edges="canvasEdges"
          :node-types="nodeTypes"
          :default-edge-options="defaultEdgeOptions"
          :nodes-draggable="false"
          :nodes-connectable="false"
          :edges-updatable="false"
          :fit-view-on-init="true"
          class="flow-canvas"
        >
          <Background :gap="24" :size="1" pattern-color="#151a28" />
          <template #node-start="startProps">
            <TerminalNode :data="startProps.data" />
          </template>
          <template #node-agent="agentProps">
            <AgentNode :data="agentProps.data" :selected="false" />
          </template>
          <template #node-end="endProps">
            <TerminalNode :data="endProps.data" />
          </template>
        </VueFlow>
      </div>
    </div>

    <!-- Quick create supervisor drawer -->
    <a-drawer
      title="快捷创建主管 Agent"
      :open="showCreateSupervisor"
      @close="showCreateSupervisor = false"
      :width="440"
    >
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="quickAgentName" placeholder="supervisor-main" />
        </a-form-item>
        <a-form-item label="显示名称">
          <a-input v-model:value="quickAgentDisplayName" placeholder="主管Agent" />
        </a-form-item>
        <a-form-item label="LLM 配置" required>
          <a-select
            v-model:value="quickAgentLlmConfigId"
            placeholder="选择 LLM 配置..."
            :options="llmConfigOptions"
            show-search
            filter-option
          />
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
import { ref, computed, onMounted, markRaw, watch, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  SaveOutlined, ExpandOutlined, ArrowUpOutlined, ArrowDownOutlined, DeleteOutlined,
} from '@ant-design/icons-vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import type { Node, Edge, NodeTypesObject } from '@vue-flow/core'
import { workflowsApi } from '@/api/workflows'
import { agentsApi } from '@/api/agents'
import { llmConfigsApi } from '@/api/llmConfigs'
import AgentNode from '@/components/editor/AgentNode.vue'
import TerminalNode from '@/components/editor/TerminalNode.vue'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const saving = ref(false)
const vueFlowRef = ref()

// ---- Basic info ----
const name = ref('')
const description = ref('')
const flowType = ref('sequential')
const errorStrategy = ref('fail_fast')
const agentTimeout = ref(60)
const workflowTimeout = ref(300)

// ---- Agents ----
const agents = ref<any[]>([])
const supervisorAgentId = ref<number | null>(null)
const workerIds = ref<number[]>([])
const selectedAgent = ref<number | null>(null)
const orderedAgents = ref<any[]>([])

const supervisorOpts = computed(() =>
  agents.value.filter(a => a.role === 'supervisor').map(a => ({ value: Number(a.id), label: a.display_name || a.name }))
)
const workerOpts = computed(() =>
  agents.value.filter(a => a.role === 'worker').map(a => ({ value: Number(a.id), label: a.display_name || a.name }))
)
const availableAgentOpts = computed(() =>
  agents.value
    .filter(a => !orderedAgents.value.some(oa => oa.id === a.id))
    .map(a => ({ value: a.id, label: `${a.display_name || a.name} (${a.role})` }))
)

function typeLabel(t: string) {
  return { local: '本地', http: 'HTTP', a2a: 'A2A', claudecode: 'Claude Code' }[t] || t
}

function getAgentName(id: number) {
  return agents.value.find(a => a.id === id)?.display_name
    || agents.value.find(a => a.id === id)?.name || `#${id}`
}

// ---- Sequential: agent list management ----
function addAgent(id: number) {
  if (!id) return
  if (orderedAgents.value.some(a => a.id === id)) { message.warning('已在列表中'); selectedAgent.value = null; return }
  const agent = agents.value.find(a => a.id === id)
  if (agent) orderedAgents.value.push(agent)
  selectedAgent.value = null
  syncCanvas()
}

function removeAgent(idx: number) { orderedAgents.value.splice(idx, 1); syncCanvas() }
function moveUp(idx: number) {
  if (idx === 0) return
  const arr = orderedAgents.value; [arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]]
  syncCanvas()
}
function moveDown(idx: number) {
  if (idx === orderedAgents.value.length - 1) return
  const arr = orderedAgents.value; [arr[idx], arr[idx + 1]] = [arr[idx + 1], arr[idx]]
  syncCanvas()
}

function removeWorker(id: number) { workerIds.value = workerIds.value.filter(w => w !== id); syncCanvas() }

function onModeChange() {
  orderedAgents.value = []
  supervisorAgentId.value = null
  workerIds.value = []
  syncCanvas()
}

// ---- Canvas (read-only preview) ----
const canvasNodes = shallowRef<Node[]>([])
const canvasEdges = shallowRef<Edge[]>([])

const nodeTypes = {
  start: markRaw(TerminalNode),
  agent: markRaw(AgentNode),
  end: markRaw(TerminalNode),
} as any as NodeTypesObject

const defaultEdgeOptions = {
  type: 'straight',
  animated: true,
  style: { stroke: '#00d4ff33', strokeWidth: 2 },
}

const agentNodeCount = computed(() =>
  canvasNodes.value.filter(n => n.type === 'agent').length
)

function syncCanvas() {
  const nodes: Node[] = [
    { id: 'start', type: 'start', position: { x: 400, y: 0 }, data: { type: 'start', label: '开始' }, draggable: false, deletable: false },
  ]
  const edges: Edge[] = []

  if (flowType.value === 'sequential') {
    const list = orderedAgents.value
    list.forEach((a, i) => {
      nodes.push({
        id: `agent_${a.id}`,
        type: 'agent',
        position: { x: 400, y: 100 + i * 110 },
        data: { label: a.display_name || a.name, role: a.role || 'worker', agentType: a.agent_type || 'local', agentId: a.id },
        draggable: false, deletable: false,
      })
    })
    if (list.length > 0) {
      edges.push({ id: 'e0', source: 'start', target: `agent_${list[0].id}`, ...edgeOpts('#00e67666') })
      for (let i = 0; i < list.length - 1; i++) {
        edges.push({ id: `e${i + 1}`, source: `agent_${list[i].id}`, target: `agent_${list[i + 1].id}`, ...edgeOpts('#00d4ff55') })
      }
      edges.push({ id: `e_last`, source: `agent_${list[list.length - 1].id}`, target: 'end', ...edgeOpts('#ff3d4f66') })
    }
  }

  if (flowType.value === 'supervisor') {
    if (supervisorAgentId.value) {
      const sv = agents.value.find(a => a.id === supervisorAgentId.value)
      nodes.push({
        id: `agent_${supervisorAgentId.value}`,
        type: 'agent',
        position: { x: 400, y: 80 },
        data: { label: sv?.display_name || sv?.name || 'Supervisor', role: 'supervisor', agentType: sv?.agent_type || 'local', agentId: supervisorAgentId.value },
        draggable: false, deletable: false,
      })
      edges.push({ id: 'e0', source: 'start', target: `agent_${supervisorAgentId.value}`, ...edgeOpts('#00e67666') })
    }
    workerIds.value.forEach((wid, i) => {
      const w = agents.value.find(a => a.id === wid)
      nodes.push({
        id: `agent_${wid}`,
        type: 'agent',
        position: { x: 180 + i * 220, y: 280 },
        data: { label: w?.display_name || w?.name || `#${wid}`, role: 'worker', agentType: w?.agent_type || 'local', agentId: wid },
        draggable: false, deletable: false,
      })
      if (supervisorAgentId.value) {
        edges.push({ id: `e_sv_${wid}`, source: `agent_${supervisorAgentId.value}`, target: `agent_${wid}`, ...edgeOpts('#f0a50055') })
      }
      edges.push({ id: `e_${wid}_end`, source: `agent_${wid}`, target: 'end', ...edgeOpts('#ff3d4f66') })
    })
  }

  nodes.push({ id: 'end', type: 'end', position: { x: 400, y: 520 }, data: { type: 'end', label: '结束' }, draggable: false, deletable: false })

  canvasNodes.value = nodes
  canvasEdges.value = edges

  setTimeout(() => { (vueFlowRef.value as any)?.fitView?.({ padding: 0.2 }) }, 100)
}

function edgeOpts(color: string) {
  return { type: 'straight', animated: true, style: { stroke: color, strokeWidth: 2 } }
}

function fitView() { (vueFlowRef.value as any)?.fitView?.({ padding: 0.2 }) }

watch([flowType, supervisorAgentId, () => workerIds.value.length, () => orderedAgents.value.length], syncCanvas)

// ---- Save ----
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
      data.worker_agent_ids = [...workerIds.value]
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

// ---- Quick create supervisor ----
const showCreateSupervisor = ref(false)
const creatingAgent = ref(false)
const quickAgentName = ref('')
const quickAgentDisplayName = ref('')
const quickAgentLlmConfigId = ref<number | null>(null)
const quickAgentPrompt = ref('')
const llmConfigOptions = ref<{ value: number; label: string }[]>([])

async function handleCreateSupervisor() {
  if (!quickAgentName.value) { message.warning('请输入名称'); return }
  if (!quickAgentLlmConfigId.value) { message.warning('请选择 LLM 配置'); return }
  creatingAgent.value = true
  try {
    const res = await agentsApi.create({
      name: quickAgentName.value,
      display_name: quickAgentDisplayName.value || quickAgentName.value,
      agent_type: 'local',
      role: 'supervisor',
      system_prompt: quickAgentPrompt.value,
      llm_config_id: quickAgentLlmConfigId.value,
      llm_config: null,
    })
    const newId = res.data.data.id
    supervisorAgentId.value = newId
    showCreateSupervisor.value = false
    message.success('主管 Agent 已创建')
    const listRes = await agentsApi.list({ status: 'active' })
    agents.value = listRes.data.data || []
    syncCanvas()
  } catch (e: any) {
    message.error(e.response?.data?.message || '创建失败')
  } finally {
    creatingAgent.value = false
  }
}

// ---- Init ----
async function loadLlmConfigOptions() {
  try {
    const res = await llmConfigsApi.list()
    llmConfigOptions.value = (res.data.data || []).map((c: any) => ({
      value: c.id, label: `${c.name} (${c.provider}/${c.model})`,
    }))
  } catch { /* ignore */ }
}

onMounted(async () => {
  loadLlmConfigOptions()
  try {
    const res = await agentsApi.list({ status: 'active' })
    agents.value = res.data.data || []
  } catch { /* ignore */ }

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
        workerIds.value = (w.worker_agent_ids || []).map(Number)
      } else {
        const ids = w.worker_agent_ids || []
        orderedAgents.value = ids.map((id: number) =>
          agents.value.find(a => a.id === id) || { id, name: `#${id}`, display_name: `Agent #${id}`, agent_type: 'local', role: 'worker' }
        )
      }
      syncCanvas()
    } catch { message.error('加载工作流失败') }
  }
})
</script>

<style scoped>
.wf-editor { animation: fade-in 0.3s var(--ease-out); }

.wf-layout {
  display: flex;
  gap: 16px;
  height: calc(100vh - 180px);
  min-height: 520px;
}

/* ---- Left form panel ---- */
.wf-form-panel {
  width: 380px;
  min-width: 380px;
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.form-scroll {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.form-section {
  padding: 12px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.form-section:last-child { border-bottom: none; }
.form-label {
  font-size: 11px;
  font-weight: 600;
  color: #8892a4;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 8px;
}

/* Agent list (sequential) */
.agent-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 260px;
  overflow-y: auto;
}
.agent-list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.15);
  border: 1px solid var(--border-subtle);
  transition: border-color var(--duration-fast) var(--ease-out);
}
.agent-list-item:hover { border-color: var(--border-glow); }
.agent-list-idx {
  font-size: 11px;
  color: #535b6e;
  width: 18px;
  text-align: center;
  font-weight: 600;
}

/* ---- Right canvas panel ---- */
.wf-canvas-panel {
  flex: 1;
  border-radius: var(--radius-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.canvas-toolbar {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-subtle);
  background: rgba(0, 0, 0, 0.2);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.flow-canvas {
  flex: 1;
  background: radial-gradient(ellipse at center, #0c101b 0%, #080c15 50%, #03050a 100%) !important;
}

/* Vue Flow dark overrides */
:deep(.vue-flow__background) { background: transparent !important; }
:deep(.vue-flow__controls-button) {
  background: rgba(12, 16, 27, 0.9) !important;
  border-color: #1e2538 !important;
  fill: #8892a4 !important;
}
:deep(.vue-flow__controls-button:hover) { background: rgba(0, 212, 255, 0.1) !important; }
:deep(.vue-flow__edge-path) { stroke: #00d4ff44 !important; }
:deep(.vue-flow__edge:hover .vue-flow__edge-path) { stroke: #00d4ff88 !important; }
:deep(.vue-flow__edge.animated path:last-child) { stroke-dasharray: 5; animation: dashdraw .5s linear infinite; }
:deep(.vue-flow__minimap) {
  background: rgba(8, 12, 21, 0.9) !important;
  border: 1px solid #1e2538 !important;
  border-radius: 8px !important;
}
</style>
