<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">触发器管理</h1>
      <a-button type="primary" @click="$router.push('/triggers/create')">
        <PlusOutlined /> 创建触发器
      </a-button>
    </div>

    <a-table :dataSource="triggers" :columns="columns" rowKey="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'trigger_type'">
          <a-tag :color="record.trigger_type === 'cron' ? 'blue' : 'green'">
            {{ record.trigger_type === 'cron' ? 'Cron' : '间隔' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'schedule'">
          <span v-if="record.trigger_type === 'interval'" class="text-sm">
            每 {{ record.interval_value }}
            {{ record.interval_unit === 'minutes' ? '分钟' : record.interval_unit === 'hours' ? '小时' : '天' }}
          </span>
          <code v-else class="text-xs px-1 py-0.5 rounded" style="background: #1a1a1c; color: #5e6ad2">
            {{ record.cron_expression }}
          </code>
        </template>
        <template v-if="column.key === 'enabled'">
          <a-switch
            :checked="record.enabled"
            @change="(checked: boolean) => handleToggleEnabled(record, checked)"
          />
        </template>
        <template v-if="column.key === 'message'">
          <a-tooltip :title="record.message">
            <span class="text-sm truncate inline-block max-w-[200px] align-middle">{{ record.message }}</span>
          </a-tooltip>
        </template>
        <template v-if="column.key === 'last_fired_at'">
          <span>{{ record.last_fired_at || '-' }}</span>
        </template>
        <template v-if="column.key === 'next_fire_at'">
          <span>{{ record.next_fire_at || '-' }}</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button size="small" @click="$router.push(`/triggers/${record.id}/edit`)">编辑</a-button>
            <a-button size="small" type="primary" ghost @click="handleExecute(record.id)">立即执行</a-button>
            <a-popconfirm title="确定删除此触发器？" @confirm="handleDelete(record.id)">
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
import { triggersApi } from '@/api/triggers'

const triggers = ref<any[]>([])
const loading = ref(false)

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '类型', key: 'trigger_type', width: 80 },
  { title: '调度配置', key: 'schedule' },
  { title: '关联应用', key: 'app_name' },
  { title: '触发消息', key: 'message' },
  { title: '状态', key: 'enabled', width: 80 },
  { title: '上次触发', key: 'last_fired_at' },
  { title: '下次触发', key: 'next_fire_at' },
  { title: '操作', key: 'actions', width: 280 },
]

async function fetchList() {
  loading.value = true
  try {
    const res = await triggersApi.list()
    triggers.value = res.data.data || []
  } finally {
    loading.value = false
  }
}

async function handleToggleEnabled(record: any, checked: boolean) {
  try {
    await triggersApi.update(record.id, { enabled: checked })
    message.success(checked ? '已启用' : '已禁用')
    fetchList()
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  }
}

async function handleExecute(id: number) {
  try {
    await triggersApi.execute(id)
    message.success('已触发执行')
  } catch (e: any) {
    message.error(e.response?.data?.message || '执行失败')
  }
}

async function handleDelete(id: number) {
  try {
    await triggersApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch (e: any) {
    message.error(e.response?.data?.message || '删除失败')
  }
}

onMounted(fetchList)
</script>
