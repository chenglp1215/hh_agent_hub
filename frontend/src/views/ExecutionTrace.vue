<template>
  <div>
    <div class="flex items-center gap-4 mb-6">
      <a-button @click="$router.back()">返回</a-button>
      <h1 class="text-2xl font-bold">追踪详情</h1>
      <a-tag v-if="metadata" :color="statusColor(metadata.status)">{{
        statusLabel(metadata.status)
      }}</a-tag>
      <span v-if="metadata" class="text-gray-400 text-sm">
        耗时: {{ (metadata.total_duration_ms / 1000).toFixed(1) }}s | Agent 数:
        {{ metadata.agent_count }}
      </span>
    </div>

    <a-spin :spinning="loading">
      <a-card v-if="metadata" class="mb-4">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span class="text-gray-400">Execution ID:</span> {{ metadata.execution_id }}
          </div>
          <div>
            <span class="text-gray-400">状态:</span> {{ statusLabel(metadata.status) }}
          </div>
          <div>
            <span class="text-gray-400">开始:</span> {{ metadata.started_at }}
          </div>
          <div>
            <span class="text-gray-400">完成:</span> {{ metadata.completed_at || '-' }}
          </div>
        </div>
      </a-card>

      <a-card title="执行时间轴" v-if="traceTree?.spans">
        <div class="space-y-4">
          <div
            v-for="span in traceTree.spans"
            :key="span.span_id"
            class="border border-[#1e1e20] rounded p-3"
          >
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                <span
                  class="inline-block w-2 h-2 rounded-full"
                  :class="span.status === 'success' ? 'bg-green-500' : 'bg-red-500'"
                />
                <span class="font-medium">{{ span.agent_name }}</span>
                <a-tag>{{ span.agent_type }}</a-tag>
              </div>
              <span class="text-xs text-gray-400">{{ span.duration_ms }}ms</span>
            </div>
            <div v-if="span.summary" class="text-xs text-gray-400 mb-2">
              {{ span.summary }}
            </div>
            <div
              v-if="span.children?.length"
              class="ml-4 space-y-1 border-l border-[#1e1e20] pl-3"
            >
              <div
                v-for="child in span.children"
                :key="child.span_id"
                class="flex items-center gap-2 text-xs py-1"
              >
                <span class="text-gray-500">{{
                  child.type === 'llm_call' ? '💬' : child.type === 'tool_call' ? '🔧' : '🔍'
                }}</span>
                <span>{{
                  child.model || child.tool_name || child.query?.slice(0, 30)
                }}</span>
                <span class="text-gray-500 ml-auto">{{ child.duration_ms }}ms</span>
              </div>
            </div>
          </div>
        </div>
      </a-card>
      <a-empty v-else-if="!loading" description="无追踪数据" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { tracesApi } from '@/api/traces'
import { createWSConnection } from '@/utils/ws'

const route = useRoute()
const executionId = route.params.executionId as string
const metadata = ref<any>(null)
const traceTree = ref<any>(null)
const loading = ref(false)
let ws: WebSocket | null = null

function statusColor(s: string) {
  return { running: 'blue', success: 'green', failed: 'red' }[s] || 'default'
}
function statusLabel(s: string) {
  return { running: '运行中', success: '成功', failed: '失败' }[s] || s
}

async function fetchTrace() {
  loading.value = true
  try {
    const res = await tracesApi.get(executionId)
    metadata.value = res.data.data.metadata
    traceTree.value = res.data.data.trace_tree
  } catch {
    // handle error silently
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchTrace()
  try {
    ws = createWSConnection(executionId, (event) => {
      if (event.type === 'trace_update') {
        traceTree.value = event.trace
      } else if (event.type === 'execution_completed') {
        metadata.value = {
          ...metadata.value,
          status: event.status,
          total_duration_ms: event.total_duration_ms,
          completed_at: new Date().toISOString(),
        }
        ws?.close()
      }
    })
  } catch {
    // WebSocket connection failed, page works with HTTP data only
  }
})

onUnmounted(() => {
  ws?.close()
})
</script>
