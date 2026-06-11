<template>
  <a-layout class="min-h-screen">
    <a-layout-sider v-model:collapsed="collapsed" collapsible class="!bg-[#010102]">
      <div class="h-16 flex items-center justify-center text-white font-bold text-lg">
        <span v-if="!collapsed">Agent Hub</span>
        <span v-else>AH</span>
      </div>
      <a-menu v-model:selectedKeys="selectedKeys" mode="inline" theme="dark" :style="{ background: '#010102' }" @click="handleMenuClick">
        <a-menu-item key="/dashboard">
          <DashboardOutlined /><span>主控台</span>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-content class="p-6 bg-[#0a0a0b]">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { DashboardOutlined } from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const collapsed = ref(false)
const selectedKeys = ref<string[]>([route.path])

watch(() => route.path, (path) => { selectedKeys.value = [path] })

function handleMenuClick({ key }: { key: string }) {
  router.push(key)
}
</script>
