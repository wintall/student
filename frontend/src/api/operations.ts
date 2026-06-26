import request from '@/utils/request'

export function getDashboardSummary() {
  return request.get('/operations/dashboard')
}

export function getDataHealth() {
  return request.get('/operations/data-health')
}

export function getExportUrl(type: string, params?: Record<string, any>) {
  const search = new URLSearchParams()
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.append(key, String(value))
  })
  const query = search.toString()
  return `/api/v1/operations/exports/${type}${query ? `?${query}` : ''}`
}

export function listNotifications(params?: any) {
  return request.get('/notifications', { params })
}

export function getNotificationUnreadCount() {
  return request.get('/notifications/unread-count')
}

export function markNotificationRead(id: number) {
  return request.post(`/notifications/${id}/read`)
}

export function markAllNotificationsRead() {
  return request.post('/notifications/read-all')
}
