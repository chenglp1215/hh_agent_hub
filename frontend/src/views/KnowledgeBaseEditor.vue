<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '创建' }} 知识库</h1>
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
          <a-select v-model:value="form.kb_type">
            <a-select-option value="file">文件目录</a-select-option>
            <a-select-option value="url">URL 抓取</a-select-option>
            <a-select-option value="rag">RAG 向量库</a-select-option>
          </a-select>
        </a-form-item>
        <template v-if="form.kb_type === 'file'">
          <a-form-item label="源路径">
            <a-input v-model:value="config.source_path" placeholder="/data/knowledge/api_docs/" />
          </a-form-item>
          <a-form-item label="文件匹配">
            <a-input v-model:value="filePatternsStr" placeholder="*.md, *.txt" />
          </a-form-item>
        </template>
        <template v-if="form.kb_type === 'url'">
          <a-form-item label="URL 列表 (每行一个)">
            <a-textarea v-model:value="urlsStr" :rows="4" />
          </a-form-item>
        </template>
        <template v-if="form.kb_type === 'rag'">
          <a-form-item label="嵌入模型">
            <a-input v-model:value="form.embedding_model" placeholder="text-embedding-3-small" />
          </a-form-item>
        </template>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { knowledgeBasesApi } from '@/api/knowledgeBases'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)
const filePatternsStr = ref('*.md, *.txt')
const urlsStr = ref('')

const form = ref<any>({ name: '', display_name: '', description: '', kb_type: 'file', embedding_model: '' })
const config = reactive<any>({ source_path: '', file_patterns: ['*.md', '*.txt'] })

onMounted(async () => {
  if (isEdit.value) {
    const res = await knowledgeBasesApi.get(Number(route.params.id))
    const d = res.data.data
    form.value = { name: d.name, display_name: d.display_name || '', description: d.description || '', kb_type: d.kb_type, embedding_model: d.embedding_model || '' }
    if (d.config) {
      Object.assign(config, d.config)
      if (d.config.file_patterns) filePatternsStr.value = d.config.file_patterns.join(', ')
      if (d.config.urls) urlsStr.value = d.config.urls.join('\n')
    }
  }
})

function buildConfig(): any {
  if (form.value.kb_type === 'file') {
    return { source_path: config.source_path, file_patterns: filePatternsStr.value.split(',').map(s => s.trim()).filter(Boolean) }
  }
  if (form.value.kb_type === 'url') {
    return { urls: urlsStr.value.split('\n').map(s => s.trim()).filter(Boolean) }
  }
  return {}
}

async function handleSubmit() {
  submitting.value = true
  try {
    const data = { ...form.value, config: buildConfig() }
    if (isEdit.value) {
      await knowledgeBasesApi.update(Number(route.params.id), data)
    } else {
      await knowledgeBasesApi.create(data)
    }
    message.success('保存成功')
    router.push('/resources/knowledge-bases')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally { submitting.value = false }
}
</script>
