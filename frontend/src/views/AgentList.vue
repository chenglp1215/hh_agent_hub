<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">Agent 管理</h1>
      <a-button type="primary" @click="$router.push('/agents/create')">
        <PlusOutlined /> 创建 Agent
      </a-button>
    </div>

    <div class="mb-4 flex gap-4">
      <a-input-search v-model:value="search" placeholder="搜索名称..." class="max-w-xs" @change="fetchList" />
      <a-select v-model:value="agentType" class="w-40" placeholder="Agent 类型" @change="fetchList">
        <a-select-option value="">全部类型</a-select-option>
        <a-select-option value="local">本地 Agent</a-select-option>
        <a-select-option value="http">HTTP Agent</a-select-option>
        <a-select-option value="a2a">A2A Agent</a-select-option>
        <a-select-option value="claudecode">Claude Code</a-select-option>
      </a-select>
      <a-select v-model:value="status" class="w-32" placeholder="状态" @change="fetchList">
        <a-select-option value="">全部状态</a-select-option>
        <a-select-option value="active">启用</a-select-option>
        <a-select-option value="disabled">禁用</a-select-option>
      </a-select>
    </div>

    <a-table
      :dataSource="filteredAgents"
      :columns="columns"
      rowKey="id"
      :loading="loading"
      :pagination="{ pageSize: 10 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'agent_type'">
          <a-tag :color="typeColor(record.agent_type)">{{ typeLabel(record.agent_type) }}</a-tag>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'red'">
            {{ record.status === 'active' ? '启用' : '禁用' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'time'">
          <span class="text-xs">{{ formatTime(record.updated_at) }}</span>
        </template>
        <template v-if="column.key === 'resources'">
          <span class="text-xs text-gray-400">
            MCP:{{ record.resource_count?.mcp || 0 }}
            知识库:{{ record.resource_count?.kb || 0 }}
            Skill:{{ record.resource_count?.skills || 0 }}
          </span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button size="small" @click="$router.push(`/agents/${record.id}/edit`)">编辑</a-button>
            <a-button size="small" @click="handleCopy(record.id)">复制</a-button>
            <a-popconfirm title="确定删除？" @confirm="handleDelete(record.id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { formatTime } from '@/utils/time'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { agentsApi } from '@/api/agents'

const agents = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const agentType = ref('')
const status = ref('')

const columns = [
  { title: '名称', dataIndex: 'display_name', key: 'name' },
  { title: '标识', dataIndex: 'name', key: 'key' },
  { title: '类型', key: 'agent_type', width: 120 },
  { title: '角色', dataIndex: 'role', key: 'role', width: 80 },
  { title: '状态', key: 'status', width: 80 },
  { title: '关联资源', key: 'resources', width: 180 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'time', width: 160 },
  { title: '操作', key: 'actions', width: 220 },
]

const filteredAgents = computed(() => {
  let list = agents.value
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(a => (a.name + a.display_name).toLowerCase().includes(q))
  }
  return list
})

function typeColor(t: string) {
  return { local: 'blue', http: 'orange', a2a: 'cyan', claudecode: 'purple' }[t] || 'default'
}

function typeLabel(t: string) {
  return { local: '本地', http: 'HTTP', a2a: 'A2A', claudecode: 'Claude Code' }[t] || t
}

async function fetchList() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (agentType.value) params.agent_type = agentType.value
    if (status.value) params.status = status.value
    const res = await agentsApi.list(params)
    agents.value = res.data.data || []
  } catch {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleCopy(id: number) {
  try {
    await agentsApi.copy(id)
    message.success('复制成功')
    fetchList()
  } catch {
    message.error('复制失败')
  }
}

async function handleDelete(id: number) {
  try {
    await agentsApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch {
    message.error('删除失败')
  }
}

onMounted(fetchList)
</script>
