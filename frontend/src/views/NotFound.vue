<template>
  <div class="flex items-center justify-center min-h-screen">
    <a-result status="404" title="404" sub-title="页面不存在">
      <template #extra>
        <a-button type="primary" @click="$router.push('/dashboard')">返回主控台</a-button>
      </template>
    </a-result>
  </div>
</template>
