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

        <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">LLM 配置</h3>
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
})

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
      }
    } catch {
      message.error('加载配置失败')
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    const data: any = { ...form.value }
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
