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
          <a-button size="small" class="ml-1" type="link" @click="openApiDoc(record)">API 文档</a-button>
          <a-popconfirm title="确定删除？" @confirm="handleDelete(record.id)">
            <a-button size="small" danger class="ml-1">删除</a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <!-- API 文档弹窗 -->
    <a-modal
      v-model:open="apiDocOpen"
      title="API 文档 - 触发应用对话"
      :footer="null"
      width="680px"
    >
      <template v-if="selectedApp">
        <div class="mb-4">
          <h4 class="text-base font-semibold mb-2">应用信息</h4>
          <div class="text-sm text-gray-500">
            <span>名称：{{ selectedApp.name }}</span>
            <span class="ml-6">API Key：<code class="bg-gray-100 px-1 rounded text-xs">{{ selectedApp.api_key }}</code></span>
          </div>
        </div>

        <a-divider />

        <div class="mb-4">
          <h4 class="text-base font-semibold mb-2">接口信息</h4>
          <a-descriptions :column="1" size="small" bordered>
            <a-descriptions-item label="请求方式"><a-tag color="green">POST</a-tag></a-descriptions-item>
            <a-descriptions-item label="接口路径"><code>/api/v1/chat</code></a-descriptions-item>
            <a-descriptions-item label="认证方式"><code>X-API-Key</code> 请求头 或 <code>Authorization: Bearer &lt;key&gt;</code></a-descriptions-item>
            <a-descriptions-item label="Content-Type"><code>application/json</code></a-descriptions-item>
            <a-descriptions-item label="流式响应">设置 <code>stream: true</code> 启用 SSE 流式输出</a-descriptions-item>
          </a-descriptions>
        </div>

        <a-divider />

        <div class="mb-4">
          <h4 class="text-base font-semibold mb-2">请求参数</h4>
          <a-table
            :dataSource="paramColumns"
            :columns="apiParamTableColumns"
            rowKey="name"
            size="small"
            :pagination="false"
            bordered
          />
        </div>

        <a-divider />

        <div class="mb-4">
          <h4 class="text-base font-semibold mb-2">响应字段（非流式）</h4>
          <a-table
            :dataSource="responseFields"
            :columns="apiParamTableColumns"
            rowKey="name"
            size="small"
            :pagination="false"
            bordered
          />
        </div>

        <a-divider />

        <div class="mb-4">
          <h4 class="text-base font-semibold mb-2">请求示例</h4>
          <div class="relative">
            <a-button size="small" class="absolute top-2 right-2 z-10" @click="copyExample(selectedApp.api_key)">复制</a-button>
            <pre class="bg-gray-900 text-green-400 p-4 rounded text-xs overflow-x-auto"><code>{{ buildCurlExample(selectedApp.api_key) }}</code></pre>
          </div>
        </div>

        <a-divider />

        <div>
          <h4 class="text-base font-semibold mb-2">响应示例（非流式）</h4>
          <pre class="bg-gray-900 text-green-400 p-4 rounded text-xs overflow-x-auto"><code>{
  "code": 0,
  "message": "success",
  "data": {
    "session_id": "uuid-string",
    "message": "这是 AI 返回的回复内容...",
    "intermediate_results": {
      "AgentName": "该 Agent 的中间输出"
    },
    "duration_ms": 1234,
    "trace": [...]
  }
}</code></pre>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { appsApi } from '@/api/apps'

const apps = ref<any[]>([])
const loading = ref(false)
const apiDocOpen = ref(false)
const selectedApp = ref<any>(null)

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '关联工作流', dataIndex: 'workflow_name', key: 'workflow' },
  { title: 'API Key', key: 'api_key' },
  { title: '限流(次/分)', dataIndex: 'rate_limit', key: 'rate' },
  { title: '状态', key: 'enabled' },
  { title: '操作', key: 'actions', width: 330 },
]

const paramColumns = [
  { name: 'app_id', type: 'int', required: '是', description: '应用的 ID（与 API Key 二选一认证）' },
  { name: 'message', type: 'string', required: '是', description: '用户发送的消息内容' },
  { name: 'session_id', type: 'string (UUID)', required: '否', description: '会话 ID，不传则自动创建新会话' },
  { name: 'stream', type: 'boolean', required: '否', description: '是否启用 SSE 流式响应，默认 false' },
]

const responseFields = [
  { name: 'code', type: 'int', required: '-', description: '状态码，0 表示成功' },
  { name: 'message', type: 'string', required: '-', description: '状态描述' },
  { name: 'data.session_id', type: 'string', required: '-', description: '会话 ID，可用于后续查询历史' },
  { name: 'data.message', type: 'string', required: '-', description: 'AI 最终回复内容' },
  { name: 'data.intermediate_results', type: 'object', required: '-', description: '各 Agent 中间输出，key 为 Agent 名称' },
  { name: 'data.duration_ms', type: 'int', required: '-', description: '执行耗时（毫秒）' },
  { name: 'data.trace', type: 'array', required: '-', description: '执行追踪链路' },
]

const apiParamTableColumns = [
  { title: '字段名', dataIndex: 'name', key: 'name', width: 160 },
  { title: '类型', dataIndex: 'type', key: 'type', width: 120 },
  { title: '必填', dataIndex: 'required', key: 'required', width: 60 },
  { title: '说明', dataIndex: 'description', key: 'description' },
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

function openApiDoc(app: any) {
  selectedApp.value = app
  apiDocOpen.value = true
}

function buildCurlExample(apiKey: string) {
  return `curl -X POST "${window.location.origin}/api/v1/chat" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ${apiKey}" \\
  -d '{
    "app_id": ${selectedApp.value?.id},
    "message": "你好，请帮我...",
    "stream": false
  }'`
}

function copyExample(apiKey: string) {
  navigator.clipboard.writeText(buildCurlExample(apiKey))
  message.success('已复制到剪贴板')
}

onMounted(fetchList)
</script>
