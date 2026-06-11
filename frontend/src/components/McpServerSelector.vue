<template>
  <div>
    <div class="flex items-center justify-between mb-2">
      <span class="text-sm text-gray-400">MCP Server 选择</span>
      <a-button size="small" @click="openModal">从目录选择</a-button>
    </div>
    <div v-if="modelValue.length === 0" class="text-xs text-gray-500">暂未选择 MCP Server</div>
    <a-tag
      v-for="item in modelValue"
      :key="item.mcp_server_id"
      closable
      :color="'#5e6ad2'"
      @close="remove(item.mcp_server_id)"
    >
      {{ item.server?.name || item.mcp_server_id }}
      <span class="text-xs ml-1">({{ (item.enabled_tools || []).length || '全部' }} tools)</span>
    </a-tag>
    <a-modal v-model:open="showModal" title="选择 MCP Server" @ok="confirmSelection">
      <a-checkbox-group v-model:value="selectedIds">
        <div v-for="s in servers" :key="s.id" class="mb-2">
          <a-checkbox :value="s.id">
            {{ s.display_name || s.name }}
            <span class="text-gray-400 text-xs ml-2">{{ s.discovered_tools?.length || 0 }} tools</span>
          </a-checkbox>
        </div>
      </a-checkbox-group>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { mcpServersApi } from '@/api/mcpServers'

const props = defineProps<{ modelValue: any[] }>()
const emit = defineEmits(['update:modelValue'])

const showModal = ref(false)
const servers = ref<any[]>([])
const selectedIds = ref<number[]>([])

function openModal() {
  selectedIds.value = props.modelValue.map((i: any) => i.mcp_server_id)
  showModal.value = true
}

function remove(id: number) {
  emit('update:modelValue', props.modelValue.filter((i: any) => i.mcp_server_id !== id))
}

function confirmSelection() {
  emit(
    'update:modelValue',
    selectedIds.value.map((id) => {
      const server = servers.value.find((s) => s.id === id)
      return {
        mcp_server_id: id,
        enabled_tools: [],
        server: server ? { id: server.id, name: server.name } : undefined,
      }
    }),
  )
  showModal.value = false
}

onMounted(async () => {
  try {
    const res = await mcpServersApi.list()
    servers.value = res.data.data || []
  } catch {
    // silently fail
  }
})
</script>
