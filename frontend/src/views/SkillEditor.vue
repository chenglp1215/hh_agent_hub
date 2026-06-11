<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '创建' }} Skill</h1>
    <a-card class="max-w-2xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <a-form-item label="名称" name="name" :rules="[{ required: true }]">
          <a-input v-model:value="form.name" :disabled="isEdit" />
        </a-form-item>
        <a-form-item label="显示名称">
          <a-input v-model:value="form.display_name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-form-item label="类型">
          <a-select v-model:value="form.skill_type">
            <a-select-option value="prompt">Prompt 模板</a-select-option>
            <a-select-option value="file">文件引用</a-select-option>
            <a-select-option value="url">URL 引用</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="分类">
          <a-select v-model:value="form.category">
            <a-select-option value="ops">运维</a-select-option>
            <a-select-option value="development">开发</a-select-option>
            <a-select-option value="testing">测试</a-select-option>
            <a-select-option value="deployment">部署</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="标签">
          <a-select v-model:value="form.tags" mode="tags" placeholder="输入标签后回车" />
        </a-form-item>
        <a-form-item v-if="form.skill_type === 'prompt'" label="Prompt 模板">
          <a-textarea v-model:value="promptTemplate" :rows="8" placeholder="## 慢查询分析流程&#10;1. 检查慢查询日志..." />
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
import { skillsApi } from '@/api/skills'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)
const promptTemplate = ref('')
const form = ref<any>({ name: '', display_name: '', description: '', skill_type: 'prompt', category: 'ops', tags: [] })

onMounted(async () => {
  if (isEdit.value) {
    const res = await skillsApi.get(Number(route.params.id))
    const d = res.data.data
    form.value = { name: d.name, display_name: d.display_name || '', description: d.description || '', skill_type: d.skill_type, category: d.category || 'ops', tags: d.tags || [] }
    if (d.content?.prompt_template) promptTemplate.value = d.content.prompt_template
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    const data = { ...form.value }
    if (form.value.skill_type === 'prompt') {
      data.content = { prompt_template: promptTemplate.value }
    }
    if (isEdit.value) {
      await skillsApi.update(Number(route.params.id), data)
    } else {
      await skillsApi.create(data)
    }
    message.success('保存成功')
    router.push('/resources/skills')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
