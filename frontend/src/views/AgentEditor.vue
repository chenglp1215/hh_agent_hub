<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '创建' }} Agent</h1>

    <a-card class="max-w-3xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <!-- Basic Info -->
        <h3 class="text-lg font-semibold mb-4 text-[#5e6ad2]">基础信息</h3>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="名称" name="name" :rules="[{ required: true, message: '请输入名称' }]">
              <a-input v-model:value="form.name" :disabled="isEdit" placeholder="data_query_agent" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="显示名称">
              <a-input v-model:value="form.display_name" placeholder="数据查询专家" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="Agent 类型">
              <a-select v-model:value="form.agent_type">
                <a-select-option value="local">本地 Agent</a-select-option>
                <a-select-option value="http">HTTP Agent</a-select-option>
                <a-select-option value="claudecode">Claude Code</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="角色">
              <a-select v-model:value="form.role">
                <a-select-option value="worker">工作 Agent</a-select-option>
                <a-select-option value="supervisor">主管 Agent</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="状态">
              <a-select v-model:value="form.status">
                <a-select-option value="active">启用</a-select-option>
                <a-select-option value="disabled">禁用</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>

        <!-- LLM Config (local agent) -->
        <template v-if="form.agent_type === 'local'">
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">LLM 配置</h3>

          <a-form-item label="选择系统配置">
            <a-radio-group v-model:value="llmMode" button-style="solid">
              <a-radio-button value="select">选用已有配置</a-radio-button>
              <a-radio-button value="manual">手动填写</a-radio-button>
            </a-radio-group>
          </a-form-item>

          <template v-if="llmMode === 'select'">
            <a-form-item label="LLM 配置">
              <a-select
                v-model:value="llmConfigId"
                placeholder="选择 LLM 配置..."
                :options="llmConfigOptions"
                show-search
                filter-option
                allow-clear
              />
            </a-form-item>
          </template>

          <template v-else>
            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item label="提供商">
                  <a-select v-model:value="llmConfig.provider">
                    <a-select-option value="openai">OpenAI</a-select-option>
                    <a-select-option value="anthropic">Anthropic</a-select-option>
                    <a-select-option value="ollama">Ollama</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="模型">
                  <a-input v-model:value="llmConfig.model" placeholder="gpt-4o-mini" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="温度">
                  <a-input-number v-model:value="llmConfig.temperature" :min="0" :max="2" :step="0.1" class="w-full" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="Max Tokens">
                  <a-input-number v-model:value="llmConfig.max_tokens" :min="100" :max="128000" class="w-full" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="API Key">
                  <a-input-password v-model:value="llmConfig.api_key" placeholder="sk-..." />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="Base URL">
                  <a-input v-model:value="llmConfig.base_url" placeholder="https://api.openai.com/v1" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>
        </template>

        <!-- HTTP Config -->
        <template v-if="form.agent_type === 'http'">
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">HTTP 配置</h3>
          <a-form-item label="Base URL" name="http_base_url" :rules="[{ required: true, message: '请输入 Base URL' }]">
            <a-input v-model:value="httpConfig.base_url" placeholder="http://external-agent:8080" />
          </a-form-item>
          <a-form-item label="Endpoint">
            <a-input v-model:value="httpConfig.endpoint" placeholder="/chat" />
          </a-form-item>
          <a-form-item label="Headers (JSON)">
            <a-textarea v-model:value="httpConfigHeaders" :rows="3" placeholder='{"Authorization": "Bearer xxx"}' />
          </a-form-item>
          <a-form-item label="超时(秒)">
            <a-input-number v-model:value="httpConfig.timeout" :min="5" :max="300" class="w-full" />
          </a-form-item>
        </template>

        <!-- Claude Code Config -->
        <template v-if="form.agent_type === 'claudecode'">
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">Claude Code 配置</h3>

          <!-- Quick settings (optional, overlay CLI args) -->
          <a-row :gutter="16">
            <a-col :span="8">
              <a-form-item label="模型 (CLI --model)">
                <a-select v-model:value="ccConfig.model" @change="syncCcToSettingsJson">
                  <a-select-option value="claude-sonnet-4-6">Claude Sonnet 4.6</a-select-option>
                  <a-select-option value="claude-opus-4-7">Claude Opus 4.7</a-select-option>
                  <a-select-option value="claude-sonnet-4-20250514">Claude Sonnet 4 (20250514)</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="最大轮次 (CLI --max-turns)">
                <a-input-number v-model:value="ccConfig.max_turns" :min="1" :max="100" class="w-full" @change="syncCcToSettingsJson" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="权限模式 (CLI --permission-mode)">
                <a-select v-model:value="ccConfig.permission_mode" @change="syncCcToSettingsJson">
                  <a-select-option value="default">Default</a-select-option>
                  <a-select-option value="acceptEdits">Accept Edits</a-select-option>
                  <a-select-option value="bypassPermissions">Bypass Permissions</a-select-option>
                  <a-select-option value="plan">Plan Only</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item label="工作目录">
            <a-input v-model:value="ccConfig.work_dir" placeholder="/data/agent_workspaces/agent_1/" />
          </a-form-item>

          <!-- Settings JSON textarea (primary config) -->
          <a-form-item
            label="settings.json (Claude Code 原生配置)"
            :validate-status="settingsJsonStatus"
            :help="settingsJsonError"
          >
            <a-textarea
              v-model:value="ccConfig.settings_json"
              :rows="12"
              placeholder='{\n  "model": "claude-sonnet-4-6",\n  "permissions": {\n    "allow": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]\n  }\n}'
              style="font-family: 'Courier New', monospace; font-size: 13px;"
              @input="validateSettingsJson"
            />
          </a-form-item>
          <p class="text-xs text-gray-500 -mt-3 mb-4">
            settings.json 是 Claude Code 的原生配置文件，将写入 work_dir/.claude/settings.json。
            上方快速设置字段（模型/轮次/权限）通过 CLI 参数透传，优先级高于 settings.json。
            MCP Server 通过页面下方的资源选择器关联，运行时自动注入。
          </p>
        </template>

        <!-- System Prompt -->
        <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">System Prompt</h3>
        <a-form-item>
          <a-textarea v-model:value="form.system_prompt" :rows="6" placeholder="你是..." />
        </a-form-item>

        <!-- Resource Selection -->
        <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">资源目录选择</h3>
        <McpServerSelector v-model="selectedMcpServers" />
        <KnowledgeBaseSelector v-model="selectedKbIds" class="mt-4" />
        <SkillsSelector v-model="selectedSkillIds" class="mt-4" />

        <a-divider />
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
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { agentsApi } from '@/api/agents'
import McpServerSelector from '@/components/McpServerSelector.vue'
import KnowledgeBaseSelector from '@/components/KnowledgeBaseSelector.vue'
import SkillsSelector from '@/components/SkillsSelector.vue'
import { llmConfigsApi } from '@/api/llmConfigs'

const props = defineProps<{ id?: string }>()

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!props.id || !!route.params.id)
const submitting = ref(false)

const form = ref<any>({
  name: '',
  display_name: '',
  description: '',
  agent_type: 'local',
  role: 'worker',
  status: 'active',
  system_prompt: '',
})
const llmConfig = ref<any>({
  provider: 'openai',
  model: 'gpt-4o-mini',
  temperature: 0.3,
  max_tokens: 4096,
  api_key: '',
  base_url: '',
})
const httpConfig = ref<any>({
  base_url: '',
  endpoint: '/chat',
  timeout: 30,
})
const llmMode = ref<'select' | 'manual'>('manual')
const llmConfigId = ref<number | null>(null)
const llmConfigOptions = ref<{ value: number; label: string }[]>([])

async function loadLlmConfigOptions() {
  try {
    const res = await llmConfigsApi.list()
    llmConfigOptions.value = (res.data.data || []).map((c: any) => ({ value: c.id, label: `${c.name} (${c.provider}/${c.model})` }))
  } catch { /* ignore */ }
}
const httpConfigHeaders = ref('{}')
const ccConfig = ref<any>({
  settings_json: '',
  model: 'claude-sonnet-4-6',
  max_turns: 25,
  work_dir: '',
  permission_mode: 'acceptEdits',
})

// JSON validation state
const settingsJsonStatus = ref<'success' | 'error' | ''>('')
const settingsJsonError = ref('')

function validateSettingsJson() {
  const val = ccConfig.value.settings_json
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

function syncCcToSettingsJson() {
  /* Optional: sync simple fields into settings_json.
     Currently not auto-syncing to preserve user's manual edits. */
}
const selectedMcpServers = ref<any[]>([])
const selectedKbIds = ref<number[]>([])
const selectedSkillIds = ref<number[]>([])

const agentId = computed(() => Number(props.id || route.params.id))

async function loadAgent() {
  try {
    const res = await agentsApi.get(agentId.value)
    const d = res.data.data
    form.value = {
      name: d.name,
      display_name: d.display_name || '',
      description: d.description || '',
      agent_type: d.agent_type,
      role: d.role,
      status: d.status,
      system_prompt: d.system_prompt || '',
    }
    if (d.llm_config_id) {
      llmMode.value = 'select'
      llmConfigId.value = d.llm_config_id
    } else if (d.llm_config) {
      llmMode.value = 'manual'
      llmConfig.value = { ...llmConfig.value, ...d.llm_config }
    }
    if (d.http_config) {
      httpConfig.value = d.http_config
      httpConfigHeaders.value = JSON.stringify(d.http_config.headers || {}, null, 2)
    }
    if (d.claudecode_config) {
      ccConfig.value = { ...ccConfig.value, ...d.claudecode_config }
      // Validate the loaded json
      validateSettingsJson()
    }
    selectedMcpServers.value = (d.mcp_links || []).map((l: any) => ({
      mcp_server_id: l.mcp_server?.id || l.mcp_server_id,
      enabled_tools: l.enabled_tools || [],
      server: l.mcp_server || undefined,
    }))
    selectedKbIds.value = (d.kb_links || []).map((l: any) => l.kb?.id || l.kb_id)
    selectedSkillIds.value = (d.skill_links || []).map((l: any) => l.skill?.id || l.skill_id)
  } catch {
    message.error('加载 Agent 失败')
  }
}

function buildFormData() {
  const data: any = { ...form.value }
  if (form.value.agent_type === 'local') {
    if (llmMode.value === 'select' && llmConfigId.value) {
      data.llm_config_id = llmConfigId.value
      data.llm_config = null
    } else {
      data.llm_config_id = null
      data.llm_config = llmConfig.value
    }
  }
  if (form.value.agent_type === 'http') {
    try {
      data.http_config = { ...httpConfig.value, headers: JSON.parse(httpConfigHeaders.value || '{}') }
    } catch {
      throw new Error('Headers JSON 格式错误')
    }
  }
  if (form.value.agent_type === 'claudecode') {
    data.claudecode_config = {
      settings_json: ccConfig.value.settings_json,
      model: ccConfig.value.model,
      max_turns: ccConfig.value.max_turns,
      work_dir: ccConfig.value.work_dir,
      permission_mode: ccConfig.value.permission_mode,
    }
  }
  data.mcp_links = selectedMcpServers.value.map((item: any) => ({
    mcp_server_id: item.mcp_server_id,
    enabled_tools: item.enabled_tools || [],
  }))
  data.kb_ids = selectedKbIds.value
  data.skill_ids = selectedSkillIds.value
  return data
}

async function handleSubmit() {
  if (submitting.value) return
  submitting.value = true
  try {
    const data = buildFormData()
    if (isEdit.value) {
      await agentsApi.update(agentId.value, data)
    } else {
      await agentsApi.create(data)
    }
    message.success('保存成功')
    router.push('/agents')
  } catch (e: any) {
    if (e instanceof Error) {
      message.error(e.message)
    } else {
      message.error(e.response?.data?.message || '操作失败')
    }
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadLlmConfigOptions()
  if (isEdit.value) {
    loadAgent()
  }
})
</script>
