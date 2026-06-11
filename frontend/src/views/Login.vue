<template>
  <div class="min-h-screen flex items-center justify-center bg-[#010102]">
    <a-card title="多Agent协同平台" class="w-96">
      <a-form :model="form" @finish="handleLogin">
        <a-form-item name="username" :rules="[{ required: true, message: '请输入用户名' }]">
          <a-input v-model:value="form.username" placeholder="用户名" size="large" />
        </a-form-item>
        <a-form-item name="password" :rules="[{ required: true, message: '请输入密码' }]">
          <a-input-password v-model:value="form.password" placeholder="密码" size="large" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" block size="large" :loading="loading">登录</a-button>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { message } from 'ant-design-vue'

const userStore = useUserStore()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function handleLogin() {
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    message.success('登录成功')
  } catch (e: any) {
    message.error(e.response?.data?.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>
