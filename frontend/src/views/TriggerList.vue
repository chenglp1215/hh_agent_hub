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
          <span>{{ formatTime(record.last_fired_at) }}</span>
        </template>
        <template v-if="column.key === 'next_fire_at'">
          <span>{{ formatTime(record.next_fire_at) }}</span>
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button size="small" @click="$router.push(`/triggers/${record.id}/edit`)">编辑</a-button>
            <a-button size="small" @click="openHistoryDrawer(record)">历史</a-button>
            <a-button size="small" type="primary" ghost @click="handleExecute(record.id)">立即执行</a-button>
            <a-popconfirm title="确定删除此触发器？" @confirm="handleDelete(record.id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 执行历史 Drawer -->
    <a-drawer
      :title="`执行历史 - ${historyTrigger?.name || ''}`"
      :open="historyDrawerVisible"
      :width="720"
      @close="historyDrawerVisible = false"
    >
      <a-table
        :dataSource="executions"
        :columns="executionColumns"
        rowKey="id"
        :loading="executionsLoading"
        :pagination="executionsPagination"
        @change="handleExecutionTableChange"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'source'">
            <a-tag :color="record.source === 'auto' ? 'blue' : 'green'">
              {{ record.source === 'auto' ? '自动' : '手动' }}
            </a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'success' ? 'green' : record.status === 'failed' ? 'red' : 'orange'">
              {{ record.status === 'success' ? '成功' : record.status === 'failed' ? '失败' : '执行中' }}
            </a-tag>
          </template>
          <template v-if="column.key === 'duration_ms'">
            <span>{{ record.duration_ms != null ? `${record.duration_ms}ms` : '-' }}</span>
          </template>
          <template v-if="column.key === 'started_at'">
            <span>{{ formatTime(record.started_at) }}</span>
          </template>
          <template v-if="column.key === 'notified'">
            <a-tag :color="record.notified ? 'green' : 'default'">
              {{ record.notified ? '已通知' : '未通知' }}
            </a-tag>
          </template>
          <template v-if="column.key === 'actions'">
            <a-button size="small" type="link" @click="openChatLogModal(record.session_id)">
              查看对话
            </a-button>
          </template>
        </template>
      </a-table>
    </a-drawer>

    <!-- 对话内容 Modal -->
    <a-modal
      title="对话内容"
      :open="chatLogModalVisible"
      :footer="null"
      :width="700"
      @cancel="chatLogModalVisible = false"
    >
      <a-spin :spinning="chatLogLoading">
        <div v-if="chatLogMessages.length === 0" class="text-center text-gray-400 py-8">
          暂无对话记录
        </div>
        <div v-else class="chat-log-container">
          <div
            v-for="(msg, idx) in chatLogMessages"
            :key="idx"
            class="chat-log-item"
            :class="msg.role === 'user' ? 'chat-user' : 'chat-assistant'"
          >
            <div class="chat-role">{{ msg.role === 'user' ? '用户' : '助手' }}</div>
            <div class="chat-content">{{ msg.content }}</div>
          </div>
        </div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { formatTime } from '@/utils/time'
import { triggersApi } from '@/api/triggers'
import { chatLogsApi } from '@/api/chatLogs'

// --- 触发器列表 ---
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
  { title: '操作', key: 'actions', width: 360 },
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

// --- 执行历史 Drawer ---
const historyDrawerVisible = ref(false)
const historyTrigger = ref<any>(null)
const executions = ref<any[]>([])
const executionsLoading = ref(false)
const executionsPagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
})

const executionColumns = [
  { title: '会话ID', dataIndex: 'session_id', key: 'session_id', width: 200, ellipsis: true },
  { title: '来源', key: 'source', width: 80 },
  { title: '状态', key: 'status', width: 80 },
  { title: '耗时', key: 'duration_ms', width: 100 },
  { title: '开始时间', key: 'started_at', width: 170 },
  { title: '通知', key: 'notified', width: 80 },
  { title: '操作', key: 'actions', width: 100 },
]

async function openHistoryDrawer(record: any) {
  historyTrigger.value = record
  historyDrawerVisible.value = true
  executionsPagination.current = 1
  await fetchExecutions()
}

async function fetchExecutions() {
  if (!historyTrigger.value) return
  executionsLoading.value = true
  try {
    const res = await triggersApi.executions(historyTrigger.value.id, {
      page: executionsPagination.current,
      page_size: executionsPagination.pageSize,
    })
    const data = res.data.data || res.data || {}
    executions.value = data.items || []
    executionsPagination.total = data.total || 0
  } catch {
    message.error('加载执行历史失败')
  } finally {
    executionsLoading.value = false
  }
}

function handleExecutionTableChange(pagination: any) {
  executionsPagination.current = pagination.current
  executionsPagination.pageSize = pagination.pageSize
  fetchExecutions()
}

// --- 对话内容 Modal ---
const chatLogModalVisible = ref(false)
const chatLogLoading = ref(false)
const chatLogMessages = ref<Array<{ role: string; content: string }>>([])

async function openChatLogModal(sessionId: string) {
  chatLogModalVisible.value = true
  chatLogLoading.value = true
  chatLogMessages.value = []
  try {
    const res = await chatLogsApi.list({ session_id: sessionId })
    const logs = res.data.data || res.data || []
    // 提取 messages 内容
    const logList = Array.isArray(logs) ? logs : (logs.items || [])
    if (logList.length > 0 && logList[0].messages) {
      chatLogMessages.value = logList[0].messages
    } else if (logList.length > 0 && logList[0].content) {
      chatLogMessages.value = [{ role: 'assistant', content: logList[0].content }]
    }
  } catch {
    message.error('加载对话记录失败')
  } finally {
    chatLogLoading.value = false
  }
}

onMounted(fetchList)
</script>

<style scoped>
.chat-log-container {
  max-height: 500px;
  overflow-y: auto;
}
.chat-log-item {
  padding: 8px 12px;
  margin-bottom: 8px;
  border-radius: 6px;
}
.chat-user {
  background: rgba(94, 106, 210, 0.1);
  border: 1px solid rgba(94, 106, 210, 0.2);
}
.chat-assistant {
  background: rgba(0, 212, 255, 0.06);
  border: 1px solid rgba(0, 212, 255, 0.15);
}
.chat-role {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  margin-bottom: 4px;
  color: #8a8f98;
}
.chat-content {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: #c2c6cc;
}
</style>
