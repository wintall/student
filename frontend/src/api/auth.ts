import request from '@/utils/request'

export function login(data: { account: string; password: string }) {
  return request.post('/auth/login', data)
}

export function logout() {
  return request.post('/auth/logout')
}

export function getMenus() {
  return request.get('/auth/menus')
}

export function changePassword(data: { old_password: string; new_password: string }) {
  return request.put('/auth/change-password', data)
}

export function refreshToken(refresh_token: string) {
  return request.post('/auth/refresh', { refresh_token })
}

// ============== 密码重置（邮箱验证码方式）===============

export function sendResetCode(email: string) {
  return request.post('/auth/password-reset/send-code', { email })
}

export function resetPassword(data: {
  email: string
  code: string
  new_password: string
  confirm_password: string
}) {
  return request.post('/auth/password-reset/confirm', data)
}
