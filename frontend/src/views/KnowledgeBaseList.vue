<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">知识库管理</h1>
      <a-button type="primary" @click="$router.push('/resources/knowledge-bases/create')">
        <PlusOutlined /> 创建知识库
      </a-button>
    </div>

    <div class="mb-4 flex gap-4">
      <a-input-search v-model:value="search" placeholder="搜索..." class="max-w-xs" />
      <a-select v-model:value="typeFilter" class="w-32">
        <a-select-option value="">全部类型</a-select-option>
        <a-select-option value="file">文件</a-select-option>
        <a-select-option value="url">URL</a-select-option>
        <a-select-option value="rag">RAG</a-select-option>
      </a-select>
    </div>

    <a-spin :spinning="loading">
      <a-table :dataSource="filteredKbs" :columns="columns" rowKey="id" :pagination="{ pageSize: 10 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'active' ? 'green' : 'red'">{{ record.status }}</a-tag>
          </template>
          <template v-if="column.key === 'actions'">
            <a-button size="small" @click="handleSync(record.id)">同步</a-button>
            <a-button size="small" class="ml-1" @click="$router.push(`/resources/knowledge-bases/${record.id}/edit`)">编辑</a-button>
            <a-popconfirm title="确定删除？" @confirm="handleDelete(record.id)">
              <a-button size="small" danger class="ml-1">删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { knowledgeBasesApi } from '@/api/knowledgeBases'

const kbs = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const typeFilter = ref('')

const columns = [
  { title: '名称', dataIndex: 'display_name', key: 'name' },
  { title: '标识', dataIndex: 'name', key: 'key' },
  { title: '类型', dataIndex: 'kb_type', key: 'type' },
  { title: '文档数', dataIndex: 'document_count', key: 'docs' },
  { title: '状态', key: 'status' },
  { title: '操作', key: 'actions', width: 240 },
]

const filteredKbs = computed(() => {
  let list = kbs.value
  if (typeFilter.value) list = list.filter(k => k.kb_type === typeFilter.value)
  if (search.value) list = list.filter(k => (k.name + k.display_name).toLowerCase().includes(search.value.toLowerCase()))
  return list
})

async function fetchList() {
  loading.value = true
  try {
    const res = await knowledgeBasesApi.list()
    kbs.value = res.data.data || []
  } finally { loading.value = false }
}

async function handleSync(id: number) {
  try {
    const res = await knowledgeBasesApi.sync(id)
    message.success(res.data.message)
    fetchList()
  } catch {
    message.error('同步失败')
  }
}

async function handleDelete(id: number) {
  try {
    await knowledgeBasesApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch {
    message.error('删除失败')
  }
}

onMounted(fetchList)
</script>
