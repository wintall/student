import request from '@/utils/request'

export interface CampusAgentChatPayload {
  message: string
  mode?: string
  session_id?: string
}

// 兼容旧智能助手接口
export function chatWithAi(message: string) {
  return request.post('/ai/chat', { message }, { timeout: 60000 })
}

// 二阶段校园助手统一聊天接口
export function chatWithCampusAgent(data: CampusAgentChatPayload) {
  return request.post('/campus-agent/chat', data, { timeout: 60000 })
}

export function getCampusAgentModes() {
  return request.get('/campus-agent/modes')
}

export function clearCampusAgentContext(sessionId?: string) {
  return request.post('/campus-agent/clear', { session_id: sessionId })
}

export function clearAiContext() {
  return request.post('/ai/clear')
}
