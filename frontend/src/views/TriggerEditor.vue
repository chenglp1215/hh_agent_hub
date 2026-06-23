<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">{{ isEdit ? '编辑' : '创建' }} 触发器</h1>
    <a-card class="max-w-2xl">
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <a-form-item label="触发器名称" name="name" :rules="[{ required: true, message: '请输入触发器名称' }]">
          <a-input v-model:value="form.name" placeholder="如：每日巡检" />
        </a-form-item>

        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="可选描述" />
        </a-form-item>

        <a-form-item label="触发类型" name="trigger_type" :rules="[{ required: true, message: '请选择触发类型' }]">
          <a-radio-group v-model:value="form.trigger_type">
            <a-radio value="interval">间隔触发</a-radio>
            <a-radio value="cron">Cron 表达式</a-radio>
          </a-radio-group>
        </a-form-item>

        <!-- Interval 配置 -->
        <template v-if="form.trigger_type === 'interval'">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="间隔数值" name="interval_value"
                :rules="[{ required: form.trigger_type === 'interval', message: '请输入间隔数值' }]">
                <a-input-number v-model:value="form.interval_value" :min="1" :max="99999" class="w-full" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="间隔单位" name="interval_unit"
                :rules="[{ required: form.trigger_type === 'interval', message: '请选择间隔单位' }]">
                <a-select v-model:value="form.interval_unit">
                  <a-select-option value="minutes">分钟</a-select-option>
                  <a-select-option value="hours">小时</a-select-option>
                  <a-select-option value="days">天</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
        </template>

        <!-- Cron 配置 -->
        <template v-if="form.trigger_type === 'cron'">
          <a-form-item label="Cron 表达式" name="cron_expression"
            :rules="[{ required: form.trigger_type === 'cron', message: '请输入 cron 表达式' }]">
            <a-input v-model:value="form.cron_expression" placeholder="如：0 9 * * 1-5" />
          </a-form-item>
          <div class="mb-4">
            <span class="text-sm text-gray-400 mr-2">预设：</span>
            <a-button size="small" class="mr-1" @click="setCronPreset('0 * * * *')">每小时</a-button>
            <a-button size="small" class="mr-1" @click="setCronPreset('0 9 * * *')">每天 9:00</a-button>
            <a-button size="small" class="mr-1" @click="setCronPreset('0 9 * * 1-5')">工作日 9:00</a-button>
            <a-button size="small" @click="setCronPreset('0 0 1 * *')">每月1日</a-button>
          </div>
        </template>

        <a-form-item label="关联应用" name="app_id"
          :rules="[{ required: true, message: '请选择关联应用' }]">
          <a-select
            v-model:value="form.app_id"
            show-search
            option-filter-prop="label"
            placeholder="选择已启用的应用"
          >
            <a-select-option
              v-for="app in enabledApps"
              :key="app.id"
              :value="app.id"
              :label="app.name"
            >
              {{ app.name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="触发消息内容" name="message"
          :rules="[{ required: true, message: '请输入触发消息内容' }]">
          <a-textarea v-model:value="form.message" :rows="3" placeholder="输入触发时发送的 Chat 消息内容" />
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
import { triggersApi } from '@/api/triggers'
import { appsApi } from '@/api/apps'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)
const enabledApps = ref<any[]>([])

const form = ref({
  name: '',
  description: '',
  trigger_type: 'interval' as 'interval' | 'cron',
  interval_value: undefined as number | undefined,
  interval_unit: undefined as string | undefined,
  cron_expression: '',
  app_id: undefined as number | undefined,
  message: '',
})

function setCronPreset(expr: string) {
  form.value.cron_expression = expr
}

onMounted(async () => {
  // 加载已启用的应用列表
  const res = await appsApi.list()
  enabledApps.value = (res.data.data || []).filter((a: any) => a.enabled)

  if (isEdit.value) {
    const res = await triggersApi.get(Number(route.params.id))
    const d = res.data.data
    form.value = {
      name: d.name,
      description: d.description || '',
      trigger_type: d.trigger_type,
      interval_value: d.interval_value,
      interval_unit: d.interval_unit,
      cron_expression: d.cron_expression || '',
      app_id: d.app_id,
      message: d.message,
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    const payload: Record<string, any> = { ...form.value }
    // 清理 interval/cron 互斥字段
    if (payload.trigger_type === 'interval') {
      payload.cron_expression = null
    } else {
      payload.interval_value = null
      payload.interval_unit = null
    }

    if (isEdit.value) {
      await triggersApi.update(Number(route.params.id), payload)
    } else {
      await triggersApi.create(payload)
    }
    message.success('保存成功')
    router.push('/triggers')
  } catch (e: any) {
    message.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
