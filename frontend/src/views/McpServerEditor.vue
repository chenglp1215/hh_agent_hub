<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '注册' }} MCP Server</h1>
    <a-card class="max-w-2xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <a-form-item label="名称" name="name" :rules="[{ required: true }]">
          <a-input v-model:value="form.name" placeholder="如 mysql-prod" :disabled="isEdit" />
        </a-form-item>
        <a-form-item label="显示名称">
          <a-input v-model:value="form.display_name" placeholder="如 生产环境 MySQL" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-form-item label="Base URL" name="base_url" :rules="[{ required: true }]">
          <a-input v-model:value="form.base_url" placeholder="http://mysql-mcp.internal:3000" />
        </a-form-item>
        <a-form-item label="超时(秒)">
          <a-input-number v-model:value="form.timeout" :min="5" :max="300" class="w-full" />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" html-type="submit" :loading="submitting">
              {{ isEdit ? '更新' : '注册' }}
            </a-button>
            <a-button @click="$router.back()">取消</a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { mcpServersApi } from '@/api/mcpServers'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)
const form = ref({ name: '', display_name: '', description: '', base_url: '', timeout: 30 })

onMounted(async () => {
  if (isEdit.value) {
    const res = await mcpServersApi.get(Number(route.params.id))
    const d = res.data.data
    form.value = { name: d.name, display_name: d.display_name || '', description: d.description || '', base_url: d.base_url, timeout: d.timeout }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    if (isEdit.value) {
      await mcpServersApi.update(Number(route.params.id), form.value)
    } else {
      await mcpServersApi.create(form.value)
    }
    message.success(isEdit.value ? '更新成功' : '注册成功')
    router.push('/resources/mcp-servers')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
