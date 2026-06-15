<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '新建' }}项目</h1>
    <a-card class="max-w-2xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <h3 class="text-lg font-semibold mb-4 text-[#5e6ad2]">基本信息</h3>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="名称" name="name" :rules="[{ required: true, message: '请输入名称' }]">
              <a-input v-model:value="form.name" :disabled="isEdit" placeholder="my_project" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="显示名称">
              <a-input v-model:value="form.display_name" placeholder="我的项目" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>

        <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">Git 配置</h3>
        <a-form-item label="仓库 URL" name="git_repo_url" :rules="[{ required: true, message: '请输入 Git 仓库 URL' }]">
          <a-input v-model:value="form.git_repo_url" placeholder="https://github.com/org/repo.git" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="分支">
              <a-input v-model:value="form.git_branch" placeholder="main" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="认证用户名">
              <a-input v-model:value="form.git_auth_username" placeholder="git 用户名" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="认证 Token">
              <a-input-password v-model:value="form.git_auth_token" placeholder="ghp_..." />
            </a-form-item>
          </a-col>
        </a-row>

        <h3 class="text-lg font-semibold mb-4 mt-4 text-[#5e6ad2]">高级设置</h3>
        <a-form-item label="自定义 Clone 目录">
          <a-input v-model:value="form.clone_path" placeholder="/data/workspaces/my_project" />
        </a-form-item>
        <a-form-item label="System Prompt">
          <a-textarea v-model:value="form.system_prompt" :rows="4" placeholder="项目特定的 Claude Code 系统提示..." />
        </a-form-item>
        <a-form-item label="执行超时(分钟)">
          <a-input-number v-model:value="form.fix_timeout_minutes" :min="1" :max="600" class="w-full" />
        </a-form-item>

        <a-divider />
        <a-form-item>
          <a-space>
            <a-button type="primary" html-type="submit" :loading="submitting">{{ isEdit ? '更新' : '创建' }}</a-button>
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
import { projectsApi } from '@/api/projects'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)
const form = ref<any>({
  name: '',
  display_name: '',
  description: '',
  git_repo_url: '',
  git_branch: 'main',
  git_auth_username: '',
  git_auth_token: '',
  clone_path: '',
  system_prompt: '',
  fix_timeout_minutes: 30,
})

onMounted(async () => {
  if (isEdit.value) {
    try {
      const res = await projectsApi.get(Number(route.params.id))
      const d = res.data.data
      form.value = {
        name: d.name,
        display_name: d.display_name || '',
        description: d.description || '',
        git_repo_url: d.git_repo_url,
        git_branch: d.git_branch || 'main',
        git_auth_username: d.git_auth_username || '',
        git_auth_token: d.git_auth_token || '',
        clone_path: d.clone_path || '',
        system_prompt: d.system_prompt || '',
        fix_timeout_minutes: d.fix_timeout_minutes ?? 30,
      }
    } catch {
      message.error('加载项目失败')
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    if (isEdit.value) {
      await projectsApi.update(Number(route.params.id), form.value)
    } else {
      await projectsApi.create(form.value)
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    router.push('/projects')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
