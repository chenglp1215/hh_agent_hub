<template>
  <div class="agent-node" :class="[`agent-node--${data.role}`, { 'agent-node--selected': selected }]">
    <Handle type="target" :position="Position.Top" class="agent-handle" />
    <div class="agent-node__icon">
      <RobotOutlined v-if="data.role !== 'supervisor'" />
      <StarOutlined v-else />
    </div>
    <div class="agent-node__info">
      <div class="agent-node__name">{{ data.label }}</div>
      <div class="agent-node__type">
        <a-tag :color="typeColor(data.agentType)" size="small">{{ data.agentType }}</a-tag>
      </div>
    </div>
    <Handle type="source" :position="Position.Bottom" class="agent-handle" />
  </div>
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { RobotOutlined, StarOutlined } from '@ant-design/icons-vue'

defineProps<{
  data: { label: string; role: string; agentType: string; agentId: number }
  selected: boolean
}>()

function typeColor(t: string) {
  return { local: 'blue', http: 'orange', a2a: 'cyan', claudecode: 'purple' }[t] || 'default'
}
</script>

<style scoped>
.agent-node {
  background: linear-gradient(135deg, rgba(12, 16, 27, 0.92), rgba(17, 22, 36, 0.9));
  border: 1px solid #1e2538;
  border-radius: 12px;
  padding: 10px 14px;
  min-width: 180px;
  backdrop-filter: blur(12px);
  transition: all var(--duration-fast) var(--ease-out);
  cursor: pointer;
}
.agent-node:hover {
  border-color: rgba(0, 212, 255, 0.3);
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.1);
}
.agent-node--selected {
  border-color: #00d4ff !important;
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.2), 0 0 40px rgba(0, 212, 255, 0.08) !important;
}
.agent-node--supervisor {
  border-color: rgba(240, 165, 0, 0.3);
  background: linear-gradient(135deg, rgba(20, 16, 10, 0.92), rgba(24, 18, 12, 0.9));
}
.agent-node--supervisor:hover,
.agent-node--supervisor.agent-node--selected {
  border-color: #f0a500 !important;
  box-shadow: 0 0 20px rgba(240, 165, 0, 0.2), 0 0 40px rgba(240, 165, 0, 0.08) !important;
}
.agent-node__icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 212, 255, 0.12);
  color: #00d4ff;
  font-size: 14px;
  margin-bottom: 6px;
}
.agent-node--supervisor .agent-node__icon {
  background: rgba(240, 165, 0, 0.12);
  color: #f0a500;
}
.agent-node__name {
  font-size: 13px;
  font-weight: 600;
  color: #e4e7ee;
  margin-bottom: 4px;
}
.agent-node__type {
  font-size: 11px;
}
.agent-handle {
  width: 10px !important;
  height: 10px !important;
  background: #1e2538 !important;
  border: 2px solid #00d4ff !important;
  transition: all var(--duration-fast) var(--ease-out);
}
.agent-handle:hover {
  background: #00d4ff !important;
  box-shadow: 0 0 8px #00d4ff88;
}
</style>
