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
            <a-tag v-if="wecomBotStatus === 'configured'" color="green">已配置</a-tag>
            <a-tag v-else color="default">未配置</a-tag>
          </a-space>
        </a-form-item>
      </a-form>
      <a-alert type="info" show-icon>
        <template #message>
          <div>配置后 wecom-bot 容器将自动连接企微智能机器人。</div>
          <div>如需修改配置，保存后需重启 wecom-bot 容器：<code>docker compose restart wecom-bot</code></div>
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
const wecomBotStatus = computed(() => {
  const id = configs.value.find((c: any) => c.config_key === 'wecom.bot_id')
  return id && id.config_value && id.config_value !== '***' ? 'configured' : 'unconfigured'
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
    message.success('保存成功，请重启 wecom-bot 容器使配置生效')
    // 刷新配置列表
    const res = await client.get('/configs')
    configs.value = res.data.data || []
    wecomForm.bot_id = ''
    wecomForm.bot_secret = ''
  } catch (e: any) {
    message.error(e.response?.data?.message || '保存失败')
  } finally {
    wecomSaving.value = false
  }
}

onMounted(async () => {
  try {
    const res = await client.get('/configs')
    configs.value = res.data.data || []
  } catch {}
})
</script>
