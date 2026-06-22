import request from '@/utils/request'

// AI 聊天（使用更长的超时时间：60 秒，避免 LLM 响应慢时超时）
export function chatWithAi(message: string) {
  return request.post('/ai/chat', { message }, { timeout: 60000 })
}

// 清空对话上下文
export function clearAiContext() {
  return request.post('/ai/clear')
}
