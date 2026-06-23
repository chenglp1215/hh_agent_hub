<template>
  <div class="login-page">
    <!-- Particle background -->
    <canvas ref="bgCanvas" class="login-canvas" />

    <!-- Animated gradient orbs -->
    <div class="orb orb-1" />
    <div class="orb orb-2" />
    <div class="orb orb-3" />

    <!-- Login card -->
    <div class="login-card glass">
      <div class="login-header">
        <div class="login-logo">
          <span class="login-logo-text">AH</span>
        </div>
        <h1 class="login-title">Agent Hub</h1>
        <p class="login-desc">多智能体协同平台</p>
      </div>

      <div class="login-divider">
        <span class="login-divider-line" />
        <span class="login-divider-dot" />
        <span class="login-divider-line" />
      </div>

      <a-form :model="form" @finish="handleLogin" class="login-form">
        <a-form-item name="username" :rules="[{ required: true, message: '请输入用户名' }]">
          <a-input
            v-model:value="form.username"
            placeholder="用户名"
            size="large"
            class="login-input"
          >
            <template #prefix>
              <UserOutlined class="!text-[#535b6e]" />
            </template>
          </a-input>
        </a-form-item>

        <a-form-item name="password" :rules="[{ required: true, message: '请输入密码' }]">
          <a-input-password
            v-model:value="form.password"
            placeholder="密码"
            size="large"
            class="login-input"
          >
            <template #prefix>
              <LockOutlined class="!text-[#535b6e]" />
            </template>
          </a-input-password>
        </a-form-item>

        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            block
            size="large"
            :loading="loading"
            class="login-btn"
          >
            <span v-if="!loading">登 录</span>
          </a-button>
        </a-form-item>
      </a-form>
    </div>

    <p class="login-footer">Agent Hub v1.0 · Powered by LangGraph + Claude</p>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, onUnmounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { message } from 'ant-design-vue'
import { UserOutlined, LockOutlined } from '@ant-design/icons-vue'

const userStore = useUserStore()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const bgCanvas = ref<HTMLCanvasElement>()

let animId = 0

onMounted(() => {
  const canvas = bgCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  let w = 0, h = 0
  const dots: { x: number; y: number; r: number; vx: number; vy: number; a: number }[] = []

  function resize() {
    w = canvas!.width = window.innerWidth
    h = canvas!.height = window.innerHeight
  }
  resize()
  window.addEventListener('resize', resize)

  for (let i = 0; i < 50; i++) {
    dots.push({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.2 + 0.3,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      a: Math.random() * 0.4 + 0.1,
    })
  }

  function draw() {
    ctx!.clearRect(0, 0, w, h)
    for (const d of dots) {
      d.x += d.vx
      d.y += d.vy
      if (d.x < 0) d.x = w
      if (d.x > w) d.x = 0
      if (d.y < 0) d.y = h
      if (d.y > h) d.y = 0

      ctx!.beginPath()
      ctx!.arc(d.x, d.y, d.r, 0, Math.PI * 2)
      ctx!.fillStyle = `rgba(0, 212, 255, ${d.a})`
      ctx!.fill()
    }

    for (let i = 0; i < dots.length; i++) {
      for (let j = i + 1; j < dots.length; j++) {
        const dx = dots[i].x - dots[j].x
        const dy = dots[i].y - dots[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < 150) {
          ctx!.beginPath()
          ctx!.moveTo(dots[i].x, dots[i].y)
          ctx!.lineTo(dots[j].x, dots[j].y)
          ctx!.strokeStyle = `rgba(0, 212, 255, ${0.06 * (1 - dist / 150)})`
          ctx!.lineWidth = 0.5
          ctx!.stroke()
        }
      }
    }

    animId = requestAnimationFrame(draw)
  }
  draw()
})

onUnmounted(() => cancelAnimationFrame(animId))

async function handleLogin() {
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    message.success('欢迎回来')
  } catch (e: any) {
    message.error(e.response?.data?.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--bg-deep);
  position: relative;
  overflow: hidden;
}

.login-canvas {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

/* Animated gradient orbs */
.orb {
  position: fixed;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.15;
  pointer-events: none;
  z-index: 0;
}
.orb-1 {
  width: 500px;
  height: 500px;
  background: #00d4ff;
  top: -150px;
  right: -100px;
  animation: orb-float-1 8s ease-in-out infinite;
}
.orb-2 {
  width: 400px;
  height: 400px;
  background: #007acc;
  bottom: -120px;
  left: -80px;
  animation: orb-float-2 10s ease-in-out infinite;
}
.orb-3 {
  width: 300px;
  height: 300px;
  background: #f0a500;
  top: 40%;
  left: 50%;
  animation: orb-float-3 12s ease-in-out infinite;
}

@keyframes orb-float-1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(40px, -30px) scale(1.08); }
  66% { transform: translate(-20px, 20px) scale(0.95); }
}
@keyframes orb-float-2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(-30px, -20px) scale(1.05); }
  66% { transform: translate(50px, 30px) scale(0.92); }
}
@keyframes orb-float-3 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-40px, -40px) scale(1.1); }
}

/* Login card */
.login-card {
  position: relative;
  z-index: 10;
  width: 420px;
  max-width: 90vw;
  padding: 40px 36px;
  border-radius: var(--radius-xl);
  border: 1px solid rgba(0, 212, 255, 0.12);
  box-shadow: 0 8px 48px rgba(0, 0, 0, 0.4), 0 0 80px rgba(0, 212, 255, 0.05);
  animation: fade-in-up 0.8s var(--ease-out);
}

.login-header {
  text-align: center;
  margin-bottom: 28px;
}

.login-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #00d4ff, #007acc);
  box-shadow: 0 0 32px rgba(0, 212, 255, 0.3), 0 0 64px rgba(0, 212, 255, 0.1);
  animation: glow-pulse 3s ease-in-out infinite;
}

.login-logo-text {
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 24px;
  font-weight: 800;
  color: #fff;
  text-shadow: 0 0 12px rgba(255, 255, 255, 0.6);
}

.login-title {
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.08em;
  margin: 0 0 6px;
}

.login-desc {
  font-size: 13px;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  margin: 0;
}

.login-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}

.login-divider-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.2), transparent);
}

.login-divider-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #00d4ff;
  box-shadow: 0 0 8px #00d4ff88;
}

.login-form {
  animation: fade-in-up 0.6s 0.2s var(--ease-out) both;
}

.login-input :deep(.ant-input-affix-wrapper) {
  border-radius: var(--radius-md) !important;
  height: 44px !important;
}
.login-input :deep(.ant-input) {
  font-size: 14px !important;
}

.login-btn {
  height: 44px !important;
  font-size: 15px !important;
  letter-spacing: 0.15em !important;
  border-radius: var(--radius-md) !important;
  margin-top: 4px;
}

.login-footer {
  position: fixed;
  bottom: 24px;
  z-index: 10;
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  animation: fade-in 1s 0.5s var(--ease-out) both;
}
</style>
