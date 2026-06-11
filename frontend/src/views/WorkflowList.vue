<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">工作流编排</h1>
      <a-button type="primary" @click="$router.push('/workflows/create')">
        <PlusOutlined /> 创建工作流
      </a-button>
    </div>

    <div class="mb-4 flex gap-4">
      <a-input-search v-model:value="search" placeholder="搜索..." class="max-w-xs" />
      <a-select v-model:value="flowType" class="w-40" @change="fetchList">
        <a-select-option value="">全部模式</a-select-option>
        <a-select-option value="supervisor">监督者模式</a-select-option>
        <a-select-option value="sequential">顺序模式</a-select-option>
        <a-select-option value="graph">图模式</a-select-option>
      </a-select>
      <a-select v-model:value="status" class="w-32" @change="fetchList">
        <a-select-option value="">全部状态</a-select-option>
        <a-select-option value="draft">草稿</a-select-option>
        <a-select-option value="published">已发布</a-select-option>
      </a-select>
    </div>

    <a-table :dataSource="filteredWorkflows" :columns="columns" rowKey="id" :loading="loading" :pagination="{ pageSize: 10 }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'flow_type'">
          <a-tag :color="{ supervisor: 'blue', sequential: 'green', graph: 'purple' }[record.flow_type]">
            {{ { supervisor: '监督者', sequential: '顺序', graph: '图' }[record.flow_type] }}
          </a-tag>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'published' ? 'green' : 'orange'">
            {{ record.status === 'published' ? '已发布' : '草稿' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" @click="$router.push(`/workflows/${record.id}/edit`)">编辑</a-button>
          <a-button v-if="record.status === 'draft'" size="small" class="ml-1" type="primary" ghost @click="handlePublish(record.id)">发布</a-button>
          <a-popconfirm title="确定删除？" @confirm="handleDelete(record.id)">
            <a-button size="small" danger class="ml-1">删除</a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { workflowsApi } from '@/api/workflows'

const workflows = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const flowType = ref('')
const status = ref('')

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '描述', dataIndex: 'description', key: 'desc' },
  { title: '模式', key: 'flow_type', width: 100 },
  { title: 'Agent 数', dataIndex: 'worker_agent_ids', key: 'agents', width: 80 },
  { title: '版本', dataIndex: 'version', key: 'version', width: 60 },
  { title: '状态', key: 'status', width: 80 },
  { title: '操作', key: 'actions', width: 260 },
]

const filteredWorkflows = computed(() => {
  let list = workflows.value
  if (search.value) list = list.filter(w => w.name.toLowerCase().includes(search.value.toLowerCase()))
  return list
})

async function fetchList() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (flowType.value) params.flow_type = flowType.value
    if (status.value) params.status = status.value
    const res = await workflowsApi.list(params)
    workflows.value = res.data.data || []
  } finally {
    loading.value = false
  }
}

async function handlePublish(id: number) {
  try {
    await workflowsApi.publish(id)
    message.success('发布成功')
    fetchList()
  } catch {
    message.error('发布失败')
  }
}

async function handleDelete(id: number) {
  try {
    await workflowsApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch {
    message.error('删除失败')
  }
}

onMounted(fetchList)
</script>
