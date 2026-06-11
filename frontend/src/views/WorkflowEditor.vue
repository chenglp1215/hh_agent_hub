<template>
  <div class="flex flex-col h-[calc(100vh-120px)]">
    <div class="flex items-center justify-between mb-4 shrink-0">
      <div class="flex items-center gap-4">
        <h1 class="text-2xl font-bold">{{ isEdit ? '编辑' : '创建' }} 工作流</h1>
        <a-input v-model:value="workflowName" placeholder="工作流名称" class="w-48" />
        <a-select v-model:value="flowType" class="w-36">
          <a-select-option value="supervisor">监督者模式</a-select-option>
          <a-select-option value="sequential">顺序模式</a-select-option>
          <a-select-option value="graph">图模式</a-select-option>
        </a-select>
        <a-select v-model:value="errorStrategy" class="w-32">
          <a-select-option value="fail_fast">快速失败</a-select-option>
          <a-select-option value="skip_continue">跳过继续</a-select-option>
          <a-select-option value="retry">自动重试</a-select-option>
        </a-select>
      </div>
      <a-space>
        <a-button @click="handleValidate">验证</a-button>
        <a-button type="primary" @click="handleSave" :loading="saving">保存</a-button>
      </a-space>
    </div>

    <div class="flex flex-1 gap-4 min-h-0">
      <!-- Left: Agent palette -->
      <div class="w-48 bg-[#0a0a0b] border border-[#1e1e20] rounded p-3 flex flex-col gap-2 overflow-y-auto shrink-0">
        <h4 class="text-sm text-gray-400 mb-2">Agent 列表</h4>
        <div v-if="agents.length === 0" class="text-xs text-gray-500">暂无可用 Agent</div>
        <div
          v-for="agent in agents" :key="agent.id"
          class="p-2 bg-[#010102] border border-[#1e1e20] rounded cursor-grab hover:border-[#5e6ad2] text-sm"
          draggable="true"
          @dragstart="onDragStart($event, agent)"
        >
          <div class="font-medium">{{ agent.display_name || agent.name }}</div>
          <div class="text-xs text-gray-500">{{ { local: '本地', http: 'HTTP', claudecode: 'CC' }[agent.agent_type] }}</div>
        </div>
      </div>

      <!-- Center: Vue Flow canvas -->
      <div
        class="flex-1 bg-[#010102] border border-[#1e1e20] rounded overflow-hidden"
        @drop="onDrop"
        @dragover.prevent
      >
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :default-viewport="{ zoom: 1 }"
          fit-view-on-init
          class="h-full"
          @node-click="onNodeClick"
          @pane-click="selectedNode = null"
        >
          <Background />
          <Controls />

          <template #node-start="props">
            <div class="px-4 py-2 bg-green-600 rounded-full text-white text-xs font-bold">START</div>
          </template>
          <template #node-end="props">
            <div class="px-4 py-2 bg-red-600 rounded-full text-white text-xs font-bold">END</div>
          </template>
          <template #node-supervisor="props">
            <div class="px-4 py-2 bg-blue-600 rounded-lg text-white text-sm font-medium">{{ props.data.label }}</div>
          </template>
          <template #node-worker="props">
            <div class="px-4 py-2 bg-green-700 rounded-lg text-white text-sm font-medium">{{ props.data.label }}</div>
          </template>
          <template #node-condition="props">
            <div
              class="bg-yellow-600 text-white text-xs font-bold flex items-center justify-center"
              style="width:80px;height:80px;transform:rotate(45deg)"
            >
              <span style="transform:rotate(-45deg)">{{ props.data.label }}</span>
            </div>
          </template>
        </VueFlow>
      </div>

      <!-- Right: Property panel -->
      <div v-if="selectedNode" class="w-64 bg-[#0a0a0b] border border-[#1e1e20] rounded p-4 shrink-0 overflow-y-auto">
        <h4 class="text-sm font-semibold mb-3 text-[#5e6ad2]">节点属性</h4>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-gray-400">标签</label>
            <a-input v-model:value="selectedNode.data.label" size="small" />
          </div>
          <div>
            <label class="text-xs text-gray-400">类型</label>
            <a-select v-model:value="selectedNode.type" size="small" class="w-full">
              <a-select-option value="supervisor">主管 Agent</a-select-option>
              <a-select-option value="worker">工作 Agent</a-select-option>
              <a-select-option value="condition">条件判断</a-select-option>
            </a-select>
          </div>
          <a-button size="small" danger block @click="removeNode">删除节点</a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { workflowsApi } from '@/api/workflows'
import { agentsApi } from '@/api/agents'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const saving = ref(false)

const workflowName = ref('')
const flowType = ref('sequential')
const errorStrategy = ref('fail_fast')
const agents = ref<any[]>([])

const nodes = ref<any[]>([
  { id: 'start', type: 'start', position: { x: 400, y: 0 }, data: { label: 'Start' } },
  { id: 'end', type: 'end', position: { x: 400, y: 500 }, data: { label: 'End' } },
])
const edges = ref<any[]>([])
const selectedNode = ref<any>(null)

let nodeIdCounter = 0

function onDragStart(event: DragEvent, agent: any) {
  event.dataTransfer!.setData('application/json', JSON.stringify(agent))
  event.dataTransfer!.effectAllowed = 'move'
}

function onDrop(event: DragEvent) {
  const data = event.dataTransfer?.getData('application/json')
  if (!data) return
  const agent = JSON.parse(data)

  const container = event.currentTarget as HTMLElement
  const rect = container.getBoundingClientRect()
  const position = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }

  const newNode = {
    id: `agent_${agent.id}_${nodeIdCounter++}`,
    type: agent.role === 'supervisor' ? 'supervisor' : 'worker',
    position,
    data: { label: agent.display_name || agent.name, agentId: agent.id },
  }
  nodes.value.push(newNode)
}

function onNodeClick(event: any) {
  selectedNode.value = event.node
}

function removeNode() {
  if (selectedNode.value && selectedNode.value.id !== 'start' && selectedNode.value.id !== 'end') {
    nodes.value = nodes.value.filter(n => n.id !== selectedNode.value.id)
    edges.value = edges.value.filter(e => e.source !== selectedNode.value.id && e.target !== selectedNode.value.id)
    selectedNode.value = null
  }
}

async function handleValidate() {
  try {
    const res = await workflowsApi.validate(isEdit.value ? Number(route.params.id) : 0)
    const vdata = res.data.data
    if (vdata.valid) {
      message.success('验证通过')
    } else {
      message.warning(`验证问题: ${vdata.errors?.join('; ') || '未知'}`)
    }
  } catch {
    if (nodes.value.length <= 2) {
      message.warning('请至少添加一个 Agent 节点')
    } else {
      message.success('本地验证通过')
    }
  }
}

async function handleSave() {
  if (!workflowName.value) {
    message.warning('请输入工作流名称')
    return
  }
  saving.value = true
  try {
    const workerIds = nodes.value
      .filter(n => n.type === 'supervisor' || n.type === 'worker')
      .map(n => n.data.agentId)
      .filter(Boolean)

    const workflowEdges = edges.value.map(e => ({
      from: e.source,
      to: e.target,
      type: 'normal',
    }))

    const data: Record<string, any> = {
      name: workflowName.value,
      flow_type: flowType.value,
      worker_agent_ids: workerIds,
      edges: workflowEdges,
      error_strategy: errorStrategy.value,
    }

    if (isEdit.value) {
      await workflowsApi.update(Number(route.params.id), data)
    } else {
      await workflowsApi.create(data)
    }
    message.success('保存成功')
    router.push('/workflows')
  } catch {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const res = await agentsApi.list({ status: 'active' })
    agents.value = res.data.data || []
  } catch {
    // Agents list is optional for the editor to function
  }

  if (isEdit.value) {
    try {
      const res = await workflowsApi.get(Number(route.params.id))
      const w = res.data.data
      workflowName.value = w.name
      flowType.value = w.flow_type
      errorStrategy.value = w.error_strategy || 'fail_fast'

      const workerNodes = (w.worker_agent_ids || []).map((id: number, i: number) => ({
        id: `agent_${id}_${i}`,
        type: 'worker',
        position: { x: 300 + i * 180, y: 200 },
        data: { label: `Agent #${id}`, agentId: id },
      }))
      nodes.value = [
        { id: 'start', type: 'start', position: { x: 400, y: 0 }, data: { label: 'Start' } },
        ...workerNodes,
        { id: 'end', type: 'end', position: { x: 400, y: 500 }, data: { label: 'End' } },
      ]

      if (w.edges?.length) {
        edges.value = w.edges.map((e: any) => ({
          id: `e-${e.from}-${e.to}`,
          source: e.from,
          target: e.to,
        }))
      } else {
        for (let i = 0; i < workerNodes.length; i++) {
          edges.value.push({
            id: `e-auto-${i}`,
            source: i === 0 ? 'start' : workerNodes[i - 1].id,
            target: workerNodes[i].id,
          })
        }
        if (workerNodes.length > 0) {
          edges.value.push({
            id: 'e-end',
            source: workerNodes[workerNodes.length - 1].id,
            target: 'end',
          })
        }
      }
    } catch {
      message.error('加载工作流失败')
    }
  }
})
</script>
