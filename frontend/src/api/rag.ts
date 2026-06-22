import request from '@/utils/request'

// ====== 四大名著 RAG 问答 ======

export interface RagBook {
  id: number
  code: string
  name: string
  author: string
  dynasty: string
  summary: string
  total_chapters: number
  total_sections: number
}

export interface RagSource {
  id: number
  book_code: string
  book_name: string
  chapter_no: number
  chapter_title: string
  section_no: number
  text: string
  keywords: string
  score: number
}

export interface RagAskResponse {
  question: string
  sources: RagSource[]
  answer: string
}

// 提问（调用 RAG 检索 + LLM 生成）
export function askRag(question: string, bookCodes: string[] | null = null, topK: number | null = null) {
  return request.post<RagAskResponse>('/rag/ask', {
    question,
    book_codes: bookCodes,
    top_k: topK,
  }, { timeout: 90000 })
}

// 仅检索（不生成答案）
export function searchRag(question: string, bookCodes: string[] | null = null, topK: number | null = null) {
  return request.post<RagSource[]>('/rag/search', {
    question,
    book_codes: bookCodes,
    top_k: topK,
  }, { timeout: 60000 })
}

// 书籍列表
export function listRagBooks() {
  return request.get<RagBook[]>('/rag/books')
}

// 健康检查
export function ragHealth() {
  return request.get('/rag/health')
}
