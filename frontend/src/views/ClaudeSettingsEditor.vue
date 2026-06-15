<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '新建' }}Claude Settings</h1>
    <a-card class="max-w-2xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <h3 class="text-lg font-semibold mb-4 text-[#5e6ad2]">基本信息</h3>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="名称" name="name" :rules="[{ required: true, message: '请输入名称' }]">
              <a-input v-model:value="form.name" :disabled="isEdit" placeholder="my_claude_config" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="显示名称">
              <a-input v-model:value="form.display_name" placeholder="Claude Code 配置" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>

        <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">执行配置</h3>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="模型">
              <a-select v-model:value="form.model">
                <a-select-option value="claude-sonnet-4-6">Claude Sonnet 4.6</a-select-option>
                <a-select-option value="claude-opus-4-7">Claude Opus 4.7</a-select-option>
                <a-select-option value="claude-sonnet-4-20250514">Claude Sonnet 4 (20250514)</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="最大轮次">
              <a-input-number v-model:value="form.max_turns" :min="1" :max="100" class="w-full" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="权限模式">
              <a-select v-model:value="form.permission_mode">
                <a-select-option value="default">Default</a-select-option>
                <a-select-option value="acceptEdits">Accept Edits</a-select-option>
                <a-select-option value="bypassPermissions">Bypass Permissions</a-select-option>
                <a-select-option value="plan">Plan Only</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item
          label="settings.json (Claude Code 原生配置)"
          :validate-status="settingsJsonStatus"
          :help="settingsJsonError"
        >
          <a-textarea
            v-model:value="form.settings_json"
            :rows="10"
            placeholder='{\n  "permissions": {\n    "allow": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]\n  }\n}'
            style="font-family: 'Courier New', monospace; font-size: 13px;"
            @input="validateSettingsJson"
          />
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
import { claudeSettingsApi } from '@/api/claudeSettings'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)
const form = ref<any>({
  name: '',
  display_name: '',
  description: '',
  model: 'claude-sonnet-4-6',
  max_turns: 25,
  permission_mode: 'acceptEdits',
  settings_json: '',
})

const settingsJsonStatus = ref<'success' | 'error' | ''>('')
const settingsJsonError = ref('')

function validateSettingsJson() {
  const val = form.value.settings_json
  if (!val || !val.trim()) {
    settingsJsonStatus.value = ''
    settingsJsonError.value = ''
    return
  }
  try {
    JSON.parse(val)
    settingsJsonStatus.value = 'success'
    settingsJsonError.value = ''
  } catch (e: any) {
    settingsJsonStatus.value = 'error'
    settingsJsonError.value = e.message || 'JSON 格式错误'
  }
}

onMounted(async () => {
  if (isEdit.value) {
    try {
      const res = await claudeSettingsApi.get(Number(route.params.id))
      const d = res.data.data
      form.value = {
        name: d.name,
        display_name: d.display_name || '',
        description: d.description || '',
        model: d.model || 'claude-sonnet-4-6',
        max_turns: d.max_turns ?? 25,
        permission_mode: d.permission_mode || 'acceptEdits',
        settings_json: d.settings_json || '',
      }
    } catch {
      message.error('加载配置失败')
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    // Final validation
    if (form.value.settings_json && form.value.settings_json.trim()) {
      try {
        JSON.parse(form.value.settings_json)
      } catch {
        message.error('settings.json 格式无效')
        submitting.value = false
        return
      }
    }
    if (isEdit.value) {
      await claudeSettingsApi.update(Number(route.params.id), form.value)
    } else {
      await claudeSettingsApi.create(form.value)
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    router.push('/claude-settings')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
