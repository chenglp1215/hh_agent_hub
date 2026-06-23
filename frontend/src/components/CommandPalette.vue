<template>
  <Teleport to="body">
    <Transition name="palette">
      <div v-if="visible" class="palette-overlay" @click.self="close">
        <div class="palette-dialog glass-strong">
          <div class="palette-input-wrap">
            <SearchOutlined class="text-[#535b6e] text-lg" />
            <input
              ref="inputRef"
              v-model="query"
              class="palette-input"
              placeholder="搜索页面、Agent 或执行操作..."
              @keydown="onKeydown"
            />
            <kbd class="palette-kbd">ESC</kbd>
          </div>

          <div v-if="filteredItems.length > 0" class="palette-results">
            <div v-for="(group, gi) in groupedItems" :key="gi" class="palette-group">
              <div class="palette-group-label">{{ group.label }}</div>
              <div
                v-for="(item, ii) in group.items"
                :key="item.key"
                class="palette-item"
                :class="{ 'palette-item--active': activeIndex === getGlobalIndex(group, ii) }"
                @click="execute(item)"
                @mouseenter="activeIndex = getGlobalIndex(group, ii)"
              >
                <span class="palette-item-icon"><component :is="item.icon" /></span>
                <span class="palette-item-label">{{ item.label }}</span>
                <span class="palette-item-desc" v-if="item.desc">{{ item.desc }}</span>
                <kbd v-if="item.shortcut" class="palette-item-kbd">{{ item.shortcut }}</kbd>
              </div>
            </div>
          </div>

          <div v-else class="palette-empty">
            <span class="text-2xl mb-2">&#x1F50D;</span>
            <span class="text-sm">未找到匹配项</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  SearchOutlined, DashboardOutlined, RobotOutlined, ApartmentOutlined,
  AppstoreOutlined, DatabaseOutlined, LineChartOutlined, SettingOutlined,
  PlusOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()

interface PaletteItem {
  key: string
  label: string
  desc?: string
  icon: any
  shortcut?: string
  group: string
  action: () => void
}

const visible = ref(false)
const query = ref('')
const activeIndex = ref(0)
const inputRef = ref<HTMLInputElement>()

const allItems: PaletteItem[] = [
  { key: 'dashboard', label: '主控台', desc: 'Dashboard', icon: DashboardOutlined, group: '页面导航', shortcut: 'D', action: () => router.push('/dashboard') },
  { key: 'agents', label: 'Agent 列表', desc: '管理所有 Agent', icon: RobotOutlined, group: '页面导航', action: () => router.push('/agents') },
  { key: 'agents-create', label: '创建 Agent', desc: '新建 Agent', icon: PlusOutlined, group: '快速操作', action: () => router.push('/agents/create') },
  { key: 'workflows', label: '工作流列表', desc: '管理工作流', icon: ApartmentOutlined, group: '页面导航', action: () => router.push('/workflows') },
  { key: 'workflows-create', label: '创建工作流', desc: '创建工作流', icon: PlusOutlined, group: '快速操作', action: () => router.push('/workflows/create') },
  { key: 'apps', label: '应用管理', desc: '管理发布的应用', icon: AppstoreOutlined, group: '页面导航', action: () => router.push('/apps') },
  { key: 'mcp', label: 'MCP Server 管理', desc: '资源目录', icon: DatabaseOutlined, group: '页面导航', action: () => router.push('/resources/mcp-servers') },
  { key: 'kb', label: '知识库管理', desc: '资源目录', icon: DatabaseOutlined, group: '页面导航', action: () => router.push('/resources/knowledge-bases') },
  { key: 'skills', label: 'Skill 管理', desc: '资源目录', icon: DatabaseOutlined, group: '页面导航', action: () => router.push('/resources/skills') },
  { key: 'traces', label: '执行追踪', desc: '监控', icon: LineChartOutlined, group: '页面导航', action: () => router.push('/monitor/traces') },
  { key: 'chat-test', label: '对话测试', desc: '测试应用对话', icon: LineChartOutlined, group: '页面导航', action: () => router.push('/monitor/chat-test') },
  { key: 'chat-logs', label: '对话日志', desc: '监控', icon: LineChartOutlined, group: '页面导航', action: () => router.push('/monitor/chat-logs') },
  { key: 'settings', label: '系统设置', desc: '管理员配置', icon: SettingOutlined, group: '页面导航', action: () => router.push('/settings') },
]

const filteredItems = computed(() => {
  if (!query.value.trim()) return allItems
  const q = query.value.toLowerCase()
  return allItems.filter(item =>
    item.label.toLowerCase().includes(q) ||
    (item.desc && item.desc.toLowerCase().includes(q))
  )
})

const groupedItems = computed(() => {
  const groups: Record<string, PaletteItem[]> = {}
  for (const item of filteredItems.value) {
    if (!groups[item.group]) groups[item.group] = []
    groups[item.group].push(item)
  }
  return Object.entries(groups).map(([label, items]) => ({ label, items }))
})

function getGlobalIndex(group: { items: PaletteItem[] }, localIdx: number): number {
  let idx = 0
  for (const g of groupedItems.value) {
    for (let i = 0; i < g.items.length; i++) {
      if (g === group && i === localIdx) return idx
      idx++
    }
  }
  return idx
}

function getItemAt(idx: number): PaletteItem | null {
  let count = 0
  for (const g of groupedItems.value) {
    for (const item of g.items) {
      if (count === idx) return item
      count++
    }
  }
  return null
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    close()
    return
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    const total = filteredItems.value.length
    activeIndex.value = (activeIndex.value + 1) % total
    return
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    const total = filteredItems.value.length
    activeIndex.value = (activeIndex.value - 1 + total) % total
    return
  }
  if (e.key === 'Enter') {
    e.preventDefault()
    const item = getItemAt(activeIndex.value)
    if (item) execute(item)
    return
  }
}

function execute(item: PaletteItem) {
  close()
  item.action()
}

function open() {
  visible.value = true
  query.value = ''
  activeIndex.value = 0
  nextTick(() => inputRef.value?.focus())
}

function close() {
  visible.value = false
}

// Global keyboard shortcut
function onGlobalKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    open()
  }
}

watch(visible, (val) => {
  if (val) {
    document.addEventListener('keydown', onGlobalKeydown)
  } else {
    document.removeEventListener('keydown', onGlobalKeydown)
  }
})

// Listen globally for Ctrl+K
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault()
      open()
    }
  })
}

defineExpose({ open, close })
</script>

<style scoped>
.palette-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 15vh;
  background: rgba(3, 5, 10, 0.7);
  backdrop-filter: blur(4px);
}

.palette-dialog {
  width: 560px;
  max-width: 90vw;
  border-radius: 16px;
  border: 1px solid rgba(0, 212, 255, 0.15);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5), 0 0 60px rgba(0, 212, 255, 0.05);
  overflow: hidden;
}

.palette-input-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-subtle);
}

.palette-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #e4e7ee;
  font-size: 15px;
  font-family: inherit;
}
.palette-input::placeholder {
  color: #535b6e;
}

.palette-kbd {
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(0, 212, 255, 0.08);
  color: #535b6e;
  font-size: 11px;
  font-family: 'Cascadia Code', 'Consolas', monospace;
  border: 1px solid #1e2538;
}

.palette-results {
  max-height: 320px;
  overflow-y: auto;
}

.palette-group {
  padding: 4px 0;
}

.palette-group-label {
  padding: 8px 20px 4px;
  font-size: 10px;
  font-weight: 700;
  color: #535b6e;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.palette-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  border-left: 2px solid transparent;
}
.palette-item:hover,
.palette-item--active {
  background: rgba(0, 212, 255, 0.06);
  border-left-color: #00d4ff;
}

.palette-item-icon {
  width: 20px;
  font-size: 15px;
  color: #535b6e;
  display: flex;
  align-items: center;
  justify-content: center;
}
.palette-item:hover .palette-item-icon,
.palette-item--active .palette-item-icon {
  color: #00d4ff;
}

.palette-item-label {
  font-size: 13px;
  font-weight: 500;
  color: #e4e7ee;
}

.palette-item-desc {
  font-size: 11px;
  color: #535b6e;
  margin-left: auto;
}

.palette-item-kbd {
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(0, 212, 255, 0.06);
  color: #535b6e;
  font-size: 10px;
  font-family: 'Cascadia Code', 'Consolas', monospace;
  margin-left: auto;
}

.palette-empty {
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #535b6e;
}

/* Transitions */
.palette-enter-active {
  transition: all 200ms var(--ease-out);
}
.palette-leave-active {
  transition: all 150ms var(--ease-in-out);
}
.palette-enter-from,
.palette-leave-to {
  opacity: 0;
}
.palette-enter-from .palette-dialog,
.palette-leave-to .palette-dialog {
  transform: scale(0.96) translateY(-8px);
}
</style>
