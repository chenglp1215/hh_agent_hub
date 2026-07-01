<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '创建' }} 应用</h1>
    <a-card class="max-w-xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <a-form-item label="应用名称" name="name" :rules="[{ required: true }]">
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-form-item label="关联工作流" name="workflow_id" :rules="[{ required: true }]">
          <a-select
            v-model:value="form.workflow_id"
            show-search
            option-filter-prop="label"
            placeholder="选择已发布的工作流"
          >
            <a-select-option
              v-for="w in publishedWorkflows"
              :key="w.id"
              :value="w.id"
              :label="w.name"
            >
              {{ w.name }} <span class="text-gray-400 text-xs ml-2">{{ w.flow_type }}</span>
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="限流(次/分钟)">
          <a-input-number v-model:value="form.rate_limit" :min="1" :max="1000" class="w-full" />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" html-type="submit" :loading="submitting">保存</a-button>
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
import { appsApi } from '@/api/apps'
import { workflowsApi } from '@/api/workflows'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)
const publishedWorkflows = ref<any[]>([])

const form = ref({
  name: '',
  description: '',
  workflow_id: undefined as number | undefined,
  rate_limit: 60,
})

onMounted(async () => {
  const res = await workflowsApi.list({ status: 'published' })
  publishedWorkflows.value = res.data.data || []

  if (isEdit.value) {
    const res = await appsApi.get(Number(route.params.id))
    const d = res.data.data
    form.value = {
      name: d.name,
      description: d.description || '',
      workflow_id: d.workflow_id,
      rate_limit: d.rate_limit,
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    if (isEdit.value) {
      await appsApi.update(Number(route.params.id), form.value)
    } else {
      await appsApi.create(form.value)
    }
    message.success('保存成功')
    router.push('/apps')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
