<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '创建' }} 触发器</h1>
    <a-card class="max-w-2xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <a-form-item label="触发器名称" name="name" :rules="[{ required: true, message: '请输入触发器名称' }]">
          <a-input v-model:value="form.name" placeholder="如：每日巡检" />
        </a-form-item>

        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="可选描述" />
        </a-form-item>

        <a-form-item label="触发类型" name="trigger_type" :rules="[{ required: true, message: '请选择触发类型' }]">
          <a-radio-group v-model:value="form.trigger_type">
            <a-radio value="interval">间隔触发</a-radio>
            <a-radio value="cron">Cron 表达式</a-radio>
            <a-radio value="wecom_bot">企微机器人</a-radio>
          </a-radio-group>
        </a-form-item>

        <!-- Interval 配置 -->
        <template v-if="form.trigger_type === 'interval'">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="间隔数值" name="interval_value"
                :rules="[{ required: form.trigger_type === 'interval', message: '请输入间隔数值' }]">
                <a-input-number v-model:value="form.interval_value" :min="1" :max="99999" class="w-full" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="间隔单位" name="interval_unit"
                :rules="[{ required: form.trigger_type === 'interval', message: '请选择间隔单位' }]">
                <a-select v-model:value="form.interval_unit">
                  <a-select-option value="minutes">分钟</a-select-option>
                  <a-select-option value="hours">小时</a-select-option>
                  <a-select-option value="days">天</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
        </template>

        <!-- Cron 配置 -->
        <template v-if="form.trigger_type === 'cron'">
          <a-form-item label="Cron 表达式" name="cron_expression"
            :rules="[{ required: form.trigger_type === 'cron', message: '请输入 cron 表达式' }]">
            <a-input v-model:value="form.cron_expression" placeholder="如：0 9 * * 1-5" />
          </a-form-item>
          <div class="mb-4">
            <span class="text-sm text-gray-400 mr-2">预设：</span>
            <a-button size="small" class="mr-1" @click="setCronPreset('0 * * * *')">每小时</a-button>
            <a-button size="small" class="mr-1" @click="setCronPreset('0 9 * * *')">每天 9:00</a-button>
            <a-button size="small" class="mr-1" @click="setCronPreset('0 9 * * 1-5')">工作日 9:00</a-button>
            <a-button size="small" @click="setCronPreset('0 0 1 * *')">每月1日</a-button>
          </div>
        </template>

        <a-form-item label="关联应用" name="app_id"
          :rules="[{ required: true, message: '请选择关联应用' }]">
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

        <a-form-item label="触发消息内容" name="message"
          :rules="[{ required: true, message: '请输入触发消息内容' }]">
          <a-textarea v-model:value="form.message" :rows="3" placeholder="输入触发时发送的 Chat 消息内容" />
        </a-form-item>

        <a-form-item v-if="form.trigger_type !== 'wecom_bot'" label="通知渠道">
          <a-select
            v-model:value="form.notification_id"
            placeholder="选择通知渠道（可选）"
            allow-clear
          >
            <a-select-option
              v-for="ch in notificationChannels"
              :key="ch.id"
              :value="ch.id"
            >
              {{ ch.name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <!-- 企微机器人绑定 -->
        <template v-if="form.trigger_type === 'wecom_bot'">
          <a-divider>企微机器人绑定</a-divider>

          <!-- 生成验证码并绑定 -->
          <a-form-item v-if="!bindResult" label="绑定聊天">
            <a-space direction="vertical" class="w-full">
              <a-button
                type="dashed"
                @click="handleGenerateCode"
                :loading="generatingCode"
                :disabled="!form.app_id"
              >
                生成绑定验证码
              </a-button>

              <template v-if="bindCode">
                <a-alert type="info" show-icon>
                  <template #message>
                    <div>请在企业微信的群聊或私聊中，向智能机器人发送以下验证码：</div>
                    <div class="text-2xl font-bold tracking-widest my-2">{{ bindCode }}</div>
                    <div class="text-gray-400">验证码有效期 5 分钟，等待绑定中...</div>
                  </template>
                </a-alert>
              </template>
            </a-space>
          </a-form-item>

          <!-- 绑定结果 -->
          <a-form-item v-if="bindResult" label="绑定结果">
            <a-alert type="success" show-icon>
              <template #message>
                <div>绑定成功！</div>
                <div>聊天类型：{{ bindResult.chat_type === 'group' ? '群聊' : '私聊' }}</div>
                <div>聊天ID：{{ bindResult.chat_id }}</div>
              </template>
            </a-alert>
          </a-form-item>
        </template>

        <a-form-item>
          <a-space>
            <a-button type="primary" html-type="submit" :loading="submitting">保存</a-button>
            <a-button @click="$router.back()">取消</a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { triggersApi } from '@/api/triggers'
import { appsApi } from '@/api/apps'
import { notificationsApi } from '@/api/notifications'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)
const enabledApps = ref<any[]>([])
const notificationChannels = ref<any[]>([])

// wecom-bot binding state
const bindCode = ref('')
const bindResult = ref<{ chat_type: string; chat_id: string } | null>(null)
const generatingCode = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const form = ref({
  name: '',
  description: '',
  trigger_type: 'interval' as 'interval' | 'cron' | 'wecom_bot',
  interval_value: undefined as number | undefined,
  interval_unit: undefined as string | undefined,
  cron_expression: '',
  app_id: undefined as number | undefined,
  message: '',
  notification_id: undefined as number | undefined,
  // wecom_bot fields
  wecom_chat_type: undefined as string | undefined,
  wecom_chat_id: undefined as string | undefined,
  wecom_user_id: undefined as string | undefined,
})

function setCronPreset(expr: string) {
  form.value.cron_expression = expr
}

onMounted(async () => {
  // 加载已启用的应用列表和通知渠道列表
  const [appsRes, notifRes] = await Promise.all([
    appsApi.list(),
    notificationsApi.list(),
  ])
  enabledApps.value = (appsRes.data.data || []).filter((a: any) => a.enabled)
  notificationChannels.value = notifRes.data.data || []

  if (isEdit.value) {
    const res = await triggersApi.get(Number(route.params.id))
    const d = res.data.data
    form.value = {
      name: d.name,
      description: d.description || '',
      trigger_type: d.trigger_type,
      interval_value: d.interval_value,
      interval_unit: d.interval_unit,
      cron_expression: d.cron_expression || '',
      app_id: d.app_id,
      message: d.message,
      notification_id: d.notification_id || undefined,
      wecom_chat_type: d.wecom_chat_type || undefined,
      wecom_chat_id: d.wecom_chat_id || undefined,
      wecom_user_id: d.wecom_user_id || undefined,
    }
    // If editing a wecom_bot trigger with existing binding, show result
    if (d.trigger_type === 'wecom_bot' && d.wecom_chat_type) {
      bindResult.value = {
        chat_type: d.wecom_chat_type,
        chat_id: d.wecom_chat_type === 'group' ? d.wecom_chat_id : d.wecom_user_id,
      }
    }
  }
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
    // 开始轮询绑定状态
    startPolling(data.code)
  } catch (e: any) {
    message.error(e.response?.data?.message || '生成验证码失败')
  } finally {
    generatingCode.value = false
  }
}

function startPolling(code: string) {
  if (pollTimer) clearInterval(pollTimer)
  let attempts = 0
  pollTimer = setInterval(async () => {
    attempts++
    if (attempts > 60) { // 5分钟超时
      clearInterval(pollTimer!)
      pollTimer = null
      message.error('绑定超时，请重新生成验证码')
      bindCode.value = ''
      return
    }
    try {
      const res = await triggersApi.getBindStatus(code)
      const data = res.data.data
      if (data.status === 'bound') {
        clearInterval(pollTimer!)
        pollTimer = null
        bindResult.value = {
          chat_type: data.chat_type,
          chat_id: data.chat_id,
        }
        // 自动填充表单字段
        form.value.wecom_chat_type = data.chat_type
        if (data.chat_type === 'group') {
          form.value.wecom_chat_id = data.chat_id
          form.value.wecom_user_id = undefined
        } else {
          form.value.wecom_user_id = data.chat_id
          form.value.wecom_chat_id = undefined
        }
        bindCode.value = ''
        message.success('绑定成功！')
      }
    } catch (e) {
      // 404 = 已过期
      if ((e as any).response?.status === 404) {
        clearInterval(pollTimer!)
        pollTimer = null
        message.error('验证码已过期，请重新生成')
        bindCode.value = ''
      }
    }
  }, 5000) // 每 5 秒轮询
}

async function handleSubmit() {
  submitting.value = true
  try {
    const payload: Record<string, any> = { ...form.value }
    // 清理互斥字段
    if (payload.trigger_type === 'interval') {
      payload.cron_expression = null
      payload.wecom_chat_type = null
      payload.wecom_chat_id = null
      payload.wecom_user_id = null
    } else if (payload.trigger_type === 'cron') {
      payload.interval_value = null
      payload.interval_unit = null
      payload.wecom_chat_type = null
      payload.wecom_chat_id = null
      payload.wecom_user_id = null
    } else if (payload.trigger_type === 'wecom_bot') {
      payload.interval_value = null
      payload.interval_unit = null
      payload.cron_expression = null
      payload.notification_id = null
    }

    if (isEdit.value) {
      await triggersApi.update(Number(route.params.id), payload)
    } else {
      await triggersApi.create(payload)
    }
    message.success('保存成功')
    router.push('/triggers')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>
