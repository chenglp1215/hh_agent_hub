<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">执行追踪</h1>
      <a-button @click="fetchList" :loading="loading">刷新</a-button>
    </div>

    <div class="mb-4 flex gap-4">
      <a-input-search v-model:value="search" placeholder="搜索 Execution ID..." class="max-w-xs" />
      <a-select v-model:value="statusFilter" class="w-32" @change="fetchList">
        <a-select-option value="">全部</a-select-option>
        <a-select-option value="running">运行中</a-select-option>
        <a-select-option value="success">成功</a-select-option>
        <a-select-option value="failed">失败</a-select-option>
      </a-select>
    </div>

    <a-table
      :dataSource="filteredTraces"
      :columns="columns"
      rowKey="id"
      :loading="loading"
      @row-click="(r: any) => $router.push(`/monitor/traces/${r.execution_id}`)"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <span class="inline-flex items-center gap-1">
            <span
              class="inline-block w-2 h-2 rounded-full"
              :class="statusColor(record.status)"
            />
            {{ statusLabel(record.status) }}
          </span>
        </template>
        <template v-if="column.key === 'time'">
          {{ formatTime(record.started_at) }}
        </template>
        <template v-if="column.key === 'duration'">
          {{ record.total_duration_ms ? `${(record.total_duration_ms / 1000).toFixed(1)}s` : '-' }}
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { tracesApi } from '@/api/traces'
import { formatTime } from '@/utils/time'

const traces = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const statusFilter = ref('')

const columns = [
  { title: 'Execution ID', dataIndex: 'execution_id', key: 'id' },
  { title: '状态', key: 'status', width: 100 },
  { title: 'Agent 数', dataIndex: 'agent_count', key: 'agents', width: 80 },
  { title: '耗时', key: 'duration', width: 80 },
  { title: '错误', dataIndex: 'error_summary', key: 'error' },
  { title: '时间', dataIndex: 'started_at', key: 'time', width: 180 },
]

const filteredTraces = computed(() => {
  if (search.value) {
    return traces.value.filter((t) => t.execution_id.includes(search.value))
  }
  return traces.value
})

function statusColor(s: string) {
  return (
    { running: 'bg-blue-500', success: 'bg-green-500', failed: 'bg-red-500' }[s] || 'bg-gray-500'
  )
}
function statusLabel(s: string) {
  return { running: '运行中', success: '成功', failed: '失败', partial: '部分完成' }[s] || s
}

async function fetchList() {
  loading.value = true
  try {
    const params: any = {}
    if (statusFilter.value) params.status = statusFilter.value
    const res = await tracesApi.list(params)
    traces.value = res.data.data || []
  } finally {
    loading.value = false
  }
}

onMounted(fetchList)
</script>
