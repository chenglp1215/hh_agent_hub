<template>
  <div>
    <div class="flex items-center gap-3 mb-6">
      <div class="w-1 h-6 rounded-full" style="background: linear-gradient(180deg, #00d4ff, #007acc);" />
      <h1 class="text-xl font-bold text-[#e4e7ee] tracking-wider">系统设置</h1>
    </div>

    <a-tabs v-model:activeKey="activeTab" class="settings-tabs">
      <!-- LLM 配置 -->
      <a-tab-pane key="llm" tab="LLM 配置">
        <div class="tab-content">
          <div class="section-header">
            <span class="section-dot" style="background:#5e6ad2" />
            <span class="section-title">默认 LLM</span>
            <a-button size="small" type="primary" ghost @click="$router.push('/settings/llm-configs')">管理配置</a-button>
          </div>
          <a-row :gutter="16">
            <a-col :span="6">
              <div class="info-item">
                <span class="info-label">提供商</span>
                <span class="info-value">{{ getConfig('llm.default.provider') }}</span>
              </div>
            </a-col>
            <a-col :span="6">
              <div class="info-item">
                <span class="info-label">模型</span>
                <span class="info-value">{{ getConfig('llm.default.model') }}</span>
              </div>
            </a-col>
            <a-col :span="6">
              <div class="info-item">
                <span class="info-label">温度</span>
                <span class="info-value font-mono">{{ getConfig('llm.default.temperature') }}</span>
              </div>
            </a-col>
            <a-col :span="6">
              <div class="info-item">
                <span class="info-label">Max Tokens</span>
                <span class="info-value font-mono">{{ getConfig('system.max_tokens') }}</span>
              </div>
            </a-col>
          </a-row>
        </div>
      </a-tab-pane>

      <!-- 企微机器人 -->
      <a-tab-pane key="wecom" tab="企微机器人">
        <div class="tab-content">
          <!-- 连接状态卡片 -->
          <div class="status-card" :class="wecomBotStatus.connected ? 'status-ok' : 'status-off'">
            <div class="status-icon">
              <span v-if="wecomBotStatus.connected" class="status-dot-on" />
              <span v-else class="status-dot-off" />
            </div>
            <div class="status-info">
              <span class="status-label">{{ wecomBotStatus.connected ? '已连接' : '未连接' }}</span>
              <span v-if="wecomBotStatus.connected_at" class="status-detail">连接时间: {{ wecomBotStatus.connected_at }}</span>
              <span v-if="wecomBotStatus.bot_id" class="status-detail">Bot ID: {{ wecomBotStatus.bot_id }}</span>
            </div>
          </div>

          <!-- 配置表单 -->
          <div class="section-header mt-4">
            <span class="section-dot" style="background:#00e676" />
            <span class="section-title">凭证配置</span>
          </div>
          <a-form layout="vertical" class="max-w-lg">
            <a-form-item label="Bot ID">
              <a-input-password v-model:value="wecomForm.bot_id" placeholder="企微智能机器人 Bot ID" />
            </a-form-item>
            <a-form-item label="Bot Secret">
              <a-input-password v-model:value="wecomForm.bot_secret" placeholder="企微智能机器人 Bot Secret" />
            </a-form-item>
            <a-form-item>
              <a-button type="primary" :loading="wecomSaving" @click="saveWecomConfig">保存配置</a-button>
            </a-form-item>
          </a-form>

          <a-alert v-if="!wecomBotStatus.connected && (wecomForm.bot_id || wecomBotStatus.bot_id)" type="warning" show-icon>
            <template #message>已配置凭证，等待 wecom-bot 容器连接...</template>
          </a-alert>
        </div>
      </a-tab-pane>

      <!-- 安全配置 -->
      <a-tab-pane key="security" tab="安全">
        <div class="tab-content">
          <div class="section-header">
            <span class="section-dot" style="background:#f0a500" />
            <span class="section-title">安全策略</span>
          </div>
          <a-row :gutter="16">
            <a-col :span="8">
              <div class="info-item">
                <span class="info-label">会话过期时间</span>
                <span class="info-value font-mono">{{ getConfig('system.session_ttl') }}s</span>
              </div>
            </a-col>
            <a-col :span="8">
              <div class="info-item">
                <span class="info-label">默认限流</span>
                <span class="info-value font-mono">{{ getConfig('system.rate_limit.default') }} 次/分</span>
              </div>
            </a-col>
          </a-row>
        </div>
      </a-tab-pane>

      <!-- 关于 -->
      <a-tab-pane key="about" tab="关于">
        <div class="tab-content">
          <div class="about-grid">
            <div class="about-item" v-for="item in aboutItems" :key="item.label">
              <span class="about-label">{{ item.label }}</span>
              <span class="about-value">{{ item.value }}</span>
            </div>
          </div>
        </div>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import client from '@/api/client'

const activeTab = ref('llm')
const configs = ref<any[]>([])

function getConfig(key: string): string {
  return configs.value.find((c: any) => c.config_key === key)?.config_value || '-'
}

const aboutItems = [
  { label: '系统名称', value: '多Agent协同平台' },
  { label: '版本', value: '1.0.0' },
  { label: '数据库', value: 'MySQL 8.0' },
  { label: 'Agent 类型', value: 'local / http / claudecode' },
  { label: '工作流引擎', value: 'LangGraph' },
  { label: '前端框架', value: 'Vue 3 + Ant Design Vue' },
]

// 企微机器人配置
const wecomForm = reactive({ bot_id: '', bot_secret: '' })
const wecomSaving = ref(false)
const wecomBotStatus = reactive({
  connected: false, bot_id: '', bot_name: '', connected_at: '', updated_at: '',
})

async function fetchWecomBotStatus() {
  try {
    const res = await client.get('/configs/wecom-bot-status')
    Object.assign(wecomBotStatus, res.data.data || {})
  } catch {}
}

async function saveWecomConfig() {
  if (!wecomForm.bot_id || !wecomForm.bot_secret) {
    message.warning('请填写 Bot ID 和 Bot Secret')
    return
  }
  wecomSaving.value = true
  try {
    await client.put('/configs/wecom.bot_id', { config_value: wecomForm.bot_id, config_type: 'secret', description: '企微智能机器人 Bot ID' })
    await client.put('/configs/wecom.bot_secret', { config_value: wecomForm.bot_secret, config_type: 'secret', description: '企微智能机器人 Bot Secret' })
    message.success('保存成功，wecom-bot 容器将自动重连')
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
  wecomForm.bot_id = configs.value.find((c: any) => c.config_key === 'wecom.bot_id')?.config_value || ''
  wecomForm.bot_secret = configs.value.find((c: any) => c.config_key === 'wecom.bot_secret')?.config_value || ''
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

<style scoped>
.settings-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 0;
}
.settings-tabs :deep(.ant-tabs-nav::before) {
  border-bottom-color: var(--border-subtle);
}
.settings-tabs :deep(.ant-tabs-tab) {
  color: var(--text-muted);
  font-size: 13px;
}
.settings-tabs :deep(.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: var(--accent) !important;
}
.settings-tabs :deep(.ant-tabs-ink-bar) {
  background: var(--accent);
}

.tab-content {
  padding: 20px 0;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.section-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
}
.info-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.info-value {
  font-size: 14px;
  color: var(--text-primary);
}

.status-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
}
.status-ok {
  background: rgba(0, 230, 118, 0.06);
  border-color: rgba(0, 230, 118, 0.2);
}
.status-off {
  background: rgba(255, 61, 79, 0.06);
  border-color: rgba(255, 61, 79, 0.2);
}
.status-dot-on {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #00e676;
  box-shadow: 0 0 8px #00e676;
  display: block;
}
.status-dot-off {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #ff3d4f;
  box-shadow: 0 0 8px #ff3d4f;
  display: block;
}
.status-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.status-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.status-detail {
  font-size: 12px;
  color: var(--text-muted);
  font-family: monospace;
}

.about-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.about-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px;
  border-radius: var(--radius-sm);
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
}
.about-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.about-value {
  font-size: 14px;
  color: var(--text-primary);
}
</style>
