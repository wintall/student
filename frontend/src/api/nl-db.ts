import request from '@/utils/request'

export function nlDbChat(message: string) {
  return request.post('/nl-db/chat', { message }, { timeout: 60000 })
}

export function nlDbHistory() {
  return request.get('/nl-db/history')
}

export function nlDbClear() {
  return request.post('/nl-db/clear')
}