<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">创建企微机器人触发器</h1>

    <a-card class="max-w-2xl">
      <a-steps :current="currentStep" class="mb-8">
        <a-step title="基本信息" description="名称、关联应用" />
        <a-step title="绑定聊天" description="验证码绑定" />
        <a-step title="确认创建" description="保存触发器" />
      </a-steps>

      <!-- Step 1: 基本信息 -->
      <div v-if="currentStep === 0">
        <a-form :model="form" layout="vertical">
          <a-form-item label="触发器名称" required>
            <a-input v-model:value="form.name" placeholder="如：客服机器人-产品群" />
          </a-form-item>

          <a-form-item label="描述">
            <a-textarea v-model:value="form.description" :rows="2" placeholder="可选描述" />
          </a-form-item>

          <a-form-item label="关联应用" required>
            <a-select
              v-model:value="form.app_id"
              show-search
              option-filter-prop="label"
              placeholder="选择已启用的应用"
            >
              <a-select-option
                v-for="app in enabledApps"
                :key="app.id"
                :value="app.id"
                :label="app.name"
              >
                {{ app.name }}
              </a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item>
            <a-button type="primary" :disabled="!form.name || !form.app_id" @click="currentStep = 1">
              下一步
            </a-button>
          </a-form-item>
        </a-form>
      </div>

      <!-- Step 2: 绑定聊天 -->
      <div v-if="currentStep === 1">
        <div class="mb-4">
          <a-button
            type="dashed"
            size="large"
            block
            @click="handleGenerateCode"
            :loading="generatingCode"
            v-if="!bindCode && !bindResult"
          >
            生成绑定验证码
          </a-button>
        </div>

        <!-- 等待绑定 -->
        <template v-if="bindCode && !bindResult">
          <a-alert type="info" show-icon class="mb-4">
            <template #message>
              <div class="text-center">
                <div class="text-base mb-2">请在企业微信的群聊或私聊中，向智能机器人发送以下验证码：</div>
                <div class="text-4xl font-bold tracking-[0.5em] my-4" style="color: var(--accent)">
                  {{ bindCode }}
                </div>
                <div class="text-gray-400">
                  <a-spin size="small" class="mr-2" />
                  等待绑定中... ({{ countdown }}s)
                </div>
              </div>
            </template>
          </a-alert>
          <a-button block @click="handleCancelBind">取消，重新生成</a-button>
        </template>

        <!-- 绑定成功 -->
        <template v-if="bindResult">
          <a-result status="success" title="绑定成功！" sub-title="已成功绑定到企微聊天">
            <template #extra>
              <a-descriptions :column="1" bordered size="small" class="max-w-md mx-auto">
                <a-descriptions-item label="聊天类型">
                  <a-tag :color="bindResult.chat_type === 'group' ? 'blue' : 'green'">
                    {{ bindResult.chat_type === 'group' ? '群聊' : '私聊' }}
                  </a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="聊天 ID">
                  <code>{{ bindResult.chat_id }}</code>
                </a-descriptions-item>
              </a-descriptions>
            </template>
          </a-result>
          <div class="flex justify-between mt-4">
            <a-button @click="currentStep = 0">上一步</a-button>
            <a-button type="primary" @click="currentStep = 2">下一步</a-button>
          </div>
        </template>

        <!-- 未开始绑定 -->
        <div v-if="!bindCode && !bindResult" class="flex justify-between mt-4">
          <a-button @click="currentStep = 0">上一步</a-button>
        </div>
      </div>

      <!-- Step 3: 确认创建 -->
      <div v-if="currentStep === 2">
        <a-descriptions :column="1" bordered size="small" class="mb-6">
          <a-descriptions-item label="触发器名称">{{ form.name }}</a-descriptions-item>
          <a-descriptions-item label="描述">{{ form.description || '-' }}</a-descriptions-item>
          <a-descriptions-item label="关联应用">
            {{ enabledApps.find(a => a.id === form.app_id)?.name }}
          </a-descriptions-item>
          <a-descriptions-item label="触发器类型">
            <a-tag color="purple">企微机器人</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="绑定聊天">
            <a-tag :color="bindResult?.chat_type === 'group' ? 'blue' : 'green'">
              {{ bindResult?.chat_type === 'group' ? '群聊' : '私聊' }}
            </a-tag>
            <code class="ml-2">{{ bindResult?.chat_id }}</code>
          </a-descriptions-item>
        </a-descriptions>

        <a-alert type="info" show-icon class="mb-4">
          <template #message>
            <div>用户在该聊天中向机器人发送的文本消息，将自动触发关联应用的工作流执行。</div>
          </template>
        </a-alert>

        <div class="flex justify-between">
          <a-button @click="currentStep = 1">上一步</a-button>
          <a-button type="primary" :loading="submitting" @click="handleSubmit">
            确认创建
          </a-button>
        </div>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { triggersApi } from '@/api/triggers'
import { appsApi } from '@/api/apps'

const router = useRouter()
const currentStep = ref(0)
const submitting = ref(false)
const enabledApps = ref<any[]>([])

const form = ref({
  name: '',
  description: '',
  app_id: undefined as number | undefined,
})

// 绑定状态
const bindCode = ref('')
const bindResult = ref<{ chat_type: string; chat_id: string } | null>(null)
const generatingCode = ref(false)
const countdown = ref(300)
let pollTimer: ReturnType<typeof setInterval> | null = null
let countdownTimer: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  const res = await appsApi.list()
  enabledApps.value = (res.data.data || []).filter((a: any) => a.enabled)
})

async function handleGenerateCode() {
  if (!form.value.app_id) {
    message.warning('请先选择关联应用')
    return
  }
  generatingCode.value = true
  try {
    const res = await triggersApi.generateCode(form.value.app_id)
    const data = res.data.data
    bindCode.value = data.code
    countdown.value = data.expires_in || 300
    startPolling(data.code)
    startCountdown()
  } catch (e: any) {
    message.error(e.response?.data?.message || '生成验证码失败')
  } finally {
    generatingCode.value = false
  }
}

function startCountdown() {
  if (countdownTimer) clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(countdownTimer!)
      countdownTimer = null
    }
  }, 1000)
}

function startPolling(code: string) {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const res = await triggersApi.getBindStatus(code)
      const data = res.data.data
      if (data.status === 'bound') {
        clearInterval(pollTimer!)
        pollTimer = null
        if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
        bindResult.value = {
          chat_type: data.chat_type,
          chat_id: data.chat_id,
        }
        message.success('绑定成功！')
      }
    } catch (e) {
      if ((e as any).response?.status === 404) {
        clearInterval(pollTimer!)
        pollTimer = null
        if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
        message.error('验证码已过期，请重新生成')
        bindCode.value = ''
      }
    }
  }, 3000)
}

function handleCancelBind() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
  bindCode.value = ''
  bindResult.value = null
}

async function handleSubmit() {
  if (!bindResult.value) {
    message.error('请先完成聊天绑定')
    return
  }
  submitting.value = true
  try {
    const payload: Record<string, any> = {
      name: form.value.name,
      description: form.value.description || null,
      trigger_type: 'wecom_bot',
      app_id: form.value.app_id,
      message: '',  // 消息内容来自 WS，不需要用户输入
      wecom_chat_type: bindResult.value.chat_type,
      interval_value: null,
      interval_unit: null,
      cron_expression: null,
      notification_id: null,
    }
    if (bindResult.value.chat_type === 'group') {
      payload.wecom_chat_id = bindResult.value.chat_id
      payload.wecom_user_id = null
    } else {
      payload.wecom_user_id = bindResult.value.chat_id
      payload.wecom_chat_id = null
    }

    await triggersApi.create(payload)
    message.success('创建成功！')
    router.push('/triggers')
  } catch (e: any) {
    message.error(e.response?.data?.message || '创建失败')
  } finally {
    submitting.value = false
  }
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>
