<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">Claude Settings 管理</h1>
      <a-button type="primary" @click="$router.push('/claude-settings/create')">
        <PlusOutlined /> 新建配置
      </a-button>
    </div>

    <div class="mb-4 flex gap-4 flex-wrap">
      <a-input-search v-model:value="search" placeholder="搜索名称或显示名..." class="max-w-xs" @search="fetchList" />
    </div>

    <a-spin :spinning="loading">
      <a-table :dataSource="filteredSettings" :columns="columns" rowKey="id" :pagination="{ pageSize: 10 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'permission_mode'">
            <a-tag color="#5e6ad2">{{ record.permission_mode }}</a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'active' ? 'green' : 'default'">
              {{ record.status === 'active' ? '启用' : '禁用' }}
            </a-tag>
          </template>
          <template v-if="column.key === 'created_at'">
            <span class="text-xs">{{ formatTime(record.created_at) }}</span>
          </template>
          <template v-if="column.key === 'actions'">
            <a-button size="small" @click="$router.push(`/claude-settings/${record.id}/edit`)">编辑</a-button>
            <a-popconfirm title="确定删除此配置？" @confirm="handleDelete(record.id)">
              <a-button size="small" danger class="ml-2">删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
      <a-empty v-if="!loading && filteredSettings.length === 0" description="暂无 Claude Settings" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { claudeSettingsApi } from '@/api/claudeSettings'
import { formatTime } from '@/utils/time'

const settings = ref<any[]>([])
const loading = ref(false)
const search = ref('')

const columns = [
  { title: '显示名称', dataIndex: 'display_name', key: 'name' },
  { title: '标识', dataIndex: 'name', key: 'key' },
  { title: '模型', dataIndex: 'model', key: 'model' },
  { title: '最大轮次', dataIndex: 'max_turns', key: 'max_turns', width: 100 },
  { title: '权限模式', key: 'permission_mode', width: 130 },
  { title: '状态', key: 'status', width: 80 },
  { title: '创建时间', key: 'created_at', width: 160 },
  { title: '操作', key: 'actions', width: 140 },
]

const filteredSettings = computed(() => {
  let list = settings.value
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(s => (s.name + (s.display_name || '')).toLowerCase().includes(q))
  }
  return list
})

async function fetchList() {
  loading.value = true
  try {
    const params: any = {}
    if (search.value) params.search = search.value
    const res = await claudeSettingsApi.list(params)
    settings.value = res.data.data || []
  } catch {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await claudeSettingsApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch {
    message.error('删除失败')
  }
}

onMounted(fetchList)
</script>
