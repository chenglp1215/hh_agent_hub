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
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const configs = ref<any[]>([])

function getConfig(key: string): string {
  return configs.value.find((c: any) => c.config_key === key)?.config_value || '-'
}

onMounted(async () => {
  try {
    const res = await client.get('/configs')
    configs.value = res.data.data || []
  } catch {}
})
</script>
