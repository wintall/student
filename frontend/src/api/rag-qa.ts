import request from '@/utils/request'

// ====== RAG 问答对管理 ======

export interface QaPair {
  id: number
  category: string
  question: string
  question_variants: string
  answer: string
  keywords: string
  source: string
  hit_count: number
  status: number
  created_at: string
  updated_at: string
}

export interface QaPairMatch {
  id: number
  question: string
  answer: string
  source: string
  score: number
  category: string
}

// 创建问答对
export function createQaPair(data: {
  category?: string
  question: string
  question_variants?: string
  answer: string
  keywords?: string
  source?: string
}) {
  return request.post<QaPair>('/rag/qa-pairs', data)
}

// 更新问答对
export function updateQaPair(id: number, data: Partial<QaPair>) {
  return request.put<QaPair>(`/rag/qa-pairs/${id}`, data)
}

// 删除问答对
export function deleteQaPair(id: number) {
  return request.delete(`/rag/qa-pairs/${id}`)
}

// 获取单个问答对
export function getQaPair(id: number) {
  return request.get<QaPair>(`/rag/qa-pairs/${id}`)
}

// 列表查询（分页）
export function listQaPairs(params: {
  page?: number
  page_size?: number
  keyword?: string
  category?: string
  status?: number
}) {
  return request.get<{
    items: QaPair[]
    total: number
    page: number
    page_size: number
  }>('/rag/qa-pairs', { params })
}

// 测试匹配接口
export function matchQaPairs(question: string, category?: string, topN: number = 3) {
  return request.post<{ question: string; matches: QaPairMatch[] }>('/rag/qa-pairs/match', {
    question,
    category,
    top_n: topN,
  })
}
