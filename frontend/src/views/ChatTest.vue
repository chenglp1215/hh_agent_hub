<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">对话测试</h1>
    <div class="flex gap-4 mb-4">
      <a-select v-model:value="selectedAppId" class="w-64" placeholder="选择应用">
        <a-select-option v-for="app in apps" :key="app.id" :value="app.id">
          {{ app.name }} ({{ app.workflow_name }})
        </a-select-option>
      </a-select>
      <a-button @click="$router.push('/apps')">管理应用</a-button>
    </div>
    <div
      v-if="selectedAppId"
      class="h-[500px] bg-[#010102] border border-[#1e1e20] rounded-lg overflow-hidden"
    >
      <ChatWindow :appId="selectedAppId" :apiKey="''" />
    </div>
    <a-empty v-else description="请先选择一个应用开始测试" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { appsApi } from '@/api/apps'
import ChatWindow from '@/components/ChatWindow.vue'

const apps = ref<any[]>([])
const selectedAppId = ref<number | null>(null)

onMounted(async () => {
  try {
    const res = await appsApi.list()
    apps.value = res.data.data || []
  } catch {
    // ignore
  }
})
</script>
