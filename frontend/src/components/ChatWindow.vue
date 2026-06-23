<template>
  <div class="flex flex-col h-full chat-window">
    <!-- Messages area -->
    <div class="flex-1 overflow-y-auto p-4 space-y-3" ref="msgContainer">
      <div
        v-for="(msg, i) in messages"
        :key="i"
        :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'"
        :style="{ animation: `fade-in-up 0.3s ${i * 0.02}s var(--ease-out) both` }"
      >
        <!-- User message -->
        <div
          v-if="msg.role === 'user'"
          class="msg-bubble msg-user"
        >
          <div class="markdown-body" v-html="renderMd(msg.content)" />
        </div>

        <!-- Thinking -->
        <div
          v-else-if="msg.type === 'thinking'"
          class="msg-bubble msg-thinking"
        >
          <span class="thinking-icon">&#x25C9;</span>
          <span class="italic text-[#f0a500] text-xs">{{ msg.content }}</span>
        </div>

        <!-- Agent call -->
        <div
          v-else-if="msg.type === 'agent_call'"
          class="msg-bubble msg-agent-call"
        >
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-[#00d4ff] animate-pulse" />
            <span class="text-xs text-[#00d4ff] font-medium">调用 {{ msg.agent }}...</span>
          </div>
        </div>

        <!-- Agent result -->
        <div
          v-else-if="msg.type === 'agent_result'"
          class="msg-bubble msg-agent-result"
        >
          <div class="text-xs text-[#535b6e] mb-1 font-medium">{{ msg.agent }} 返回:</div>
          <div class="text-xs max-h-32 overflow-y-auto markdown-body opacity-80" v-html="renderMd(msg.output)" />
        </div>

        <!-- Tool call -->
        <div
          v-else-if="msg.type === 'tool_call'"
          class="msg-bubble msg-tool"
        >
          <span class="text-xs text-[#7c5cfc] font-mono">&#x2699; {{ msg.tool }}({{ msg.args }})</span>
        </div>

        <!-- Tool result -->
        <div
          v-else-if="msg.type === 'tool_result'"
          class="msg-bubble msg-tool"
        >
          <div class="text-xs text-[#535b6e] font-mono">{{ msg.tool }} &rarr;</div>
          <div class="text-xs mt-1 max-h-24 overflow-y-auto font-mono opacity-70">{{ msg.result }}</div>
        </div>

        <!-- Assistant text -->
        <div
          v-else-if="msg.type === 'text'"
          class="msg-bubble msg-assistant"
        >
          <div class="markdown-body" v-html="renderMd(msg.content)" />
        </div>

        <!-- Fallback -->
        <div v-else class="msg-bubble msg-assistant">
          {{ msg.content }}
        </div>
      </div>

      <!-- Streaming indicator -->
      <div v-if="streaming" class="flex justify-start">
        <div class="msg-bubble msg-assistant">
          <div class="typing-indicator">
            <span /><span /><span />
          </div>
        </div>
      </div>
    </div>

    <!-- Input area -->
    <div class="input-area">
      <div class="flex gap-2">
        <a-textarea
          v-model:value="inputText"
          :rows="1"
          placeholder="输入消息，Enter 发送..."
          @pressEnter="handleSend"
          class="chat-input"
          :autoSize="{ minRows: 1, maxRows: 4 }"
        />
        <a-button
          type="primary"
          :disabled="!inputText.trim() || streaming"
          @click="handleSend"
          class="send-btn"
        >
          <SendOutlined v-if="!streaming" />
          <span v-else class="loading-dot" />
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { marked } from 'marked'
import { SendOutlined } from '@ant-design/icons-vue'

marked.setOptions({ breaks: true, gfm: true })

function renderMd(text: string): string {
  if (!text) return ''
  try {
    return marked.parse(text) as string
  } catch {
    return text.replace(/</g, '&lt;')
  }
}

const props = defineProps<{
  appId: number
  apiKey: string
  sessionId?: string
  initialMessages?: any[]
}>()
const emit = defineEmits<{
  (e: 'update:sessionId', value: string): void
}>()
const messages = ref<any[]>(props.initialMessages || [])
const inputText = ref('')
const streaming = ref(false)
const msgContainer = ref<HTMLDivElement>()
const currentSessionId = ref<string | undefined>(props.sessionId)

watch(() => props.sessionId, (val) => {
  currentSessionId.value = val
})

watch(() => messages.value.length, async () => {
  await nextTick()
  if (msgContainer.value) {
    msgContainer.value.scrollTop = msgContainer.value.scrollHeight
  }
})

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
    const body: Record<string, any> = { app_id: props.appId, message: text, stream: true }
    if (currentSessionId.value) body.session_id = currentSessionId.value
    createSSEConnection(
      '/api/v1/chat',
      body,
      (event, data) => {
        if (event === 'thinking') {
          messages.value.push({ role: 'assistant', type: 'thinking', content: data.content })
        } else if (event === 'agent_call') {
          messages.value.push({ role: 'assistant', type: 'agent_call', agent: data.agent })
        } else if (event === 'agent_result') {
          messages.value.push({ role: 'assistant', type: 'agent_result', agent: data.agent, output: data.output })
        } else if (event === 'tool_call') {
          messages.value.push({ role: 'assistant', type: 'tool_call', tool: data.tool, args: data.args })
        } else if (event === 'tool_result') {
          messages.value.push({ role: 'assistant', type: 'tool_result', tool: data.tool, result: data.result })
        } else if (event === 'text') {
          const last = messages.value[messages.value.length - 1]
          if (last?.type === 'text' && last.role === 'assistant') {
            last.content = data.content
          } else {
            messages.value.push({ role: 'assistant', type: 'text', content: data.content })
          }
        } else if (event === 'done') {
          streaming.value = false
          if (data.session_id) {
            currentSessionId.value = data.session_id
            emit('update:sessionId', data.session_id)
          }
        }
      },
      headers,
    )
  } catch {
    streaming.value = false
  }
}
</script>

<style scoped>
.chat-window {
  background: transparent;
}

/* Message bubbles */
.msg-bubble {
  max-width: 82%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.55;
  word-break: break-word;
  color: #e4e7ee;
}

.msg-user {
  background: linear-gradient(135deg, #00b8e0, #0080c0);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 2px 12px rgba(0, 180, 224, 0.25);
}

.msg-assistant {
  background: linear-gradient(135deg, rgba(17, 22, 36, 0.9), rgba(12, 16, 27, 0.85));
  border: 1px solid var(--border-subtle);
  color: #e4e7ee;
  border-bottom-left-radius: 4px;
  backdrop-filter: blur(12px);
}

.msg-thinking {
  background: rgba(240, 165, 0, 0.08);
  border: 1px solid rgba(240, 165, 0, 0.2);
  border-bottom-left-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.thinking-icon {
  font-size: 16px;
  animation: float 2s ease-in-out infinite;
}

.msg-agent-call {
  background: rgba(0, 212, 255, 0.06);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-bottom-left-radius: 4px;
}

.msg-agent-result {
  background: rgba(0, 230, 118, 0.05);
  border: 1px solid rgba(0, 230, 118, 0.1);
  border-bottom-left-radius: 4px;
}

.msg-tool {
  background: rgba(124, 92, 252, 0.05);
  border: 1px solid rgba(124, 92, 252, 0.1);
  border-bottom-left-radius: 4px;
}

/* Typing indicator */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 2px 0;
}
.typing-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #535b6e;
  animation: typing-bounce 1.4s ease-in-out infinite;
}
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

/* Input area */
.input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--border-subtle);
  background: rgba(0, 0, 0, 0.15);
}

.chat-input :deep(.ant-input) {
  background: var(--bg-elevated) !important;
  border-color: var(--border-default) !important;
  border-radius: 24px !important;
  padding: 8px 16px !important;
  font-size: 13px !important;
  color: var(--text-primary) !important;
  resize: none !important;
}
.chat-input :deep(.ant-input):focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1) !important;
}

.send-btn {
  width: 40px !important;
  height: 40px !important;
  min-width: 40px !important;
  border-radius: 50% !important;
  display: flex !important;
  align-items: center;
  justify-content: center;
  padding: 0 !important;
}

.loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fff;
  animation: typing-bounce 1s ease-in-out infinite;
}

/* Markdown body for chat messages */
.markdown-body :deep(*) { color: inherit; }
.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 4px 0;
  font-size: 12px;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #1e2538;
  padding: 4px 8px;
  text-align: left;
}
.markdown-body :deep(th) {
  background: #0f1219;
  color: #8892a4;
  font-weight: 600;
}
.markdown-body :deep(code) {
  background: rgba(0, 212, 255, 0.08);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
  color: #00d4ff;
  font-family: 'Cascadia Code', 'Consolas', monospace;
}
.markdown-body :deep(pre) {
  background: #080c15;
  padding: 10px 12px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
  border: 1px solid #151a28;
}
.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: #e4e7ee;
}
.markdown-body :deep(p) {
  margin: 4px 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 16px;
  margin: 4px 0;
}
.markdown-body :deep(strong) {
  color: #fff;
}
.markdown-body :deep(hr) {
  border-color: #151a28;
  margin: 8px 0;
}
</style>
