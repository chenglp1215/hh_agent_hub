<template>
  <span>{{ displayValue }}</span>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

const props = withDefaults(defineProps<{
  target: number
  duration?: number
  delay?: number
}>(), {
  duration: 1200,
  delay: 0,
})

const displayValue = ref(0)

function animate() {
  const start = 0
  const end = props.target
  if (end === 0) {
    displayValue.value = 0
    return
  }

  const startTime = performance.now()

  function easeOutExpo(t: number): number {
    return t === 1 ? 1 : 1 - Math.pow(2, -10 * t)
  }

  function tick(now: number) {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / props.duration, 1)
    const eased = easeOutExpo(progress)
    displayValue.value = Math.round(start + (end - start) * eased)

    if (progress < 1) {
      requestAnimationFrame(tick)
    }
  }

  requestAnimationFrame(tick)
}

onMounted(() => {
  if (props.delay > 0) {
    setTimeout(animate, props.delay)
  } else {
    animate()
  }
})

watch(() => props.target, () => {
  if (props.delay > 0) {
    setTimeout(animate, props.delay)
  } else {
    animate()
  }
})
</script>
