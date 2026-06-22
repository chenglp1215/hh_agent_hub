<template>
  <a-layout class="min-h-screen relative">
    <ParticlesBackground />

    <AppSidebar />

    <a-layout class="relative z-10">
      <!-- Glass header -->
      <a-layout-header
        class="glass-strong flex items-center justify-between px-6 border-b border-[#151a28]"
        style="height: 56px; line-height: 56px"
      >
        <div class="flex items-center gap-3">
          <div class="w-1.5 h-1.5 rounded-full animate-pulse bg-[#00d4ff]"
            style="box-shadow: 0 0 8px #00d4ff, 0 0 16px #00d4ff44" />
          <a-breadcrumb>
            <a-breadcrumb-item v-for="(item, i) in breadcrumbs" :key="i">
              {{ item }}
            </a-breadcrumb-item>
          </a-breadcrumb>
        </div>

        <div class="flex items-center gap-4">
          <!-- Ctrl+K hint -->
          <div
            class="flex items-center gap-1.5 px-3 py-1 rounded-md cursor-pointer text-xs text-[#535b6e] border border-[#1e2538] hover:border-[#00d4ff44] hover:text-[#00d4ff] transition-all"
            @click="cmdPalette?.open()"
          >
            <SearchOutlined class="text-[10px]" />
            <span class="hidden sm:inline">搜索</span>
            <kbd class="font-mono text-[10px] px-1 rounded bg-[#0a0d14] border border-[#1e2538]">Ctrl+K</kbd>
          </div>
          <span class="text-xs text-[#535b6e] font-mono hidden sm:inline">
            {{ timeStr }}
          </span>
          <div class="flex items-center gap-2">
            <div
              class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
              style="background: linear-gradient(135deg, #00d4ff, #0088cc); color: #fff; text-shadow: 0 0 8px rgba(0,212,255,0.5);"
            >
              {{ userInitial }}
            </div>
            <span v-if="userStore.user" class="text-sm text-[#e4e7ee] font-medium">
              {{ userStore.user.username }}
            </span>
            <a-button
              type="text"
              @click="userStore.logout"
              class="!text-[#535b6e] hover:!text-[#ff3d4f] !transition-colors"
            >
              <LogoutOutlined />
            </a-button>
          </div>
        </div>
      </a-layout-header>

      <!-- Content area -->
      <a-layout-content class="p-6 relative z-10">
        <router-view />
      </a-layout-content>
    </a-layout>

    <CommandPalette ref="cmdPalette" />
  </a-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { LogoutOutlined, SearchOutlined } from '@ant-design/icons-vue'
import AppSidebar from '@/components/AppSidebar.vue'
import ParticlesBackground from '@/components/ParticlesBackground.vue'
import CommandPalette from '@/components/CommandPalette.vue'

const route = useRoute()
const userStore = useUserStore()
const cmdPalette = ref<InstanceType<typeof CommandPalette>>()

const timeStr = ref('')
let timer: ReturnType<typeof setInterval>

const breadcrumbs = computed(() => {
  return route.matched.filter(r => r.meta?.title).map(r => r.meta.title as string)
})

const userInitial = computed(() => {
  return userStore.user?.username?.charAt(0).toUpperCase() || 'U'
})

function updateTime() {
  const now = new Date()
  timeStr.value = now.toLocaleTimeString('zh-CN', { hour12: false })
}

onMounted(async () => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  if (!userStore.user) {
    await userStore.fetchUser()
  }
})

onUnmounted(() => clearInterval(timer))
</script>
