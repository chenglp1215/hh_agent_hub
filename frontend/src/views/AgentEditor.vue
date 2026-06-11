<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">{{ id ? '编辑 Agent' : '创建 Agent' }}</h1>
    </div>
    <p class="text-gray-400">Agent 编辑器页面 — 即将实现</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{ id?: string }>()
</script>
