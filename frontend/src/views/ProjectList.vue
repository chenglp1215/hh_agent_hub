<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">项目管理</h1>
      <a-button type="primary" @click="$router.push('/projects/create')">
        <PlusOutlined /> 新建项目
      </a-button>
    </div>

    <div class="mb-4 flex gap-4 flex-wrap">
      <a-input-search v-model:value="search" placeholder="搜索名称或仓库 URL..." class="max-w-xs" @search="fetchList" />
      <a-select v-model:value="statusFilter" class="w-32" allow-clear @change="fetchList">
        <a-select-option value="">全部状态</a-select-option>
        <a-select-option value="active">启用</a-select-option>
        <a-select-option value="disabled">禁用</a-select-option>
      </a-select>
    </div>

    <a-spin :spinning="loading">
      <a-table :dataSource="filteredProjects" :columns="columns" rowKey="id" :pagination="{ pageSize: 10 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'active' ? 'green' : 'default'">
              {{ record.status === 'active' ? '启用' : '禁用' }}
            </a-tag>
          </template>
          <template v-if="column.key === 'git_url'">
            <span class="text-xs font-mono">{{ record.git_repo_url }}</span>
          </template>
          <template v-if="column.key === 'created_at'">
            <span class="text-xs">{{ record.created_at?.slice(0, 19).replace('T', ' ') }}</span>
          </template>
          <template v-if="column.key === 'actions'">
            <a-button size="small" @click="$router.push(`/projects/${record.id}/edit`)">编辑</a-button>
            <a-popconfirm title="确定删除此项目？" @confirm="handleDelete(record.id)">
              <a-button size="small" danger class="ml-2">删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
      <a-empty v-if="!loading && filteredProjects.length === 0" description="暂无项目" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { projectsApi } from '@/api/projects'

const projects = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const statusFilter = ref('')

const columns = [
  { title: '名称', dataIndex: 'display_name', key: 'name' },
  { title: '标识', dataIndex: 'name', key: 'key' },
  { title: '仓库 URL', key: 'git_url' },
  { title: '分支', dataIndex: 'git_branch', key: 'branch' },
  { title: '状态', key: 'status', width: 80 },
  { title: '创建时间', key: 'created_at', width: 160 },
  { title: '操作', key: 'actions', width: 140 },
]

const filteredProjects = computed(() => {
  let list = projects.value
  if (statusFilter.value) list = list.filter(p => p.status === statusFilter.value)
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(p => (p.name + (p.display_name || '') + p.git_repo_url).toLowerCase().includes(q))
  }
  return list
})

async function fetchList() {
  loading.value = true
  try {
    const params: any = {}
    if (statusFilter.value) params.status = statusFilter.value
    if (search.value) params.search = search.value
    const res = await projectsApi.list(params)
    projects.value = res.data.data || []
  } catch {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await projectsApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch {
    message.error('删除失败')
  }
}

onMounted(fetchList)
</script>
