<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '创建' }} Agent</h1>

    <a-card class="max-w-3xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <!-- Basic Info -->
        <h3 class="text-lg font-semibold mb-4 text-[#00d4ff]">基础信息</h3>
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
                <a-select-option value="a2a">A2A Agent</a-select-option>
                <a-select-option value="claudecode">Claude Code</a-select-option>
                <a-select-option value="reasonix">Reasonix (DeepSeek)</a-select-option>
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

        <!-- Supervisor Config -->
        <template v-if="form.role === 'supervisor'">
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#00d4ff]">Supervisor 配置</h3>
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="行为模式">
                <a-select v-model:value="supervisorPromptTemplate">
                  <a-select-option value="free_route">自由路由型</a-select-option>
                  <a-select-option value="strict_flow">流程遵从型</a-select-option>
                  <a-select-option value="quick_qa">快速问答型</a-select-option>
                  <a-select-option value="iterative">迭代优化型</a-select-option>
                </a-select>
                <div class="text-xs text-[#535b6e] mt-1">
                  Supervisor 的调度行为模式，跟着 Agent 走
                </div>
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item label="自定义 Prompt 覆盖" v-if="userStore.isAdmin">
            <a-textarea v-model:value="customPromptOverride" :rows="4" placeholder="留空则使用上方选择的默认模板..." />
            <div class="text-xs text-[#535b6e] mt-1">
              自定义 Prompt 将覆盖默认模板，仅管理员可设置
            </div>
          </a-form-item>
          <a-form-item label="Prompt 补充说明">
            <a-textarea v-model:value="supervisorPromptSupplement" :rows="3" placeholder="对最终工作总结的补充说明、额外的输出格式要求等..." />
            <div class="text-xs text-[#535b6e] mt-1">
              补充内容将追加到 Prompt 末尾，不会覆盖模板。可用于对工作总结内容、输出格式等进行额外说明
            </div>
          </a-form-item>
        </template>

        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>

        <!-- LLM Config (local agent) -->
        <template v-if="form.agent_type === 'local'">
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#00d4ff]">LLM 配置</h3>

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
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#00d4ff]">HTTP 配置</h3>
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

        <!-- A2A Config -->
        <template v-if="form.agent_type === 'a2a'">
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#00d4ff]">A2A 对端配置</h3>
          <a-form-item label="Agent Card URL" required>
            <a-input v-model:value="a2aConfig.agent_card_url" placeholder="http://peer-agent:8080/api/v1/mdr_log_analyze_mcp/a2a/agent-card.json" />
          </a-form-item>
          <a-form-item label="请求头 (JSON)">
            <a-textarea v-model:value="a2aConfigHeaders" :rows="3" placeholder='{"X-API-Key": "sk-test-key-123"}' />
          </a-form-item>
          <a-form-item label="超时(秒)">
            <a-input-number v-model:value="a2aConfig.timeout" :min="5" :max="300" class="w-full" />
          </a-form-item>
        </template>

        <!-- Claude Code Config -->
        <template v-if="form.agent_type === 'claudecode'">
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#00d4ff]">Claude Code 配置</h3>

          <a-form-item label="关联项目">
            <a-select
              v-model:value="ccConfig.project_registry_id"
              placeholder="选择项目..."
              :options="projectOptions"
              show-search
              filter-option
              allow-clear
              :loading="loadingProjects"
            />
          </a-form-item>
          <a-form-item label="关联 Settings">
            <a-select
              v-model:value="ccConfig.settings_registry_id"
              placeholder="选择 Claude Settings..."
              :options="settingsOptions"
              show-search
              filter-option
              allow-clear
              :loading="loadingSettings"
            />
          </a-form-item>
        </template>

        <!-- Reasonix Config -->
        <template v-if="form.agent_type === 'reasonix'">
          <h3 class="text-lg font-semibold mb-4 mt-4 text-[#00d4ff]">Reasonix 配置 (DeepSeek)</h3>

          <a-form-item label="选择配置">
            <a-select
              v-model:value="rxConfig.settings_registry_id"
              placeholder="选择 Reasonix 配置..."
              :options="reasonixSettingsOptions"
              show-search
              filter-option
              allow-clear
              :loading="loadingReasonixSettings"
            />
            <div class="text-xs text-[#535b6e] mt-1">
              在 <router-link to="/reasonix-settings" class="text-[#5e6ad2]">Reasonix 配置管理</router-link> 中创建和管理配置
            </div>
          </a-form-item>
          <a-form-item label="关联项目">
            <a-select
              v-model:value="rxConfig.project_registry_id"
              placeholder="选择项目..."
              :options="projectOptions"
              show-search
              filter-option
              allow-clear
              :loading="loadingProjects"
            />
          </a-form-item>
        </template>

        <!-- System Prompt (hidden for supervisor - uses prompt template instead) -->
        <template v-if="form.role !== 'supervisor'">
        <h3 class="text-lg font-semibold mb-4 mt-4 text-[#00d4ff]">System Prompt</h3>
        <a-form-item>
          <a-textarea v-model:value="form.system_prompt" :rows="6" placeholder="你是..." />
        </a-form-item>
        </template>

        <!-- Resource Selection -->
        <h3 class="text-lg font-semibold mb-4 mt-4 text-[#00d4ff]">资源目录选择</h3>
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
import { useUserStore } from '@/stores/user'
import { projectsApi } from '@/api/projects'
import { claudeSettingsApi } from '@/api/claudeSettings'
import McpServerSelector from '@/components/McpServerSelector.vue'
import KnowledgeBaseSelector from '@/components/KnowledgeBaseSelector.vue'
import SkillsSelector from '@/components/SkillsSelector.vue'
import { llmConfigsApi } from '@/api/llmConfigs'
import { reasonixSettingsApi } from '@/api/reasonixSettings'

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
const userStore = useUserStore()
const supervisorPromptTemplate = ref('free_route')
const customPromptOverride = ref('')
const supervisorPromptSupplement = ref('')
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
const a2aConfig = ref<any>({
  agent_card_url: '',
  headers: {},
  timeout: 30,
})
const a2aConfigHeaders = ref('{}')
const ccConfig = ref<any>({
  project_registry_id: undefined,
  settings_registry_id: undefined,
})
const rxConfig = ref<any>({
  settings_registry_id: undefined,
  project_registry_id: undefined,
})

const loadingProjects = ref(false)
const projectOptions = ref<{ value: number; label: string }[]>([])
const loadingSettings = ref(false)
const settingsOptions = ref<{ value: number; label: string }[]>([])

async function loadProjectOptions() {
  loadingProjects.value = true
  try {
    const res = await projectsApi.list()
    const list = res.data.data || []
    projectOptions.value = list.map((p: any) => ({ value: p.id, label: `${p.display_name || p.name} (${p.git_repo_url})` }))
  } catch {
    // ignore
  } finally {
    loadingProjects.value = false
  }
}

async function loadSettingsOptions() {
  loadingSettings.value = true
  try {
    const res = await claudeSettingsApi.list()
    const list = res.data.data || []
    settingsOptions.value = list.map((s: any) => ({ value: s.id, label: `${s.display_name || s.name} (${s.model})` }))
  } catch {
    // ignore
  } finally {
    loadingSettings.value = false
  }
}

const loadingReasonixSettings = ref(false)
const reasonixSettingsOptions = ref<{ value: number; label: string }[]>([])

async function loadReasonixSettingsOptions() {
  loadingReasonixSettings.value = true
  try {
    const res = await reasonixSettingsApi.list()
    const list = res.data.data || []
    reasonixSettingsOptions.value = list.map((s: any) => ({ value: s.id, label: `${s.display_name || s.name} (${s.model})` }))
  } catch {
    // ignore
  } finally {
    loadingReasonixSettings.value = false
  }
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
    supervisorPromptTemplate.value = d.supervisor_prompt_template || 'free_route'
    customPromptOverride.value = d.custom_prompt_override || ''
    supervisorPromptSupplement.value = d.supervisor_prompt_supplement || ''
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
    if (d.a2a_config) {
      a2aConfig.value = d.a2a_config
      a2aConfigHeaders.value = JSON.stringify(d.a2a_config.headers || {}, null, 2)
    }
    if (d.claudecode_config) {
      // Support both old and new claudecode_config format
      if (d.claudecode_config.project_registry_id !== undefined) {
        ccConfig.value.project_registry_id = d.claudecode_config.project_registry_id
        ccConfig.value.settings_registry_id = d.claudecode_config.settings_registry_id
      } else {
        // Old format — ignore inline fields, leave selectors empty
        ccConfig.value.project_registry_id = undefined
        ccConfig.value.settings_registry_id = undefined
      }
    }
    if (d.reasonix_config) {
      rxConfig.value = {
        settings_registry_id: d.reasonix_config.settings_registry_id || undefined,
        project_registry_id: d.reasonix_config.project_registry_id || undefined,
      }
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
  if (form.value.agent_type === 'a2a') {
    if (!a2aConfig.value.agent_card_url?.trim()) {
      throw new Error('请输入 Agent Card URL')
    }
    try {
      data.a2a_config = { ...a2aConfig.value, headers: JSON.parse(a2aConfigHeaders.value || '{}') }
    } catch {
      throw new Error('A2A Headers JSON 格式错误')
    }
  }
  if (form.value.agent_type === 'claudecode') {
    data.claudecode_config = {
      project_registry_id: ccConfig.value.project_registry_id || undefined,
      settings_registry_id: ccConfig.value.settings_registry_id || undefined,
    }
  }
  if (form.value.agent_type === 'reasonix') {
    if (!rxConfig.value.settings_registry_id) {
      throw new Error('请选择 Reasonix 配置')
    }
    data.reasonix_config = {
      settings_registry_id: rxConfig.value.settings_registry_id || undefined,
      project_registry_id: rxConfig.value.project_registry_id || undefined,
    }
  }
  data.mcp_links = selectedMcpServers.value.map((item: any) => ({
    mcp_server_id: item.mcp_server_id,
    enabled_tools: item.enabled_tools || [],
  }))
  data.kb_ids = selectedKbIds.value
  data.skill_ids = selectedSkillIds.value
  data.supervisor_prompt_template = supervisorPromptTemplate.value
  data.custom_prompt_override = customPromptOverride.value || null
  data.supervisor_prompt_supplement = supervisorPromptSupplement.value || null
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
  loadProjectOptions()
  loadSettingsOptions()
  loadReasonixSettingsOptions()
  if (isEdit.value) {
    loadAgent()
  }
})
</script>
