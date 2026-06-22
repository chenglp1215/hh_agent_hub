<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">MCP Server 资源目录</h1>
      <div class="flex gap-2">
        <a-button :loading="testing" @click="handleBatchTest">
          <ReloadOutlined /> 测试全部连接
        </a-button>
        <a-button type="primary" @click="$router.push('/resources/mcp-servers/create')">
          <PlusOutlined /> 注册 Server
        </a-button>
      </div>
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
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-2">
                <a-tooltip :title="s.status === 'active' ? '连接正常' : '连接异常'">
                  <span class="inline-block w-2.5 h-2.5 rounded-full" :class="s.status === 'active' ? 'bg-green-500' : 'bg-red-500'" />
                </a-tooltip>
                <h3 class="text-lg font-semibold truncate">{{ s.display_name || s.name }}</h3>
              </div>
              <p class="text-gray-400 text-sm mb-1 truncate">{{ s.description || '暂无描述' }}</p>
              <p class="text-gray-500 text-xs mb-2">地址: {{ s.base_url }}</p>
              <!-- 工具列表：展示全部工具名称 -->
              <div v-if="(s.discovered_tools || []).length > 0" class="mb-1">
                <p class="text-gray-500 text-xs mb-1">工具 ({{ s.discovered_tools.length }}):</p>
                <div class="flex flex-wrap gap-1">
                  <a-tag
                    v-for="tool in s.discovered_tools"
                    :key="tool.name"
                    color="blue"
                    class="text-xs"
                  >{{ tool.name }}</a-tag>
                </div>
              </div>
              <p v-else class="text-gray-500 text-xs">暂未发现工具</p>
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
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { mcpServersApi } from '@/api/mcpServers'

const servers = ref<any[]>([])
const loading = ref(false)
const testing = ref(false)
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

/**
 * 自动测试所有服务器连接，并用结果更新 status 字段
 */
async function autoTestConnections() {
  if (servers.value.length === 0) return
  testing.value = true
  try {
    const res = await mcpServersApi.batchTest()
    const results: Array<{ id: number; status: string }> = res.data.data?.results || []
    // 将批量测试结果合并到现有 servers 数据中
    for (const r of results) {
      const s = servers.value.find((sv: any) => sv.id === r.id)
      if (s) s.status = r.status
    }
  } catch {
    // 静默处理：自动测试失败不影响页面展示
    console.warn('[MCP] 自动连接测试失败')
  } finally {
    testing.value = false
  }
}

async function handleBatchTest() {
  testing.value = true
  try {
    const res = await mcpServersApi.batchTest()
    const results: Array<{ id: number; name: string; connected: boolean }> = res.data.data?.results || []
    // 更新本地服务器的 status
    for (const r of results) {
      const s = servers.value.find((sv: any) => sv.id === r.id)
      if (s) s.status = r.connected ? 'active' : 'error'
    }
    const total = results.length
    const ok = results.filter(r => r.connected).length
    message.success(`连接测试完成: ${ok}/${total} 在线`)
  } catch {
    message.error('批量测试失败')
  } finally {
    testing.value = false
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
    const d = res.data.data
    if (d.connected) {
      s.status = 'active'
      message.success(`${s.display_name || s.name} 连接成功`)
    } else {
      s.status = 'error'
      message.error(`${s.display_name || s.name} 连接失败: ${d.error || '未知错误'}`)
    }
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

onMounted(async () => {
  await fetchList()
  // 页面加载后自动进行连接测试
  await autoTestConnections()
})
</script>
