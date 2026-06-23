<template>
  <div class="chat-test">
    <h1 class="text-2xl font-bold mb-4">对话测试</h1>

    <div class="chat-layout">
      <!-- Left: app list -->
      <div class="app-sidebar glass">
        <div class="app-sidebar-header">
          <span class="text-xs font-semibold text-[#8892a4] uppercase tracking-wider">应用列表</span>
          <a-button size="small" type="link" @click="$router.push('/apps')">管理</a-button>
        </div>
        <div class="app-list">
          <div
            v-for="app in apps"
            :key="app.id"
            class="app-item"
            :class="{ 'app-item--active': selectedAppId === app.id }"
            @click="selectApp(app.id)"
          >
            <div class="app-item-indicator" />
            <div class="app-item-content">
              <div class="text-sm font-medium text-[#e4e7ee] truncate">{{ app.name }}</div>
              <div class="text-xs text-[#535b6e] truncate">{{ app.workflow_name || '未绑定' }}</div>
            </div>
            <span v-if="selectedAppId === app.id" class="app-item-check text-[#00d4ff]">&blacktriangleright;</span>
          </div>
        </div>
        <div v-if="apps.length === 0" class="text-xs text-[#535b6e] text-center py-8">
          暂无应用，请先创建
        </div>
      </div>

      <!-- Right: chat window -->
      <div class="chat-area glass" v-if="selectedAppId">
        <ChatWindow :key="selectedAppId" :appId="selectedAppId" :apiKey="selectedAppApiKey" />
      </div>
      <div v-else class="chat-area glass flex items-center justify-center">
        <a-empty description="选择左侧应用开始测试" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { appsApi } from '@/api/apps'
import ChatWindow from '@/components/ChatWindow.vue'

const apps = ref<any[]>([])
const selectedAppId = ref<number | null>(null)
const selectedAppApiKey = ref('')

async function selectApp(id: number) {
  if (selectedAppId.value === id) return
  selectedAppId.value = id
  selectedAppApiKey.value = ''
  try {
    const res = await appsApi.get(id)
    selectedAppApiKey.value = res.data.data?.api_key || ''
  } catch { /* ignore */ }
}

onMounted(async () => {
  try {
    const res = await appsApi.list()
    apps.value = res.data.data || []
  } catch { /* ignore */ }
})
</script>

<style scoped>
.chat-test {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 140px);
}

.chat-layout {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

/* App sidebar */
.app-sidebar {
  width: 260px;
  min-width: 260px;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.app-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-subtle);
}
.app-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}
.app-item {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
}
.app-item:hover { background: rgba(0, 212, 255, 0.04); }
.app-item--active { background: rgba(0, 212, 255, 0.08); }
.app-item-indicator {
  width: 3px;
  height: 20px;
  border-radius: 0 3px 3px 0;
  margin-right: 10px;
  background: transparent;
  transition: background var(--duration-fast) var(--ease-out);
}
.app-item--active .app-item-indicator {
  background: #00d4ff;
  box-shadow: 0 0 8px #00d4ff88;
}
.app-item-content {
  flex: 1;
  min-width: 0;
}
.app-item-check {
  font-size: 12px;
  margin-left: 6px;
}

/* Chat area */
.chat-area {
  flex: 1;
  border-radius: var(--radius-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
