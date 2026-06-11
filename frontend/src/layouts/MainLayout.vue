<template>
  <a-layout class="min-h-screen">
    <AppSidebar />
    <a-layout>
      <a-layout-header class="!bg-[#0a0a0b] flex items-center justify-between px-6 border-b border-[#1e1e20]">
        <a-breadcrumb>
          <a-breadcrumb-item v-for="(item, i) in breadcrumbs" :key="i">
            {{ item }}
          </a-breadcrumb-item>
        </a-breadcrumb>
        <a-space>
          <a-tag v-if="userStore.user" color="#5e6ad2">{{ userStore.user.username }}</a-tag>
          <a-button type="text" @click="userStore.logout">
            <LogoutOutlined />
          </a-button>
        </a-space>
      </a-layout-header>
      <a-layout-content class="p-6 bg-[#0a0a0b]">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { LogoutOutlined } from '@ant-design/icons-vue'
import AppSidebar from '@/components/AppSidebar.vue'

const route = useRoute()
const userStore = useUserStore()

const breadcrumbs = computed(() => {
  return route.matched.filter(r => r.meta?.title).map(r => r.meta.title as string)
})

onMounted(async () => {
  if (!userStore.user) {
    await userStore.fetchUser()
  }
})
</script>
