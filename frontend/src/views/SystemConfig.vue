<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">系统设置</h1>

    <a-card class="max-w-2xl mb-4">
      <template #title>
        <div class="flex items-center justify-between">
          <span>LLM 默认配置</span>
          <a-button size="small" type="primary" ghost @click="$router.push('/settings/llm-configs')">管理配置</a-button>
        </div>
      </template>
      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="默认提供商">
              <a-input :value="getConfig('llm.default.provider')" disabled />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="默认模型">
              <a-input :value="getConfig('llm.default.model')" disabled />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="默认温度">
              <a-input :value="getConfig('llm.default.temperature')" disabled />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="Max Tokens">
              <a-input :value="getConfig('system.max_tokens')" disabled />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-card>

    <a-card title="安全配置" class="max-w-2xl mb-4">
      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="会话过期时间(秒)">
              <a-input :value="getConfig('system.session_ttl')" disabled />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="默认限流(次/分钟)">
              <a-input :value="getConfig('system.rate_limit.default')" disabled />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-card>

    <a-card title="企微智能机器人" class="max-w-2xl mb-4">
      <!-- 连接状态 -->
      <div class="mb-4 p-3 rounded" style="background: var(--surface-1); border: 1px solid var(--border)">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-gray-400">连接状态</span>
          <a-tag v-if="wecomBotStatus.connected" color="green">已连接</a-tag>
          <a-tag v-else color="default">未连接</a-tag>
        </div>
        <template v-if="wecomBotStatus.connected">
          <div v-if="wecomBotStatus.bot_id" class="flex items-center justify-between text-sm">
            <span class="text-gray-400">Bot ID</span>
            <code class="text-xs">{{ wecomBotStatus.bot_id }}</code>
          </div>
          <div v-if="wecomBotStatus.connected_at" class="flex items-center justify-between text-sm mt-1">
            <span class="text-gray-400">连接时间</span>
            <span>{{ wecomBotStatus.connected_at }}</span>
          </div>
        </template>
      </div>

      <a-form layout="vertical">
        <a-form-item label="Bot ID">
          <a-input-password
            v-model:value="wecomForm.bot_id"
            placeholder="企微智能机器人 Bot ID"
          />
        </a-form-item>
        <a-form-item label="Bot Secret">
          <a-input-password
            v-model:value="wecomForm.bot_secret"
            placeholder="企微智能机器人 Bot Secret"
          />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" :loading="wecomSaving" @click="saveWecomConfig">
              保存配置
            </a-button>
            <a-tag v-if="wecomForm.bot_id || wecomForm.bot_secret" color="green">已配置</a-tag>
            <a-tag v-else-if="wecomBotStatus.bot_id" color="green">已配置</a-tag>
            <a-tag v-else color="default">未配置</a-tag>
          </a-space>
        </a-form-item>
      </a-form>
      <a-alert v-if="wecomBotStatus.connected" type="success" show-icon>
        <template #message>
          <div>企微智能机器人已连接，用户发送的消息将自动触发关联应用。</div>
        </template>
      </a-alert>
      <a-alert v-else-if="wecomForm.bot_id || wecomBotStatus.bot_id" type="warning" show-icon>
        <template #message>
          <div>已配置凭证，等待 wecom-bot 容器连接... 如长时间未连接，请检查容器日志。</div>
        </template>
      </a-alert>
      <a-alert v-else type="info" show-icon>
        <template #message>
          <div>请填写 Bot ID 和 Bot Secret 后保存，wecom-bot 容器将自动连接。</div>
        </template>
      </a-alert>
    </a-card>

    <a-card title="关于" class="max-w-2xl">
      <div class="space-y-2 text-sm">
        <div class="flex justify-between"><span class="text-gray-400">系统名称</span><span>多Agent协同平台</span></div>
        <div class="flex justify-between"><span class="text-gray-400">版本</span><span>1.0.0</span></div>
        <div class="flex justify-between"><span class="text-gray-400">数据库</span><span>MySQL 8.0</span></div>
        <div class="flex justify-between"><span class="text-gray-400">Agent 类型</span><span>local / http / claudecode</span></div>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import client from '@/api/client'

const configs = ref<any[]>([])

function getConfig(key: string): string {
  return configs.value.find((c: any) => c.config_key === key)?.config_value || '-'
}

// 企微机器人配置
const wecomForm = reactive({
  bot_id: '',
  bot_secret: '',
})
const wecomSaving = ref(false)
const wecomBotStatus = reactive({
  connected: false,
  bot_id: '',
  bot_name: '',
  connected_at: '',
  updated_at: '',
})

async function fetchWecomBotStatus() {
  try {
    const res = await client.get('/configs/wecom-bot-status')
    const data = res.data.data || {}
    Object.assign(wecomBotStatus, data)
  } catch {}
}
})

async function saveWecomConfig() {
  if (!wecomForm.bot_id || !wecomForm.bot_secret) {
    message.warning('请填写 Bot ID 和 Bot Secret')
    return
  }
  wecomSaving.value = true
  try {
    await client.put('/configs/wecom.bot_id', {
      config_value: wecomForm.bot_id,
      config_type: 'secret',
      description: '企微智能机器人 Bot ID',
    })
    await client.put('/configs/wecom.bot_secret', {
      config_value: wecomForm.bot_secret,
      config_type: 'secret',
      description: '企微智能机器人 Bot Secret',
    })
    message.success('保存成功，wecom-bot 容器将自动重连')
    // 刷新配置列表并回填 ***
    const res = await client.get('/configs')
    configs.value = res.data.data || []
    fillWecomForm()
  } catch (e: any) {
    message.error(e.response?.data?.message || '保存失败')
  } finally {
    wecomSaving.value = false
  }
}

function fillWecomForm() {
  const idVal = configs.value.find((c: any) => c.config_key === 'wecom.bot_id')?.config_value || ''
  const secretVal = configs.value.find((c: any) => c.config_key === 'wecom.bot_secret')?.config_value || ''
  // secret 类型返回 "***"，直接显示在输入框中
  wecomForm.bot_id = idVal
  wecomForm.bot_secret = secretVal
}

onMounted(async () => {
  try {
    const res = await client.get('/configs')
    configs.value = res.data.data || []
    fillWecomForm()
    await fetchWecomBotStatus()
  } catch {}
})
</script>
