<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">LLM 配置管理</h1>
      <a-button type="primary" @click="openCreate"><PlusOutlined /> 新建配置</a-button>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <a-card v-for="c in configs" :key="c.id" hoverable>
        <div class="flex items-start justify-between mb-3">
          <div>
            <div class="flex items-center gap-2">
              <a-tag :color="providerColor(c.provider)">{{ c.provider }}</a-tag>
              <span class="text-sm text-gray-400">{{ c.model }}</span>
            </div>
            <h3 class="text-lg font-semibold mt-1">{{ c.name }}</h3>
          </div>
          <a-badge :status="c.status === 'active' ? 'success' : 'default'" />
        </div>
        <p v-if="c.description" class="text-sm text-gray-500 mb-3">{{ c.description }}</p>
        <div class="text-xs text-gray-500 space-y-1 mb-3">
          <div>Temperature: {{ c.temperature }} &middot; Max Tokens: {{ c.max_tokens }}</div>
        </div>
        <template #actions>
          <a-button size="small" @click="openEdit(c)">编辑</a-button>
          <a-popconfirm title="确定删除？" @confirm="handleDelete(c.id)">
            <a-button size="small" danger>删除</a-button>
          </a-popconfirm>
        </template>
      </a-card>

      <a-empty v-if="!loading && configs.length === 0" description="暂无 LLM 配置" class="col-span-full" />
    </div>

    <!-- 创建/编辑弹窗 -->
    <a-modal
      v-model:open="modalOpen"
      :title="editingId ? '编辑 LLM 配置' : '新建 LLM 配置'"
      @ok="handleSave"
      :confirmLoading="saving"
      width="520px"
    >
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="form.name" placeholder="如 openai-gpt4o" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="提供商" required>
              <a-select v-model:value="form.provider">
                <a-select-option value="openai">OpenAI</a-select-option>
                <a-select-option value="anthropic">Anthropic</a-select-option>
                <a-select-option value="ollama">Ollama</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="模型" required>
              <a-input v-model:value="form.model" placeholder="gpt-4o-mini" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="API Key">
          <a-input-password v-model:value="form.api_key" placeholder="sk-..." />
        </a-form-item>
        <a-form-item label="Base URL">
          <a-input v-model:value="form.base_url" placeholder="https://api.openai.com/v1（可选）" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="Temperature">
              <a-input-number v-model:value="form.temperature" :min="0" :max="2" :step="0.1" class="w-full" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="Max Tokens">
              <a-input-number v-model:value="form.max_tokens" :min="100" :max="128000" class="w-full" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="可选描述" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { llmConfigsApi } from '@/api/llmConfigs'

const configs = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const editingId = ref<number | null>(null)

const form = ref({ name: '', provider: 'openai', model: 'gpt-4o-mini', api_key: '', base_url: '', temperature: 0.3, max_tokens: 4096, description: '' })

function providerColor(p: string) { return { openai: 'green', anthropic: 'purple', ollama: 'blue' }[p] || 'default' }

async function fetchList() {
  loading.value = true
  try {
    const res = await llmConfigsApi.list()
    configs.value = res.data.data || []
  } catch { message.error('加载失败') }
  finally { loading.value = false }
}

function openCreate() {
  editingId.value = null
  form.value = { name: '', provider: 'openai', model: 'gpt-4o-mini', api_key: '', base_url: '', temperature: 0.3, max_tokens: 4096, description: '' }
  modalOpen.value = true
}

function openEdit(c: any) {
  editingId.value = c.id
  form.value = { name: c.name, provider: c.provider, model: c.model, api_key: c.api_key || '', base_url: c.base_url || '', temperature: c.temperature, max_tokens: c.max_tokens, description: c.description || '' }
  modalOpen.value = true
}

async function handleSave() {
  if (!form.value.name.trim()) { message.warning('请输入名称'); return }
  saving.value = true
  try {
    if (editingId.value) {
      await llmConfigsApi.update(editingId.value, form.value)
    } else {
      await llmConfigsApi.create(form.value)
    }
    message.success(editingId.value ? '更新成功' : '创建成功')
    modalOpen.value = false
    fetchList()
  } catch (e: any) { message.error(e.response?.data?.message || '保存失败') }
  finally { saving.value = false }
}

async function handleDelete(id: number) {
  try {
    await llmConfigsApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch { message.error('删除失败') }
}

onMounted(fetchList)
</script>
