<template>
  <div class="terminal-node" :class="[`terminal-node--${data.type}`]">
    <Handle v-if="data.type === 'start'" type="source" :position="Position.Bottom" class="terminal-handle" />
    <Handle v-if="data.type === 'end'" type="target" :position="Position.Top" class="terminal-handle" />
    <span class="terminal-node__label">{{ data.label }}</span>
  </div>
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'

defineProps<{ data: { type: string; label: string } }>()
</script>

<style scoped>
.terminal-node {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid;
  backdrop-filter: blur(12px);
}
.terminal-node--start {
  background: rgba(0, 230, 118, 0.08);
  border-color: rgba(0, 230, 118, 0.4);
  box-shadow: 0 0 20px rgba(0, 230, 118, 0.1);
}
.terminal-node--end {
  background: rgba(255, 61, 79, 0.08);
  border-color: rgba(255, 61, 79, 0.4);
  box-shadow: 0 0 20px rgba(255, 61, 79, 0.1);
}
.terminal-node__label {
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #e4e7ee;
}
.terminal-handle {
  width: 10px !important;
  height: 10px !important;
  background: #1e2538 !important;
  border: 2px solid #00d4ff !important;
}
.terminal-handle:hover {
  background: #00d4ff !important;
  box-shadow: 0 0 8px #00d4ff88;
}
</style>
