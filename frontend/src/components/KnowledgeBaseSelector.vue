<template>
  <div>
    <div class="flex items-center justify-between mb-2">
      <span class="text-sm text-gray-400">知识库选择</span>
      <a-button size="small" @click="openModal">从目录选择</a-button>
    </div>
    <div v-if="modelValue.length === 0" class="text-xs text-gray-500">暂未选择知识库</div>
    <a-tag v-for="id in modelValue" :key="id" closable :color="'#5e6ad2'" @close="remove(id)">
      {{ getKbName(id) }}
    </a-tag>
    <a-modal v-model:open="showModal" title="选择知识库" @ok="confirmSelection">
      <a-checkbox-group v-model:value="selectedIds">
        <div v-for="k in kbs" :key="k.id" class="mb-2">
          <a-checkbox :value="k.id">
            {{ k.display_name || k.name }}
            <span class="text-gray-400 text-xs ml-2">{{ k.document_count }} 文档</span>
          </a-checkbox>
        </div>
      </a-checkbox-group>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { knowledgeBasesApi } from '@/api/knowledgeBases'

const props = defineProps<{ modelValue: number[] }>()
const emit = defineEmits(['update:modelValue'])

const showModal = ref(false)
const kbs = ref<any[]>([])
const selectedIds = ref<number[]>([])

function openModal() {
  selectedIds.value = [...props.modelValue]
  showModal.value = true
}

function getKbName(id: number) {
  return kbs.value.find((k) => k.id === id)?.display_name || `KB #${id}`
}

function remove(id: number) {
  emit(
    'update:modelValue',
    props.modelValue.filter((i) => i !== id),
  )
}

function confirmSelection() {
  emit('update:modelValue', [...selectedIds.value])
  showModal.value = false
}

onMounted(async () => {
  try {
    const res = await knowledgeBasesApi.list()
    kbs.value = res.data.data || []
  } catch {
    // silently fail
  }
})
</script>
