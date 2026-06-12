<template>
  <div class="flex flex-col h-full">
    <div class="flex-1 overflow-y-auto p-4 space-y-4">
      <div v-for="(msg, i) in messages" :key="i" :class="msg.role === 'user' ? 'text-right' : 'text-left'">
        <div
          :class="
            msg.role === 'user'
              ? 'bg-[#5e6ad2] ml-auto'
              : 'bg-[#1a1a1c] mr-auto'
          "
          class="inline-block max-w-[80%] px-4 py-2 rounded-lg text-sm"
        >
          <div v-if="msg.type === 'thinking'" class="text-yellow-400 italic">
            &#x1f4ad; {{ msg.content }}
          </div>
          <div v-else-if="msg.type === 'agent_call'" class="text-blue-400">
            &#x1f504; 调用 {{ msg.agent }}...
          </div>
          <div v-else-if="msg.type === 'agent_result'" class="text-green-400">
            <div class="text-xs text-gray-400">{{ msg.agent }} 返回:</div>
            <div class="text-xs mt-1 max-h-32 overflow-y-auto">{{ msg.output }}</div>
          </div>
          <div v-else>{{ msg.content }}</div>
        </div>
      </div>
      <div v-if="streaming" class="text-gray-500 text-xs">...</div>
    </div>
    <div class="p-4 border-t border-[#1e1e20]">
      <div class="flex gap-2">
        <a-textarea
          v-model:value="inputText"
          :rows="1"
          placeholder="输入消息..."
          @pressEnter="handleSend"
          class="flex-1"
        />
        <a-button type="primary" :disabled="!inputText.trim() || streaming" @click="handleSend">
          发送
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ appId: number; apiKey: string }>()
const messages = ref<any[]>([])
const inputText = ref('')
const streaming = ref(false)

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || streaming.value) return

  messages.value.push({ role: 'user', content: text, type: 'text' })
  inputText.value = ''
  streaming.value = true

  try {
    const { createSSEConnection } = await import('@/utils/sse')
    const headers: Record<string, string> = {}
    if (props.apiKey) headers['X-API-Key'] = props.apiKey
    createSSEConnection(
      '/api/v1/chat',
      { app_id: props.appId, message: text, stream: true },
      (event, data) => {
        if (event === 'thinking') {
          messages.value.push({
            role: 'assistant',
            type: 'thinking',
            content: data.content,
          })
        } else if (event === 'agent_call') {
          messages.value.push({
            role: 'assistant',
            type: 'agent_call',
            agent: data.agent,
          })
        } else if (event === 'agent_result') {
          messages.value.push({
            role: 'assistant',
            type: 'agent_result',
            agent: data.agent,
            output: data.output,
          })
        } else if (event === 'text') {
          const last = messages.value[messages.value.length - 1]
          if (last?.type === 'text' && last.role === 'assistant') {
            last.content = data.content
          } else {
            messages.value.push({
              role: 'assistant',
              type: 'text',
              content: data.content,
            })
          }
        } else if (event === 'done') {
          streaming.value = false
        }
      },
      headers,
    )
  } catch {
    streaming.value = false
  }
}
</script>
