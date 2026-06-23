<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">通知管理</h1>
      <a-button type="primary" @click="$router.push('/notifications/create')">
        <PlusOutlined /> 创建通知渠道
      </a-button>
    </div>

    <a-table :dataSource="notifications" :columns="columns" rowKey="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'channel_type'">
          <a-tag color="blue">{{ record.channel_type }}</a-tag>
        </template>
        <template v-if="column.key === 'webhook_url'">
          <a-tooltip :title="record.webhook_url">
            <span class="text-sm truncate inline-block max-w-[300px] align-middle">{{ record.webhook_url }}</span>
          </a-tooltip>
        </template>
        <template v-if="column.key === 'enabled'">
          <a-switch
            :checked="record.enabled"
            @change="(checked: boolean) => handleToggleEnabled(record, checked)"
          />
        </template>
        <template v-if="column.key === 'created_at'">
          <span>{{ formatTime(record.created_at) }}</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button size="small" @click="$router.push(`/notifications/${record.id}/edit`)">编辑</a-button>
            <a-popconfirm title="确定删除此通知渠道？" @confirm="handleDelete(record.id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { notificationsApi } from '@/api/notifications'
import { formatTime } from '@/utils/time'

const notifications = ref<any[]>([])
const loading = ref(false)

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '渠道类型', key: 'channel_type', width: 140 },
  { title: 'Webhook URL', key: 'webhook_url' },
  { title: '状态', key: 'enabled', width: 80 },
  { title: '创建时间', key: 'created_at', width: 180 },
  { title: '操作', key: 'actions', width: 160 },
]

async function fetchList() {
  loading.value = true
  try {
    const res = await notificationsApi.list()
    notifications.value = res.data.data || []
  } catch {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleToggleEnabled(record: any, checked: boolean) {
  try {
    await notificationsApi.update(record.id, { enabled: checked })
    message.success(checked ? '已启用' : '已禁用')
    fetchList()
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  }
}

async function handleDelete(id: number) {
  try {
    await notificationsApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch (e: any) {
    message.error(e.response?.data?.message || '删除失败')
  }
}

onMounted(fetchList)
</script>
