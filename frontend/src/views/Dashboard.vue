<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">主控台</h1>

    <!-- Stats cards -->
    <a-row :gutter="16" class="mb-8">
      <a-col :span="6">
        <a-card class="text-center hover:border-[#5e6ad2] transition-colors cursor-pointer" @click="$router.push('/agents')">
          <p class="text-gray-400 text-sm">Agent 总数</p>
          <p class="text-3xl font-bold text-[#5e6ad2]">{{ stats.agents }}</p>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="text-center hover:border-[#5e6ad2] transition-colors cursor-pointer" @click="$router.push('/workflows')">
          <p class="text-gray-400 text-sm">工作流总数</p>
          <p class="text-3xl font-bold text-[#5e6ad2]">{{ stats.workflows }}</p>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="text-center hover:border-[#5e6ad2] transition-colors cursor-pointer" @click="$router.push('/apps')">
          <p class="text-gray-400 text-sm">应用总数</p>
          <p class="text-3xl font-bold text-[#5e6ad2]">{{ stats.apps }}</p>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="text-center">
          <p class="text-gray-400 text-sm">今日执行</p>
          <p class="text-3xl font-bold text-[#5e6ad2]">{{ stats.executions }}</p>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="16">
      <!-- Recent executions -->
      <a-col :span="16">
        <a-card title="最近执行" class="mb-4">
          <a-table :dataSource="recentTraces" :columns="traceColumns" rowKey="id" size="small" :pagination="false">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'">
                <span class="inline-flex items-center gap-1">
                  <span class="inline-block w-2 h-2 rounded-full" :class="statusColor(record.status)" />
                  {{ statusLabel(record.status) }}
                </span>
              </template>
              <template v-if="column.key === 'actions'">
                <a-button size="small" type="link" @click="$router.push(`/monitor/traces/${record.execution_id}`)">查看</a-button>
              </template>
            </template>
          </a-table>
          <a-empty v-if="recentTraces.length === 0" description="暂无执行记录" class="mt-4" />
        </a-card>
      </a-col>

      <!-- Quick actions + Resource status -->
      <a-col :span="8">
        <a-card title="快捷入口" class="mb-4">
          <div class="space-y-3">
            <a-button type="primary" block @click="$router.push('/agents/create')">创建 Agent</a-button>
            <a-button block @click="$router.push('/workflows/create')">编排工作流</a-button>
            <a-button block @click="$router.push('/resources/mcp-servers/create')">注册 MCP Server</a-button>
            <a-button block @click="$router.push('/monitor/chat-test')">对话测试</a-button>
          </div>
        </a-card>

        <a-card title="资源状态">
          <div class="space-y-2 text-sm">
            <div class="flex justify-between">
              <span class="text-gray-400">MCP Server 在线</span>
              <span class="text-green-400">{{ resourceStatus.mcpOnline }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-400">知识库</span>
              <span>{{ resourceStatus.kbCount }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-400">Skill 模板</span>
              <span>{{ resourceStatus.skillCount }}</span>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { agentsApi } from '@/api/agents'
import { workflowsApi } from '@/api/workflows'
import { appsApi } from '@/api/apps'
import { tracesApi } from '@/api/traces'
import { mcpServersApi } from '@/api/mcpServers'
import { knowledgeBasesApi } from '@/api/knowledgeBases'
import { skillsApi } from '@/api/skills'

const stats = ref({ agents: 0, workflows: 0, apps: 0, executions: 0 })
const recentTraces = ref<any[]>([])
const resourceStatus = ref({ mcpOnline: 0, kbCount: 0, skillCount: 0 })

const traceColumns = [
  { title: 'Execution ID', dataIndex: 'execution_id', key: 'id', ellipsis: true },
  { title: '状态', key: 'status', width: 80 },
  { title: '耗时', dataIndex: 'total_duration_ms', key: 'duration', width: 80 },
  { title: '', key: 'actions', width: 60 },
]

function statusColor(s: string) { return { running: 'bg-blue-500', success: 'bg-green-500', failed: 'bg-red-500' }[s] || 'bg-gray-500' }
function statusLabel(s: string) { return { running: '运行中', success: '成功', failed: '失败' }[s] || s }

onMounted(async () => {
  try {
    const [agents, workflows, apps, traces, mcp, kbs, skills] = await Promise.allSettled([
      agentsApi.list(), workflowsApi.list(), appsApi.list(),
      tracesApi.list({ limit: 10 }),
      mcpServersApi.list(), knowledgeBasesApi.list(), skillsApi.list(),
    ])
    stats.value.agents = agents.status === 'fulfilled' ? (agents.value.data.data || []).length : 0
    stats.value.workflows = workflows.status === 'fulfilled' ? (workflows.value.data.data || []).length : 0
    stats.value.apps = apps.status === 'fulfilled' ? (apps.value.data.data || []).length : 0
    if (traces.status === 'fulfilled') {
      const traceData = traces.value.data.data || []
      stats.value.executions = traceData.length
      recentTraces.value = traceData.slice(0, 10)
    }
    if (mcp.status === 'fulfilled') {
      const mcpData = mcp.value.data.data || []
      resourceStatus.value.mcpOnline = mcpData.filter((s: any) => s.status === 'active').length
    }
    resourceStatus.value.kbCount = kbs.status === 'fulfilled' ? (kbs.value.data.data || []).length : 0
    resourceStatus.value.skillCount = skills.status === 'fulfilled' ? (skills.value.data.data || []).length : 0
  } catch {}
})
</script>
