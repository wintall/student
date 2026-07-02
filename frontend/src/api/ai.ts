import request from '@/utils/request'

export interface CampusAgentChatPayload {
  message: string
  mode?: string
  session_id?: string
  file_ids?: string[]
  llm_provider?: string
  llm_model?: string
}

// 兼容旧智能助手接口
export function chatWithAi(message: string) {
  return request.post('/ai/chat', { message }, { timeout: 60000 })
}

// 二阶段校园助手统一聊天接口
export function chatWithCampusAgent(data: CampusAgentChatPayload) {
  return request.post('/campus-agent/chat', data, { timeout: 120000 })
}

export function uploadCampusAgentFile(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request.post('/campus-agent/files', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

export function getCampusAgentModes() {
  return request.get('/campus-agent/modes')
}

export function getCampusAgentSessions(limit = 20) {
  return request.get('/campus-agent/sessions', { params: { limit } })
}

export function getCampusAgentSession(sessionId: string) {
  return request.get(`/campus-agent/sessions/${sessionId}`)
}

export function deleteCampusAgentSession(sessionId: string) {
  return request.delete(`/campus-agent/sessions/${sessionId}`)
}

export function clearCampusAgentContext(sessionId?: string) {
  return request.post('/campus-agent/clear', { session_id: sessionId })
}

export function clearAiContext() {
  return request.post('/ai/clear')
}
