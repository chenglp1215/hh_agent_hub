import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import router from '@/router'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('access_token') || '')
  const user = ref<any>(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password })
    token.value = res.data.data.access_token
    user.value = res.data.data.user
    localStorage.setItem('access_token', token.value)
    router.push('/dashboard')
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    router.push('/login')
  }

  async function fetchUser() {
    try {
      const res = await authApi.me()
      user.value = res.data.data
    } catch {
      logout()
    }
  }

  return { token, user, isLoggedIn, isAdmin, login, logout, fetchUser }
})
