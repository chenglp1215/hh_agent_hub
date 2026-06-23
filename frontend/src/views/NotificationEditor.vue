<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '创建' }} 通知渠道</h1>
    <a-card class="max-w-2xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <a-form-item label="渠道名称" name="name" :rules="[{ required: true, message: '请输入渠道名称' }]">
          <a-input v-model:value="form.name" placeholder="如：运维告警群" />
        </a-form-item>

        <a-form-item label="Webhook URL" name="webhook_url" :rules="[{ required: true, message: '请输入 Webhook URL' }]">
          <a-input v-model:value="form.webhook_url" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx" />
        </a-form-item>

        <a-form-item>
          <a-space>
            <a-button type="primary" html-type="submit" :loading="submitting">
              {{ isEdit ? '更新' : '创建' }}
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
import { notificationsApi } from '@/api/notifications'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)

const form = ref({
  name: '',
  channel_type: 'wecom_webhook',
  webhook_url: '',
})

onMounted(async () => {
  if (isEdit.value) {
    const res = await notificationsApi.get(Number(route.params.id))
    const d = res.data.data
    form.value = {
      name: d.name,
      channel_type: d.channel_type || 'wecom_webhook',
      webhook_url: d.webhook_url,
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    if (isEdit.value) {
      await notificationsApi.update(Number(route.params.id), form.value)
    } else {
      await notificationsApi.create(form.value)
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    router.push('/notifications')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
