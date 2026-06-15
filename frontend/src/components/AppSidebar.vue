<template>
  <a-layout-sider v-model:collapsed="collapsed" collapsible class="!bg-[#010102]" :style="{ borderRight: '1px solid #1e1e20' }">
    <div class="h-16 flex items-center justify-center text-white font-bold text-lg border-b border-[#1e1e20]">
      <span v-if="!collapsed" class="text-[#5e6ad2]">Agent Hub</span>
      <span v-else class="text-[#5e6ad2]">AH</span>
    </div>
    <a-menu
      v-model:selectedKeys="selectedKeys"
      v-model:openKeys="openKeys"
      mode="inline"
      theme="dark"
      :style="{ background: '#010102' }"
      @click="handleMenuClick"
    >
      <a-menu-item key="/dashboard">
        <template #icon><DashboardOutlined /></template>
        <span>主控台</span>
      </a-menu-item>

      <a-sub-menu key="agents">
        <template #icon><RobotOutlined /></template>
        <template #title>Agent 管理</template>
        <a-menu-item key="/agents">Agent 列表</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="workflows">
        <template #icon><ApartmentOutlined /></template>
        <template #title>工作流编排</template>
        <a-menu-item key="/workflows">工作流列表</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="apps">
        <template #icon><AppstoreOutlined /></template>
        <template #title>应用管理</template>
        <a-menu-item key="/apps">应用列表</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="resources">
        <template #icon><DatabaseOutlined /></template>
        <template #title>资源目录</template>
        <a-menu-item key="/resources/mcp-servers">MCP Server 管理</a-menu-item>
        <a-menu-item key="/resources/knowledge-bases">知识库管理</a-menu-item>
        <a-menu-item key="/resources/skills">Skill 管理</a-menu-item>
        <a-menu-item key="/projects">项目管理</a-menu-item>
        <a-menu-item key="/claude-settings">Claude Settings</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="monitor">
        <template #icon><LineChartOutlined /></template>
        <template #title>监控</template>
        <a-menu-item key="/monitor/traces">执行追踪</a-menu-item>
        <a-menu-item key="/monitor/chat-test">对话测试</a-menu-item>
      </a-sub-menu>

      <a-sub-menu key="settings" v-if="userStore.isAdmin">
        <template #icon><SettingOutlined /></template>
        <template #title>系统设置</template>
        <a-menu-item key="/settings">基础配置</a-menu-item>
        <a-menu-item key="/settings/llm-configs">LLM 配置</a-menu-item>
      </a-sub-menu>
    </a-menu>
  </a-layout-sider>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import {
  DashboardOutlined, RobotOutlined, ApartmentOutlined,
  AppstoreOutlined, DatabaseOutlined, LineChartOutlined, SettingOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const collapsed = ref(false)
const selectedKeys = ref<string[]>([route.path])
const openKeys = ref<string[]>(['agents', 'workflows', 'apps', 'resources', 'monitor', 'settings'])

watch(() => route.path, (path) => {
  selectedKeys.value = [path]
  // Auto-expand parent submenu when navigating
  const segs = path.split('/')
  const parentKey = segs[1] // e.g. 'agents', 'workflows', 'resources', 'monitor'
  if (parentKey && !openKeys.value.includes(parentKey)) {
    openKeys.value = [...openKeys.value, parentKey]
  }
})

function handleMenuClick({ key }: { key: string }) {
  router.push(key)
}
</script>
