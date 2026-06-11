<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">应用管理</h1>
      <a-button type="primary" @click="$router.push('/apps/create')"><PlusOutlined /> 创建应用</a-button>
    </div>
    <a-table :dataSource="apps" :columns="columns" rowKey="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'api_key'">
          <span class="font-mono text-xs">{{ record.api_key }}</span>
          <a-button size="small" type="link" @click="copyKey(record.api_key)">复制</a-button>
        </template>
        <template v-if="column.key === 'enabled'">
          <a-tag :color="record.enabled ? 'green' : 'red'">{{ record.enabled ? '启用' : '禁用' }}</a-tag>
        </template>
        <template v-if="column.key === 'actions'">
          <a-button size="small" @click="$router.push(`/apps/${record.id}/edit`)">编辑</a-button>
          <a-button size="small" class="ml-1" @click="handleRotate(record.id)">轮换密钥</a-button>
          <a-popconfirm title="确定删除？" @confirm="handleDelete(record.id)">
            <a-button size="small" danger class="ml-1">删除</a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { appsApi } from '@/api/apps'

const apps = ref<any[]>([])
const loading = ref(false)

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '关联工作流', dataIndex: 'workflow_name', key: 'workflow' },
  { title: 'API Key', key: 'api_key' },
  { title: '限流(次/分)', dataIndex: 'rate_limit', key: 'rate' },
  { title: '状态', key: 'enabled' },
  { title: '操作', key: 'actions', width: 260 },
]

async function fetchList() {
  loading.value = true
  try {
    const res = await appsApi.list()
    apps.value = res.data.data || []
  } finally {
    loading.value = false
  }
}

function copyKey(key: string) {
  navigator.clipboard.writeText(key)
  message.success('已复制到剪贴板')
}

async function handleRotate(id: number) {
  const res = await appsApi.rotateKey(id)
  message.success('密钥已轮换: ' + res.data.data.api_key)
  fetchList()
}

async function handleDelete(id: number) {
  await appsApi.delete(id)
  message.success('已删除')
  fetchList()
}

onMounted(fetchList)
</script>
