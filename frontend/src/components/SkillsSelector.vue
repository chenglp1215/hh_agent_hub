<template>
  <div>
    <div class="flex items-center justify-between mb-2">
      <span class="text-sm text-gray-400">Skill 选择</span>
      <a-button size="small" @click="openModal">从目录选择</a-button>
    </div>
    <div v-if="modelValue.length === 0" class="text-xs text-gray-500">暂未选择 Skill</div>
    <a-tag v-for="id in modelValue" :key="id" closable :color="'#5e6ad2'" @close="remove(id)">
      {{ getSkillName(id) }}
    </a-tag>
    <a-modal v-model:open="showModal" title="选择 Skill" @ok="confirmSelection">
      <a-checkbox-group v-model:value="selectedIds">
        <div v-for="s in skills" :key="s.id" class="mb-2">
          <a-checkbox :value="s.id">
            {{ s.display_name || s.name }}
            <a-tag class="ml-2" :color="s.category === 'ops' ? 'orange' : 'blue'">{{ s.category }}</a-tag>
          </a-checkbox>
        </div>
      </a-checkbox-group>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { skillsApi } from '@/api/skills'

const props = defineProps<{ modelValue: number[] }>()
const emit = defineEmits(['update:modelValue'])

const showModal = ref(false)
const skills = ref<any[]>([])
const selectedIds = ref<number[]>([])

function openModal() {
  selectedIds.value = [...props.modelValue]
  showModal.value = true
}

function getSkillName(id: number) {
  return skills.value.find((s) => s.id === id)?.display_name || `Skill #${id}`
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
    const res = await skillsApi.list()
    skills.value = res.data.data || []
  } catch {
    // silently fail
  }
})
</script>
