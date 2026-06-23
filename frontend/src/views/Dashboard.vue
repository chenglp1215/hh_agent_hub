<template>
  <div class="dashboard">
    <!-- Page title -->
    <div class="page-header" style="animation: fade-in-down 0.5s var(--ease-out)">
      <div class="flex items-center gap-3">
        <div class="w-1 h-6 rounded-full"
          style="background: linear-gradient(180deg, #00d4ff, #007acc); box-shadow: 0 0 12px #00d4ff66;" />
        <h1 class="text-xl font-bold font-display text-[#e4e7ee] tracking-wider">主控台</h1>
      </div>
      <span class="text-xs text-[#535b6e] font-mono">{{ dateStr }}</span>
    </div>

    <!-- Stats cards with animated counters -->
    <a-row :gutter="16" class="mb-8">
      <a-col :span="6" v-for="(card, i) in statCards" :key="card.key">
        <div
          class="stat-card glass"
          :style="{ animation: `fade-in-up 0.5s ${i * 0.08}s var(--ease-out) both` }"
          @click="card.to && $router.push(card.to)"
          :class="{ 'cursor-pointer': !!card.to }"
        >
          <div class="stat-card-inner">
            <div class="stat-icon" :style="{ background: card.gradient, boxShadow: card.glow }">
              <component :is="card.icon" />
            </div>
            <div class="stat-info">
              <span class="stat-label">{{ card.label }}</span>
              <span class="stat-value" :class="card.valueClass">
                <AnimatedCounter :target="card.value" :duration="1200" :delay="i * 100 + 300" />
              </span>
            </div>
          </div>
          <div class="stat-border" :style="{ background: card.gradient }" />
        </div>
      </a-col>
    </a-row>

    <a-row :gutter="16">
      <!-- Recent executions -->
      <a-col :span="16">
        <div
          class="glass"
          style="border-radius: var(--radius-lg); overflow: hidden; animation: fade-in-up 0.5s 0.3s var(--ease-out) both;"
        >
          <div class="panel-header">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-[#00d4ff]" style="box-shadow: 0 0 6px #00d4ff;" />
              <span class="text-sm font-semibold text-[#e4e7ee]">最近执行</span>
            </div>
            <a-button type="link" size="small" @click="$router.push('/monitor/traces')">查看全部</a-button>
          </div>

          <a-table
            :dataSource="recentTraces"
            :columns="traceColumns"
            rowKey="id"
            size="small"
            :pagination="false"
            :loading="loading"
            class="dashboard-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'execution_id'">
                <span class="font-mono text-xs text-[#00d4ff]">{{ (record.execution_id || '').slice(0, 12) }}...</span>
              </template>
              <template v-if="column.key === 'status'">
                <span class="status-dot" :class="`status-${record.status}`" />
                <span class="text-xs ml-2">{{ statusLabel(record.status) }}</span>
              </template>
              <template v-if="column.key === 'duration'">
                <span class="font-mono text-xs">{{ record.total_duration_ms }}ms</span>
              </template>
              <template v-if="column.key === 'actions'">
                <a-button size="small" type="link" @click="$router.push(`/monitor/traces/${record.execution_id}`)">
                  查看
                </a-button>
              </template>
            </template>
          </a-table>

          <a-empty
            v-if="!loading && recentTraces.length === 0"
            description="暂无执行记录"
            class="py-8"
          />
        </div>
      </a-col>

      <!-- Quick actions + Resource status -->
      <a-col :span="8">
        <div class="space-y-4" style="animation: fade-in-up 0.5s 0.4s var(--ease-out) both;">
          <!-- Quick actions -->
          <div class="glass" style="border-radius: var(--radius-lg); padding: 20px;">
            <div class="flex items-center gap-2 mb-4">
              <span class="w-2 h-2 rounded-full bg-[#f0a500]" style="box-shadow: 0 0 6px #f0a500;" />
              <span class="text-sm font-semibold text-[#e4e7ee]">快捷入口</span>
            </div>
            <div class="flex flex-col gap-3">
              <a-button type="primary" block size="large" class="!h-11 !rounded-lg !text-sm" @click="$router.push('/agents/create')">
                <template #icon><PlusOutlined /></template>
                创建 Agent
              </a-button>
              <a-button block size="large" class="!h-11 !rounded-lg !text-sm" @click="$router.push('/workflows/create')">
                <template #icon><ApartmentOutlined /></template>
                编排工作流
              </a-button>
              <a-button block size="large" class="!h-11 !rounded-lg !text-sm" @click="$router.push('/resources/mcp-servers/create')">
                <template #icon><ApiOutlined /></template>
                注册 MCP Server
              </a-button>
              <a-button block size="large" class="!h-11 !rounded-lg !text-sm" @click="$router.push('/monitor/chat-test')">
                <template #icon><MessageOutlined /></template>
                对话测试
              </a-button>
            </div>
          </div>

          <!-- Resource status -->
          <div class="glass" style="border-radius: var(--radius-lg); padding: 20px;">
            <div class="flex items-center gap-2 mb-4">
              <span class="w-2 h-2 rounded-full bg-[#00e676]" style="box-shadow: 0 0 6px #00e676;" />
              <span class="text-sm font-semibold text-[#e4e7ee]">资源状态</span>
            </div>
            <div class="space-y-3">
              <div class="resource-item" v-for="r in resourceItems" :key="r.key">
                <div class="flex items-center gap-2">
                  <span class="w-1.5 h-1.5 rounded-full" :style="{ background: r.color, boxShadow: `0 0 6px ${r.color}` }" />
                  <span class="text-xs text-[#8892a4]">{{ r.label }}</span>
                </div>
                <span class="font-mono text-sm" :style="{ color: r.color }">{{ r.value }}</span>
              </div>
            </div>
          </div>
        </div>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  RobotOutlined, ApartmentOutlined, AppstoreOutlined, ThunderboltOutlined,
  PlusOutlined, ApiOutlined, MessageOutlined,
} from '@ant-design/icons-vue'
import { dashboardApi } from '@/api/dashboard'
import AnimatedCounter from '@/components/AnimatedCounter.vue'

const loading = ref(false)
const stats = ref({ agents: 0, workflows: 0, apps: 0, today_executions: 0, mcp_online: 0, kb_count: 0, skill_count: 0 })
const recentTraces = ref<any[]>([])

const dateStr = computed(() => {
  return new Date().toLocaleDateString('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })
})

const statCards = computed(() => [
  {
    key: 'agents', label: 'Agent 总数', value: stats.value.agents,
    icon: RobotOutlined, to: '/agents',
    gradient: 'linear-gradient(135deg, #00d4ff, #0088cc)',
    glow: '0 0 16px rgba(0,212,255,0.3)',
    valueClass: 'text-[#00d4ff]',
  },
  {
    key: 'workflows', label: '工作流总数', value: stats.value.workflows,
    icon: ApartmentOutlined, to: '/workflows',
    gradient: 'linear-gradient(135deg, #7c5cfc, #5b3ecc)',
    glow: '0 0 16px rgba(124,92,252,0.3)',
    valueClass: 'text-[#9b7cfc]',
  },
  {
    key: 'apps', label: '应用总数', value: stats.value.apps,
    icon: AppstoreOutlined, to: '/apps',
    gradient: 'linear-gradient(135deg, #00e676, #00b34d)',
    glow: '0 0 16px rgba(0,230,118,0.3)',
    valueClass: 'text-[#00e676]',
  },
  {
    key: 'executions', label: '今日执行', value: stats.value.today_executions,
    icon: ThunderboltOutlined, to: null,
    gradient: 'linear-gradient(135deg, #f0a500, #cc8800)',
    glow: '0 0 16px rgba(240,165,0,0.3)',
    valueClass: 'text-[#f0a500]',
  },
])

const resourceItems = computed(() => [
  { key: 'mcp', label: 'MCP Server 在线', value: stats.value.mcp_online, color: '#00e676' },
  { key: 'kb', label: '知识库', value: stats.value.kb_count, color: '#00d4ff' },
  { key: 'skills', label: 'Skill 模板', value: stats.value.skill_count, color: '#f0a500' },
])

const traceColumns = [
  { title: 'Execution ID', key: 'execution_id', ellipsis: true },
  { title: '状态', key: 'status', width: 90 },
  { title: '耗时', key: 'duration', width: 80 },
  { title: '', key: 'actions', width: 60 },
]

function statusLabel(s: string) {
  return { running: '运行中', success: '成功', failed: '失败' }[s] || s
}

onMounted(async () => {
  loading.value = true
  try {
    const res = await dashboardApi.getStats()
    const d = res.data.data
    stats.value = {
      agents: d.agents || 0,
      workflows: d.workflows || 0,
      apps: d.apps || 0,
      today_executions: d.today_executions || 0,
      mcp_online: d.mcp_online || 0,
      kb_count: d.kb_count || 0,
      skill_count: d.skill_count || 0,
    }
    recentTraces.value = d.recent_traces || []
  } catch {
    // silent fail, keep zeros
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.dashboard {
  animation: fade-in 0.4s var(--ease-out);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

/* Stat cards */
.stat-card {
  position: relative;
  border-radius: var(--radius-lg);
  padding: 20px;
  overflow: hidden;
  transition: transform var(--duration-normal) var(--ease-out),
              border-color var(--duration-normal) var(--ease-out);
}
.stat-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-glow) !important;
}

.stat-card-inner {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  min-width: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #fff;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.stat-value {
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-border {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  opacity: 0.6;
}

/* Panel header */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-subtle);
}

/* Status dots */
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  vertical-align: middle;
}
.status-running { background: #00d4ff; box-shadow: 0 0 6px #00d4ff; animation: glow-pulse 2s ease-in-out infinite; }
.status-success { background: #00e676; box-shadow: 0 0 6px #00e676; }
.status-failed { background: #ff3d4f; box-shadow: 0 0 6px #ff3d4f; }

/* Resource items */
.resource-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: rgba(0, 0, 0, 0.15);
}

/* Dashboard table */
.dashboard-table :deep(.ant-table) {
  background: transparent !important;
}
.dashboard-table :deep(.ant-table-thead > tr > th) {
  background: rgba(0, 0, 0, 0.15) !important;
  padding: 10px 16px !important;
}
.dashboard-table :deep(.ant-table-tbody > tr > td) {
  padding: 10px 16px !important;
}
</style>
