<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '新建' }}Reasonix 配置</h1>
    <a-card class="max-w-2xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <h3 class="text-lg font-semibold mb-4 text-[#5e6ad2]">基本信息</h3>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="名称" name="name" :rules="[{ required: true, message: '请输入名称' }]">
              <a-input v-model:value="form.name" :disabled="isEdit" placeholder="deepseek_pro_config" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="显示名称">
              <a-input v-model:value="form.display_name" placeholder="DeepSeek Pro 配置" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>

        <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">模型配置</h3>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="模型">
              <a-select v-model:value="form.model">
                <a-select-option value="deepseek-v4-pro">DeepSeek V4 Pro</a-select-option>
                <a-select-option value="deepseek-v4-flash">DeepSeek V4 Flash</a-select-option>
                <a-select-option value="deepseek-chat">deepseek-chat (legacy)</a-select-option>
                <a-select-option value="deepseek-coder">deepseek-coder (legacy)</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="温度">
              <a-input-number v-model:value="form.temperature" :min="0" :max="2" :step="0.1" class="w-full" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="最大轮次">
              <a-input-number v-model:value="form.max_turns" :min="1" :max="100" class="w-full" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="16">
            <a-form-item label="API Key">
              <a-input-password v-model:value="form.api_key" placeholder="sk-..." />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="Base URL">
              <a-input v-model:value="form.base_url" placeholder="留空使用默认地址" />
            </a-form-item>
          </a-col>
        </a-row>

        <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">Agent 行为</h3>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="推理语言">
              <a-select v-model:value="form.reasoning_language">
                <a-select-option value="zh">中文</a-select-option>
                <a-select-option value="en">English</a-select-option>
                <a-select-option value="auto">自动</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="压缩阈值">
              <a-input-number v-model:value="form.compact_ratio" :min="0.3" :max="0.95" :step="0.05" class="w-full" />
              <div class="text-xs text-[#535b6e] mt-1">上下文达到此比例时触发压缩</div>
            </a-form-item>
          </a-col>
        </a-row>

        <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">高级配置 (JSON)</h3>
        <a-form-item
          :validate-status="extraJsonStatus"
          :help="extraJsonError"
        >
          <a-textarea
            v-model:value="extraJsonStr"
            :rows="6"
            placeholder='{"sandbox": {"bash": "enforce", "network": true}, "permissions": {"mode": "ask", "allow": ["Edit", "Bash(*)"]}}'
            style="font-family: 'Courier New', monospace; font-size: 13px;"
            @input="validateExtraJson"
          />
          <div class="text-xs text-[#535b6e] mt-1">
            补充 reasonix.toml 高级字段，如 sandbox、permissions、tools 等。留空则使用默认值。
          </div>
        </a-form-item>

        <a-divider />
        <a-form-item>
          <a-space>
            <a-button type="primary" html-type="submit" :loading="submitting">{{ isEdit ? '更新' : '创建' }}</a-button>
            <a-button @click="$router.back()">取消</a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { reasonixSettingsApi } from '@/api/reasonixSettings'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)
const form = ref<any>({
  name: '',
  display_name: '',
  description: '',
  model: 'deepseek-v4-pro',
  api_key: '',
  base_url: '',
  temperature: 0.0,
  max_turns: 25,
  reasoning_language: 'zh',
  compact_ratio: 0.8,
})

const extraJsonStr = ref('')
const extraJsonStatus = ref<'success' | 'error' | ''>('')
const extraJsonError = ref('')

function validateExtraJson() {
  const val = extraJsonStr.value
  if (!val || !val.trim()) {
    extraJsonStatus.value = ''
    extraJsonError.value = ''
    return
  }
  try {
    JSON.parse(val)
    extraJsonStatus.value = 'success'
    extraJsonError.value = ''
  } catch (e: any) {
    extraJsonStatus.value = 'error'
    extraJsonError.value = e.message || 'JSON 格式错误'
  }
}

onMounted(async () => {
  if (isEdit.value) {
    try {
      const res = await reasonixSettingsApi.get(Number(route.params.id))
      const d = res.data.data
      form.value = {
        name: d.name,
        display_name: d.display_name || '',
        description: d.description || '',
        model: d.model || 'deepseek-v4-pro',
        api_key: d.api_key || '',
        base_url: d.base_url || '',
        temperature: d.temperature ?? 0.0,
        max_turns: d.max_turns ?? 25,
        reasoning_language: d.reasoning_language || 'zh',
        compact_ratio: d.compact_ratio ?? 0.8,
      }
      if (d.extra_json) {
        extraJsonStr.value = JSON.stringify(d.extra_json, null, 2)
      }
    } catch {
      message.error('加载配置失败')
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    if (extraJsonStr.value && extraJsonStr.value.trim()) {
      try {
        JSON.parse(extraJsonStr.value)
      } catch {
        message.error('高级配置 JSON 格式无效')
        submitting.value = false
        return
      }
    }
    const data: any = { ...form.value }
    if (extraJsonStr.value && extraJsonStr.value.trim()) {
      data.extra_json = JSON.parse(extraJsonStr.value)
    } else {
      data.extra_json = null
    }
    if (isEdit.value) {
      await reasonixSettingsApi.update(Number(route.params.id), data)
    } else {
      await reasonixSettingsApi.create(data)
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    router.push('/reasonix-settings')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
