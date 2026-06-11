<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">Skill 资源目录</h1>
      <a-button type="primary" @click="$router.push('/resources/skills/create')">
        <PlusOutlined /> 创建 Skill
      </a-button>
    </div>

    <div class="mb-4 flex gap-4 flex-wrap">
      <a-input-search v-model:value="search" placeholder="搜索..." class="max-w-xs" />
      <a-select v-model:value="category" class="w-32" placeholder="分类">
        <a-select-option value="">全部分类</a-select-option>
        <a-select-option value="ops">运维</a-select-option>
        <a-select-option value="development">开发</a-select-option>
        <a-select-option value="testing">测试</a-select-option>
        <a-select-option value="deployment">部署</a-select-option>
      </a-select>
    </div>

    <a-spin :spinning="loading">
      <a-table :dataSource="filteredSkills" :columns="columns" rowKey="id" :pagination="{ pageSize: 10 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'tags'">
            <a-tag v-for="tag in (record.tags || [])" :key="tag" color="#5e6ad2">{{ tag }}</a-tag>
          </template>
          <template v-if="column.key === 'actions'">
            <a-button size="small" @click="$router.push(`/resources/skills/${record.id}/edit`)">编辑</a-button>
            <a-popconfirm title="确定删除？" @confirm="handleDelete(record.id)">
              <a-button size="small" danger class="ml-2">删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { skillsApi } from '@/api/skills'

const skills = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const category = ref('')

const columns = [
  { title: '名称', dataIndex: 'display_name', key: 'name' },
  { title: '标识', dataIndex: 'name', key: 'key' },
  { title: '分类', dataIndex: 'category', key: 'category' },
  { title: '类型', dataIndex: 'skill_type', key: 'type' },
  { title: '标签', key: 'tags' },
  { title: '版本', dataIndex: 'version', key: 'version' },
  { title: '操作', key: 'actions', width: 160 },
]

const filteredSkills = computed(() => {
  let list = skills.value
  if (category.value) list = list.filter(s => s.category === category.value)
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(s => (s.name + s.display_name + s.description).toLowerCase().includes(q))
  }
  return list
})

async function fetchList() {
  loading.value = true
  try {
    const res = await skillsApi.list(category.value ? { category: category.value } : undefined)
    skills.value = res.data.data || []
  } finally {
    loading.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await skillsApi.delete(id)
    message.success('已删除')
    fetchList()
  } catch {
    message.error('删除失败')
  }
}

onMounted(fetchList)
</script>
