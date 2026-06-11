<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">MCP Server 资源目录</h1>
      <a-button type="primary" @click="$router.push('/resources/mcp-servers/create')">
        <PlusOutlined /> 注册 Server
      </a-button>
    </div>

    <div class="mb-4 flex gap-4">
      <a-input-search v-model:value="search" placeholder="搜索名称或地址..." class="max-w-xs" @search="fetchList" />
      <a-select v-model:value="statusFilter" class="w-32" @change="fetchList">
        <a-select-option value="">全部状态</a-select-option>
        <a-select-option value="active">在线</a-select-option>
        <a-select-option value="error">异常</a-select-option>
        <a-select-option value="disabled">已禁用</a-select-option>
      </a-select>
    </div>

    <a-spin :spinning="loading">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <a-card v-for="s in filteredServers" :key="s.id" class="hover:border-[#5e6ad2] transition-colors">
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-2">
                <span class="inline-block w-2 h-2 rounded-full" :class="s.status === 'active' ? 'bg-green-500' : 'bg-red-500'" />
                <h3 class="text-lg font-semibold">{{ s.display_name || s.name }}</h3>
              </div>
              <p class="text-gray-400 text-sm mb-1">{{ s.description }}</p>
              <p class="text-gray-500 text-xs">地址: {{ s.base_url }}</p>
              <p class="text-gray-500 text-xs">工具: {{ (s.discovered_tools || []).length }} 个</p>
            </div>
          </div>
          <template #actions>
            <a-button size="small" @click="handleDiscover(s)">发现工具</a-button>
            <a-button size="small" @click="handleTest(s)">测试连接</a-button>
            <a-button size="small" @click="$router.push(`/resources/mcp-servers/${s.id}/edit`)">编辑</a-button>
            <a-popconfirm title="确定删除？" @confirm="handleDelete(s.id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </a-card>
      </div>
      <a-empty v-if="!loading && filteredServers.length === 0" description="暂无 MCP Server" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { mcpServersApi } from '@/api/mcpServers'

const servers = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const statusFilter = ref('')

const filteredServers = computed(() => {
  let list = servers.value
  if (statusFilter.value) list = list.filter(s => s.status === statusFilter.value)
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(s => (s.name + s.display_name + s.base_url).toLowerCase().includes(q))
  }
  return list
})

async function fetchList() {
  loading.value = true
  try {
    const res = await mcpServersApi.list()
    servers.value = res.data.data || []
  } catch {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleDiscover(s: any) {
  try {
    const res = await mcpServersApi.discover(s.id)
    message.success(res.data.message)
    fetchList()
  } catch {
    message.error('工具发现失败')
  }
}

async function handleTest(s: any) {
  try {
    const res = await mcpServersApi.test(s.id)
    message.success(res.data.data.connected ? '连接成功' : '连接失败: ' + res.data.data.error)
  } catch {
    message.error('测试失败')
  }
}

async function handleDelete(id: number) {
  try {
    await mcpServersApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch {
    message.error('删除失败')
  }
}

onMounted(fetchList)
</script>
