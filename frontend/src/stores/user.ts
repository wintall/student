import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const userInfo = ref<any>(null)
  const menus = ref<any[]>([])

  function setToken(access: string, refresh: string) {
    token.value = access
    refreshToken.value = refresh
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
  }

  function setUserInfo(info: any) {
    userInfo.value = info
    if (info) {
      localStorage.setItem('user_info', JSON.stringify(info))
    } else {
      localStorage.removeItem('user_info')
    }
  }

  // 从本地缓存恢复
  try {
    const cached = localStorage.getItem('user_info')
    if (cached) userInfo.value = JSON.parse(cached)
  } catch (e) {}

  function clearAuth() {
    token.value = ''
    refreshToken.value = ''
    userInfo.value = null
    menus.value = []
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_info')
  }

  async function fetchMenus() {
    const res = await request.get('/auth/menus')
    menus.value = res.data
  }

  async function fetchUserInfo() {
    try {
      const res = await request.get('/auth/me')
      userInfo.value = res.data
      localStorage.setItem('user_info', JSON.stringify(res.data))
      return res.data
    } catch (e) {
      return null
    }
  }

  async function logout() {
    try {
      await request.post('/auth/logout')
    } catch (e) {}
    clearAuth()
  }

  return {
    token, refreshToken, userInfo, menus,
    setToken, setUserInfo, clearAuth,
    fetchMenus, fetchUserInfo, logout,
  }
})
