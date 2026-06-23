<template>
  <a-layout-sider
    v-model:collapsed="collapsed"
    collapsible
    width="240"
    :trigger="null"
    class="sidebar"
  >
    <!-- Logo area -->
    <div class="logo-area" @click="$router.push('/dashboard')">
      <div class="logo-icon">
        <span class="logo-text">{{ collapsed ? 'A' : 'AH' }}</span>
      </div>
      <transition name="logo-slide">
        <div v-if="!collapsed" class="logo-brand">
          <span class="logo-title">Agent Hub</span>
          <span class="logo-subtitle">协同平台</span>
        </div>
      </transition>
    </div>

    <!-- Navigation -->
    <a-menu
      v-model:selectedKeys="selectedKeys"
      v-model:openKeys="openKeys"
      mode="inline"
      theme="dark"
      class="nav-menu"
      @click="handleMenuClick"
    >
      <a-menu-item key="/dashboard" class="menu-item">
        <template #icon>
          <span class="menu-icon"><DashboardOutlined /></span>
        </template>
        <span>主控台</span>
      </a-menu-item>

      <a-sub-menu key="agents" class="menu-sub">
        <template #icon>
          <span class="menu-icon"><RobotOutlined /></span>
        </template>
        <template #title>Agent 管理</template>
        <a-menu-item key="/agents">Agent 列表</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="workflows" class="menu-sub">
        <template #icon>
          <span class="menu-icon"><ApartmentOutlined /></span>
        </template>
        <template #title>工作流编排</template>
        <a-menu-item key="/workflows">工作流列表</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="apps" class="menu-sub">
        <template #icon>
          <span class="menu-icon"><AppstoreOutlined /></span>
        </template>
        <template #title>应用管理</template>
        <a-menu-item key="/apps">应用列表</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="triggers" class="menu-sub">
        <template #icon>
          <span class="menu-icon"><FieldTimeOutlined /></span>
        </template>
        <template #title>执行管理</template>
        <a-menu-item key="/triggers">触发器列表</a-menu-item>
        <a-menu-item key="/notifications">通知管理</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="resources" class="menu-sub">
        <template #icon>
          <span class="menu-icon"><DatabaseOutlined /></span>
        </template>
        <template #title>资源目录</template>
        <a-menu-item key="/resources/mcp-servers">MCP Server 管理</a-menu-item>
        <a-menu-item key="/resources/knowledge-bases">知识库管理</a-menu-item>
        <a-menu-item key="/resources/skills">Skill 管理</a-menu-item>
        <a-menu-item key="/projects">项目管理</a-menu-item>
        <a-menu-item key="/claude-settings">Claude Settings</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="monitor" class="menu-sub">
        <template #icon>
          <span class="menu-icon"><LineChartOutlined /></span>
        </template>
        <template #title>监控</template>
        <a-menu-item key="/monitor/traces">执行追踪</a-menu-item>
        <a-menu-item key="/monitor/chat-logs">对话日志</a-menu-item>
        <a-menu-item key="/monitor/chat-test">对话测试</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="settings" v-if="userStore.isAdmin" class="menu-sub">
        <template #icon>
          <span class="menu-icon"><SettingOutlined /></span>
        </template>
        <template #title>系统设置</template>
        <a-menu-item key="/settings">基础配置</a-menu-item>
        <a-menu-item key="/settings/llm-configs">LLM 配置</a-menu-item>
      </a-sub-menu>
    </a-menu>

    <!-- Collapse toggle -->
    <div class="collapse-btn" @click="collapsed = !collapsed">
      <MenuFoldOutlined v-if="!collapsed" />
      <MenuUnfoldOutlined v-else />
    </div>
  </a-layout-sider>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import {
  DashboardOutlined, RobotOutlined, ApartmentOutlined,
  AppstoreOutlined, DatabaseOutlined, LineChartOutlined, SettingOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined, FieldTimeOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const collapsed = ref(false)
const selectedKeys = ref<string[]>([route.path])
const openKeys = ref<string[]>(['agents', 'workflows', 'apps', 'triggers', 'resources', 'monitor', 'settings'])

watch(() => route.path, (path) => {
  selectedKeys.value = [path]
  const segs = path.split('/')
  const parentKey = segs[1]
  if (parentKey && !openKeys.value.includes(parentKey)) {
    openKeys.value = [...openKeys.value, parentKey]
  }
})

function handleMenuClick({ key }: { key: string }) {
  router.push(key)
}
</script>

<style scoped>
.sidebar {
  position: relative !important;
  z-index: 10 !important;
  background: linear-gradient(180deg, rgba(8, 12, 21, 0.95) 0%, rgba(3, 5, 10, 0.98) 100%) !important;
  backdrop-filter: blur(24px) !important;
  -webkit-backdrop-filter: blur(24px) !important;
  border-right: 1px solid var(--border-subtle) !important;
  box-shadow: 4px 0 32px rgba(0, 0, 0, 0.3) !important;
}

.logo-area {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 12px;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  overflow: hidden;
  transition: background var(--duration-fast) var(--ease-out);
}
.logo-area:hover {
  background: rgba(0, 212, 255, 0.04);
}

.logo-icon {
  width: 36px;
  height: 36px;
  min-width: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #00d4ff, #007acc);
  box-shadow: 0 0 16px rgba(0, 212, 255, 0.3), 0 0 32px rgba(0, 212, 255, 0.1);
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-weight: 700;
  font-size: 14px;
  color: #fff;
  text-shadow: 0 0 8px rgba(255,255,255,0.5);
}

.logo-brand {
  display: flex;
  flex-direction: column;
  white-space: nowrap;
}
.logo-title {
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: #e4e7ee;
  letter-spacing: 0.06em;
  line-height: 1.1;
}
.logo-subtitle {
  font-size: 10px;
  color: #535b6e;
  letter-spacing: 0.1em;
}

.logo-slide-enter-active {
  transition: all 300ms var(--ease-out);
}
.logo-slide-leave-active {
  transition: all 200ms var(--ease-in-out);
}
.logo-slide-enter-from,
.logo-slide-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}

/* Navigation menu */
.nav-menu {
  background: transparent !important;
  border-inline-end: none !important;
  padding: 8px 0;
  margin-top: 4px;
}

/* Override Ant Design menu styles for futuristic look */
:deep(.ant-menu) {
  background: transparent !important;
}
:deep(.ant-menu-item),
:deep(.ant-menu-submenu-title) {
  margin: 2px 8px !important;
  border-radius: 8px !important;
  transition: all var(--duration-fast) var(--ease-out) !important;
  color: #8892a4 !important;
  position: relative !important;
  overflow: hidden !important;
}
:deep(.ant-menu-item:hover),
:deep(.ant-menu-submenu-title:hover) {
  color: #e4e7ee !important;
  background: rgba(0, 212, 255, 0.06) !important;
}
:deep(.ant-menu-item-selected) {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.12), rgba(0, 180, 230, 0.06)) !important;
  color: #00d4ff !important;
  font-weight: 600 !important;
}
:deep(.ant-menu-item-selected::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: linear-gradient(180deg, #00d4ff, #007acc);
  border-radius: 0 3px 3px 0;
  box-shadow: 0 0 8px #00d4ff88;
}
:deep(.ant-menu-submenu-arrow) {
  color: #535b6e !important;
}
:deep(.ant-menu-submenu-open .ant-menu-submenu-arrow) {
  color: #00d4ff !important;
}
:deep(.ant-menu-submenu-open > .ant-menu-submenu-title) {
  color: #e4e7ee !important;
}
:deep(.ant-menu-inline .ant-menu-item) {
  padding-left: 52px !important;
}
:deep(.ant-menu .ant-menu-item .anticon) {
  color: inherit !important;
}

.menu-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  font-size: 16px;
  opacity: 0.7;
}

/* Collapse button */
.collapse-btn {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #535b6e;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  border: 1px solid transparent;
}
.collapse-btn:hover {
  color: #00d4ff;
  background: rgba(0, 212, 255, 0.08);
  border-color: rgba(0, 212, 255, 0.2);
  box-shadow: 0 0 16px rgba(0, 212, 255, 0.15);
}
</style>
