<template>
  <canvas ref="canvasRef" class="particles-canvas" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const canvasRef = ref<HTMLCanvasElement>()
let animId = 0
let mouseX = -1000
let mouseY = -1000

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  r: number
  alpha: number
}

onMounted(() => {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  let w = 0
  let h = 0
  const particles: Particle[] = []
  const count = 80

  function resize() {
    w = canvas!.width = window.innerWidth
    h = canvas!.height = window.innerHeight
  }
  resize()
  window.addEventListener('resize', resize)

  for (let i = 0; i < count; i++) {
    particles.push({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      r: Math.random() * 1.8 + 0.5,
      alpha: Math.random() * 0.5 + 0.2,
    })
  }

  function onMouseMove(e: MouseEvent) {
    mouseX = e.clientX
    mouseY = e.clientY
  }
  window.addEventListener('mousemove', onMouseMove)

  const maxDist = 140

  function draw() {
    ctx!.clearRect(0, 0, w, h)

    for (let i = 0; i < particles.length; i++) {
      const p = particles[i]
      p.x += p.vx
      p.y += p.vy

      if (p.x < 0) p.x = w
      if (p.x > w) p.x = 0
      if (p.y < 0) p.y = h
      if (p.y > h) p.y = 0

      // Draw particle
      ctx!.beginPath()
      ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx!.fillStyle = `rgba(0, 212, 255, ${p.alpha})`
      ctx!.fill()

      // Mouse repulsion glow
      const dxm = mouseX - p.x
      const dym = mouseY - p.y
      const distM = Math.sqrt(dxm * dxm + dym * dym)
      if (distM < 200) {
        ctx!.beginPath()
        ctx!.arc(p.x, p.y, p.r + 2, 0, Math.PI * 2)
        ctx!.fillStyle = `rgba(0, 212, 255, ${0.6 * (1 - distM / 200)})`
        ctx!.fill()
      }

      // Draw connections to nearby particles
      for (let j = i + 1; j < particles.length; j++) {
        const q = particles[j]
        const dx = p.x - q.x
        const dy = p.y - q.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < maxDist) {
          const opacity = (1 - dist / maxDist) * 0.12
          ctx!.beginPath()
          ctx!.moveTo(p.x, p.y)
          ctx!.lineTo(q.x, q.y)
          ctx!.strokeStyle = `rgba(0, 212, 255, ${opacity})`
          ctx!.lineWidth = 0.5
          ctx!.stroke()
        }
      }
    }

    animId = requestAnimationFrame(draw)
  }

  draw()
})

onUnmounted(() => {
  cancelAnimationFrame(animId)
})
</script>

<style scoped>
.particles-canvas {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}
</style>
