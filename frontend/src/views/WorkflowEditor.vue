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
      <!-- Sidebar: mode + config + agent palette -->
      <div class="wf-sidebar glass" style="animation: slide-in-left 0.4s var(--ease-out)">
        <!-- Workflow name -->
        <div class="sidebar-section">
          <div class="sidebar-label">工作流名称</div>
          <a-input v-model:value="name" placeholder="如：需求分析流水线" size="large" class="!mb-2" />
          <a-textarea v-model:value="description" :rows="2" placeholder="描述（可选）" />
        </div>

        <!-- Flow mode -->
        <div class="sidebar-section">
          <div class="sidebar-label">工作流模式</div>
          <a-radio-group v-model:value="flowType" button-style="solid" size="small" @change="onModeChange" class="mode-group">
            <a-radio-button value="sequential">顺序</a-radio-button>
            <a-radio-button value="supervisor">监督者</a-radio-button>
            <a-radio-button value="graph">自由图</a-radio-button>
          </a-radio-group>
        </div>

        <!-- Supervisor selector (supervisor mode) -->
        <div v-if="flowType === 'supervisor'" class="sidebar-section">
          <div class="sidebar-label">主管 Agent</div>
          <a-select
            v-model:value="supervisorAgentId"
            placeholder="选择主管..."
            :options="supervisorAgentOpts"
            show-search
            filter-option
            allow-clear
            @change="onSupervisorChange"
          />
          <a-button size="small" type="link" @click="showCreateSupervisor = true" class="!p-0 !mt-1">
            + 快捷创建主管
          </a-button>
        </div>

        <!-- Agent palette for drag -->
        <div class="sidebar-section flex-1 flex flex-col min-h-0">
          <div class="sidebar-label">
            可用 Agent
            <span class="text-xs text-[#535b6e] ml-1">（拖拽到画布）</span>
          </div>
          <a-input-search
            v-model:value="agentSearch"
            placeholder="搜索..."
            size="small"
            class="!mb-2"
          />
          <div class="agent-palette">
            <div
              v-for="agent in filteredAgentList"
              :key="agent.id"
              class="palette-item"
              :class="{ 'palette-item--used': usedAgentIds.has(agent.id) }"
              draggable="true"
              @dragstart="onDragStart($event, agent)"
            >
              <div class="palette-item__icon" :class="agent.role === 'supervisor' ? 'bg-[#f0a50020] text-[#f0a500]' : 'bg-[#00d4ff15] text-[#00d4ff]'">
                <RobotOutlined />
              </div>
              <div class="palette-item__info">
                <div class="text-xs font-medium text-[#e4e7ee] truncate">
                  {{ agent.display_name || agent.name }}
                </div>
                <div class="text-[10px] text-[#535b6e]">{{ agent.role }} · {{ agent.agent_type }}</div>
              </div>
              <span v-if="usedAgentIds.has(agent.id)" class="text-[10px] text-[#00e676]">已用</span>
            </div>
            <div v-if="filteredAgentList.length === 0" class="text-center text-xs text-[#535b6e] py-4">
              无匹配 Agent
            </div>
          </div>
        </div>
      </div>

      <!-- Canvas -->
      <div class="wf-canvas glass" style="animation: scale-in 0.5s var(--ease-out)">
        <div class="canvas-toolbar">
          <a-space size="small">
            <a-button size="small" @click="autoLayout" :disabled="allNodes.length <= 2">
              <PartitionOutlined /> 自动布局
            </a-button>
            <a-button size="small" @click="fitView">
              <ExpandOutlined /> 适应画布
            </a-button>
            <a-divider type="vertical" />
            <span class="text-xs text-[#535b6e]">
              {{ allNodes.length }} 节点 · {{ edges.length }} 连线
            </span>
          </a-space>
        </div>

        <VueFlow
          ref="vueFlowRef"
          v-model:nodes="nodes"
          v-model:edges="edges"
          :node-types="nodeTypes"
          :default-edge-options="defaultEdgeOptions"
          :connection-line-style="connectionLineStyle"
          fit-view-on-init
          class="flow-canvas"
          @drop="onDrop"
          @dragover="onDragOver"
          @connect="onConnect"
          @node-click="onNodeClick"
          @pane-click="onPaneClick"
          @edge-click="onEdgeClick"
        >
          <Background :gap="24" :size="1" pattern-color="#151a28" />
          <Controls position="bottom-right" />
          <template #node-start="startProps">
            <TerminalNode :data="startProps.data" />
          </template>
          <template #node-agent="agentProps">
            <AgentNode :data="agentProps.data" :selected="agentProps.selected" />
          </template>
          <template #node-end="endProps">
            <TerminalNode :data="endProps.data" />
          </template>
        </VueFlow>
      </div>
    </div>

    <!-- Advanced settings -->
    <div class="mt-4 glass" style="border-radius: var(--radius-lg); padding: 16px 20px; animation: fade-in-up 0.5s 0.2s var(--ease-out) both;">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-xs text-[#8892a4] font-semibold">高级设置</span>
        <div class="flex items-center gap-2">
          <span class="text-xs text-[#535b6e]">错误策略</span>
          <a-radio-group v-model:value="errorStrategy" button-style="solid" size="small">
            <a-radio-button value="fail_fast">快速失败</a-radio-button>
            <a-radio-button value="skip_continue">跳过继续</a-radio-button>
          </a-radio-group>
        </div>
        <a-divider type="vertical" />
        <div class="flex items-center gap-2">
          <span class="text-xs text-[#535b6e]">Agent超时</span>
          <a-input-number v-model:value="agentTimeout" :min="5" :max="600" size="small" class="!w-20" />s
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-[#535b6e]">工作流超时</span>
          <a-input-number v-model:value="workflowTimeout" :min="10" :max="3600" size="small" class="!w-20" />s
        </div>
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
  SaveOutlined, RobotOutlined, PartitionOutlined, ExpandOutlined,
} from '@ant-design/icons-vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import type { Node, Edge, Connection, NodeTypesObject } from '@vue-flow/core'
import { workflowsApi } from '@/api/workflows'
import { agentsApi } from '@/api/agents'
import { llmConfigsApi } from '@/api/llmConfigs'
import AgentNode from '@/components/editor/AgentNode.vue'
import TerminalNode from '@/components/editor/TerminalNode.vue'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const saving = ref(false)

const vueFlowRef = ref()

// --- Basic info ---
const name = ref('')
const description = ref('')
const flowType = ref('sequential')
const errorStrategy = ref('fail_fast')
const agentTimeout = ref(60)
const workflowTimeout = ref(300)

// --- Vue Flow state ---
const nodes = shallowRef<Node[]>([])
const edges = shallowRef<Edge[]>([])

const nodeTypes = {
  start: markRaw(TerminalNode),
  agent: markRaw(AgentNode),
  end: markRaw(TerminalNode),
} as any as NodeTypesObject

const defaultEdgeOptions = {
  type: 'smoothstep',
  animated: true,
  style: {
    stroke: '#00d4ff33',
    strokeWidth: 2,
  },
}

const connectionLineStyle = {
  stroke: '#00d4ff66',
  strokeWidth: 2,
}

const allNodes = computed(() => nodes.value)
const usedAgentIds = computed(() => {
  const ids = new Set<number>()
  for (const n of nodes.value) {
    if (n.type === 'agent' && n.data?.agentId) ids.add(n.data.agentId)
  }
  return ids
})

// --- Agent palette ---
const agents = ref<any[]>([])
const agentSearch = ref('')

const filteredAgentList = computed(() => {
  if (!agentSearch.value) return agents.value
  const q = agentSearch.value.toLowerCase()
  return agents.value.filter((a: any) =>
    (a.name + a.display_name).toLowerCase().includes(q)
  )
})

const supervisorAgentOpts = computed(() =>
  agents.value
    .filter((a: any) => a.role === 'supervisor')
    .map((a: any) => ({ value: Number(a.id), label: a.display_name || a.name }))
)

const supervisorAgentId = ref<number | null>(null)

// --- Drag from palette ---
let draggedAgent: any = null

function onDragStart(event: DragEvent, agent: any) {
  draggedAgent = agent
  event.dataTransfer!.effectAllowed = 'move'
  event.dataTransfer!.setData('application/json', JSON.stringify(agent))
}

function onDragOver(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}

function onDrop(event: DragEvent) {
  if (!draggedAgent) return
  const agent = draggedAgent
  draggedAgent = null

  const position = (vueFlowRef.value as any)?.screenToFlowCoordinate?.({
    x: event.clientX,
    y: event.clientY,
  }) || { x: event.clientX - 320, y: event.clientY - 200 }

  addAgentNode(agent, position)
}

// --- Node management ---
let nodeCounter = 0

function addAgentNode(agent: any, position?: { x: number; y: number }) {
  if (usedAgentIds.value.has(agent.id)) {
    message.warning('该 Agent 已在画布中')
    return
  }

  const pos = position || {
    x: 300 + nodeCounter * 50,
    y: 200 + nodeCounter * 80,
  }
  nodeCounter++

  const newNode: Node = {
    id: `agent_${agent.id}`,
    type: 'agent',
    position: pos,
    data: {
      label: agent.display_name || agent.name,
      role: agent.role || 'worker',
      agentType: agent.agent_type || 'local',
      agentId: agent.id,
    },
  }

  nodes.value.push(newNode)

  // Auto-create edges in sequential mode
  if (flowType.value === 'sequential') {
    rebuildSequentialEdges()
  }
  if (flowType.value === 'supervisor' && agent.role !== 'supervisor') {
    rebuildSupervisorEdges()
  }
}

function onConnect(connection: Connection) {
  if (flowType.value !== 'graph') {
    message.info('仅在自由图模式可手动连线')
    return
  }
  edges.value = [
    ...edges.value,
    {
      ...connection,
      id: `edge_${connection.source}_${connection.target}`,
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#00d4ff55', strokeWidth: 2 },
    } as Edge,
  ]
}

function onNodeClick({ node }: { node: Node }) {
  if (node.type === 'agent') {
    message.info(`Agent: ${node.data.label}`)
  }
}

function onPaneClick() {
  // Deselect all
}

function onEdgeClick({ edge }: { edge: Edge }) {
  edges.value = edges.value.filter(e => e.id !== edge.id)
}

// --- Edge rebuilding for different modes ---
function rebuildSequentialEdges() {
  const agentNodes = nodes.value.filter(n => n.type === 'agent')
  const newEdges: Edge[] = []

  if (agentNodes.length > 0) {
    newEdges.push({
      id: 'e_start_first',
      source: 'start',
      target: agentNodes[0].id,
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#00e67666', strokeWidth: 2 },
    })
    for (let i = 0; i < agentNodes.length - 1; i++) {
      newEdges.push({
        id: `e_${agentNodes[i].id}_${agentNodes[i + 1].id}`,
        source: agentNodes[i].id,
        target: agentNodes[i + 1].id,
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#00d4ff55', strokeWidth: 2 },
      })
    }
    newEdges.push({
      id: 'e_last_end',
      source: agentNodes[agentNodes.length - 1].id,
      target: 'end',
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#ff3d4f66', strokeWidth: 2 },
    })
  }

  edges.value = newEdges
}

function rebuildSupervisorEdges() {
  const svNode = nodes.value.find(n => n.type === 'agent' && n.data.role === 'supervisor')
  const workerNodes = nodes.value.filter(n => n.type === 'agent' && n.data.role !== 'supervisor')
  const newEdges: Edge[] = []

  if (svNode) {
    newEdges.push({
      id: 'e_start_sv',
      source: 'start',
      target: svNode.id,
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#00e67666', strokeWidth: 2 },
    })
    for (const wn of workerNodes) {
      newEdges.push({
        id: `e_sv_${wn.id}`,
        source: svNode.id,
        target: wn.id,
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#f0a50055', strokeWidth: 2 },
      })
      newEdges.push({
        id: `e_${wn.id}_end`,
        source: wn.id,
        target: 'end',
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#ff3d4f66', strokeWidth: 2 },
      })
    }
  }

  edges.value = newEdges
}

// --- Supervisor node management ---
function onSupervisorChange(val: number | null) {
  // Remove old supervisor nodes
  nodes.value = nodes.value.filter(n => !(n.type === 'agent' && n.data.role === 'supervisor'))

  if (val) {
    const agent = agents.value.find((a: any) => a.id === val)
    if (agent) {
      const svNode: Node = {
        id: `agent_${agent.id}`,
        type: 'agent',
        position: { x: 400, y: 120 },
        data: {
          label: agent.display_name || agent.name,
          role: 'supervisor',
          agentType: agent.agent_type || 'local',
          agentId: agent.id,
        },
      }
      nodes.value = [...nodes.value, svNode]
      rebuildSupervisorEdges()
    }
  } else {
    edges.value = []
  }
}

// --- Auto layout ---
function autoLayout() {
  const agentNodes = nodes.value.filter(n => n.type === 'agent')
  if (agentNodes.length === 0) return

  if (flowType.value === 'sequential') {
    const startX = 400
    agentNodes.forEach((n, i) => {
      n.position = { x: startX, y: 120 + i * 120 }
    })
  } else if (flowType.value === 'supervisor') {
    const svNode = agentNodes.find(n => n.data.role === 'supervisor')
    const workers = agentNodes.filter(n => n.data.role !== 'supervisor')
    if (svNode) svNode.position = { x: 400, y: 80 }
    workers.forEach((n, i) => {
      n.position = { x: 200 + i * 200, y: 280 }
    })
  } else {
    // Graph: circular layout
    const cx = 450, cy = 250, radius = 180
    agentNodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / agentNodes.length - Math.PI / 2
      n.position = { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) }
    })
  }

  // Trigger reactivity
  nodes.value = [...nodes.value]
}

function fitView() {
  ;(vueFlowRef.value as any)?.fitView?.({ padding: 0.2 })
}

// --- Mode change ---
function onModeChange() {
  // Remove all agent nodes and edges
  nodes.value = nodes.value.filter(n => n.type === 'start' || n.type === 'end')
  edges.value = []
  supervisorAgentId.value = null
}

// --- Ensure terminal nodes exist ---
function ensureTerminalNodes() {
  const hasStart = nodes.value.some(n => n.id === 'start')
  const hasEnd = nodes.value.some(n => n.id === 'end')

  const updates: Node[] = []
  if (!hasStart) {
    updates.push({
      id: 'start',
      type: 'start',
      position: { x: 400, y: 0 },
      data: { type: 'start', label: '开始' },
      draggable: false,
      deletable: false,
    })
  }
  if (!hasEnd) {
    updates.push({
      id: 'end',
      type: 'end',
      position: { x: 400, y: 500 },
      data: { type: 'end', label: '结束' },
      draggable: false,
      deletable: false,
    })
  }
  if (updates.length > 0) {
    nodes.value = [...nodes.value, ...updates]
  }
}

watch([flowType, nodes], () => {
  ensureTerminalNodes()
}, { immediate: true, deep: true })

// --- Save ---
async function handleSave() {
  if (!name.value.trim()) { message.warning('请输入工作流名称'); return }

  saving.value = true
  try {
    const agentNodes = nodes.value.filter(n => n.type === 'agent')
    const workerAgentIds = agentNodes
      .filter(n => n.data.role !== 'supervisor')
      .map(n => n.data.agentId)
    const svNode = agentNodes.find(n => n.data.role === 'supervisor')

    // Serialize edges for graph mode
    const edgeData = (flowType.value === 'graph')
      ? edges.value.map(e => ({ from: e.source, to: e.target }))
      : []

    const data: Record<string, any> = {
      name: name.value.trim(),
      description: description.value,
      flow_type: flowType.value,
      worker_agent_ids: workerAgentIds,
      edges: edgeData,
      error_strategy: errorStrategy.value,
      agent_timeout_seconds: agentTimeout.value,
      workflow_timeout_seconds: workflowTimeout.value,
    }

    if (flowType.value === 'supervisor') {
      data.supervisor_agent_id = svNode?.data?.agentId || supervisorAgentId.value
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

// --- Quick create supervisor ---
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
    onSupervisorChange(newId)
  } catch (e: any) {
    message.error(e.response?.data?.message || '创建失败')
  } finally {
    creatingAgent.value = false
  }
}

// --- Init ---
async function loadLlmConfigOptions() {
  try {
    const res = await llmConfigsApi.list()
    llmConfigOptions.value = (res.data.data || []).map((c: any) => ({
      value: c.id,
      label: `${c.name} (${c.provider}/${c.model})`,
    }))
  } catch { /* ignore */ }
}

onMounted(async () => {
  loadLlmConfigOptions()
  try {
    const res = await agentsApi.list({ status: 'active' })
    agents.value = res.data.data || []
  } catch { /* optional */ }

  ensureTerminalNodes()

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

      const workerIds: number[] = w.worker_agent_ids || []
      const loadedNodes: Node[] = [...nodes.value]

      // Add supervisor node
      if (w.supervisor_agent_id) {
        supervisorAgentId.value = w.supervisor_agent_id
        const svAgent = agents.value.find((a: any) => a.id === w.supervisor_agent_id)
        loadedNodes.push({
          id: `agent_${w.supervisor_agent_id}`,
          type: 'agent',
          position: { x: 400, y: 80 },
          data: {
            label: svAgent?.display_name || svAgent?.name || `Agent #${w.supervisor_agent_id}`,
            role: 'supervisor',
            agentType: svAgent?.agent_type || 'local',
            agentId: w.supervisor_agent_id,
          },
        })
      }

      // Add worker nodes
      workerIds.forEach((id: number, idx: number) => {
        const agent = agents.value.find((a: any) => a.id === id)
        loadedNodes.push({
          id: `agent_${id}`,
          type: 'agent',
          position: {
            x: w.flow_type === 'supervisor' ? 200 + idx * 200 : 400,
            y: w.flow_type === 'supervisor' ? 280 : 120 + idx * 120,
          },
          data: {
            label: agent?.display_name || agent?.name || `Agent #${id}`,
            role: agent?.role || 'worker',
            agentType: agent?.agent_type || 'local',
            agentId: id,
          },
        })
      })

      nodes.value = loadedNodes

      // Rebuild edges
      if (w.flow_type === 'sequential') rebuildSequentialEdges()
      else if (w.flow_type === 'supervisor') rebuildSupervisorEdges()
      else if (w.flow_type === 'graph' && w.edges) {
        edges.value = w.edges.map((e: any) => ({
          id: `edge_${e.from}_${e.to}`,
          source: e.from,
          target: e.to,
          type: 'smoothstep',
          animated: true,
          style: { stroke: '#00d4ff55', strokeWidth: 2 },
        }))
      }
    } catch {
      message.error('加载工作流失败')
    }
  }
})
</script>

<style scoped>
.wf-editor {
  animation: fade-in 0.3s var(--ease-out);
}

.wf-layout {
  display: flex;
  gap: 16px;
  height: calc(100vh - 220px);
  min-height: 500px;
}

.wf-sidebar {
  width: 280px;
  min-width: 280px;
  border-radius: var(--radius-lg);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow: hidden;
}

.sidebar-section {
  padding-bottom: 14px;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--border-subtle);
}
.sidebar-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.sidebar-label {
  font-size: 11px;
  font-weight: 600;
  color: #8892a4;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 8px;
}

.mode-group :deep(.ant-radio-button-wrapper) {
  font-size: 12px !important;
  padding: 2px 10px !important;
}

/* Agent palette */
.agent-palette {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.palette-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: grab;
  transition: all var(--duration-fast) var(--ease-out);
  border: 1px solid transparent;
}
.palette-item:hover {
  background: rgba(0, 212, 255, 0.05);
  border-color: rgba(0, 212, 255, 0.12);
}
.palette-item:active {
  cursor: grabbing;
  background: rgba(0, 212, 255, 0.1);
}
.palette-item--used {
  opacity: 0.4;
}

.palette-item__icon {
  width: 28px;
  height: 28px;
  min-width: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
}

.palette-item__info {
  flex: 1;
  min-width: 0;
}

/* Canvas */
.wf-canvas {
  flex: 1;
  border-radius: var(--radius-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.canvas-toolbar {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-subtle);
  background: rgba(0, 0, 0, 0.2);
}

.flow-canvas {
  flex: 1;
  background: radial-gradient(ellipse at center, #0c101b 0%, #080c15 50%, #03050a 100%) !important;
}

/* Vue Flow dark overrides */
:deep(.vue-flow__background) {
  background: transparent !important;
}
:deep(.vue-flow__controls) {
  z-index: 10 !important;
}
:deep(.vue-flow__controls-button) {
  background: rgba(12, 16, 27, 0.9) !important;
  border-color: #1e2538 !important;
  fill: #8892a4 !important;
}
:deep(.vue-flow__controls-button:hover) {
  background: rgba(0, 212, 255, 0.1) !important;
}
:deep(.vue-flow__edge-path) {
  stroke: #00d4ff44 !important;
}
:deep(.vue-flow__edge:hover .vue-flow__edge-path) {
  stroke: #00d4ff88 !important;
}
:deep(.vue-flow__edge.selected .vue-flow__edge-path) {
  stroke: #00d4ff !important;
  stroke-width: 2.5;
}
:deep(.vue-flow__selection) {
  border-color: #00d4ff44 !important;
  background: rgba(0, 212, 255, 0.04) !important;
}
:deep(.vue-flow__minimap) {
  background: rgba(8, 12, 21, 0.9) !important;
  border: 1px solid #1e2538 !important;
  border-radius: 8px !important;
}
</style>
