import request from '@/utils/request'

export interface KnowledgeBase {
  id: number
  name: string
  description?: string
  owner_id: number
  scope_type: 'personal' | 'public' | 'class' | 'course'
  scope_id?: number
  status: number
  document_count: number
  chunk_count: number
  chunk_strategy: 'paragraph' | 'fixed'
  chunk_size: number
  chunk_overlap: number
  embedding_model: string
  vector_store: string
  similarity_metric: 'COSINE' | 'IP' | 'L2'
  retrieval_mode: 'vector' | 'keyword' | 'hybrid'
  default_top_k: number
  default_min_score: number
  vector_weight: number
  bm25_weight: number
  title_weight: number
  core_weight: number
  eval_score?: number
  eval_recall?: number
  eval_precision?: number
  eval_f1?: number
  eval_hit?: number
  eval_mrr?: number
  eval_sample_count?: number
  evaluated_at?: string
  config?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface KnowledgeDocument {
  id: number
  kb_id: number
  title: string
  source_type: 'text' | 'upload' | 'path'
  file_name?: string
  file_ext?: string
  status: string
  error_message?: string
  chunk_count: number
  char_count: number
  created_at: string
  updated_at: string
}

export interface KnowledgeSource {
  chunk_id: number
  document_id: number
  kb_id: number
  title: string
  chunk_no: number
  score: number
  vector_score?: number
  bm25_score?: number
  title_score?: number
  core_score?: number
  content: string
}

export interface KnowledgeAskResponse {
  question: string
  answer: string
  sources: KnowledgeSource[]
  retrieval?: Record<string, any>
}

export interface KnowledgeBasePayload {
  name: string
  description?: string
  scope_type?: string
  scope_id?: number
  chunk_strategy?: 'paragraph' | 'fixed'
  chunk_size?: number
  chunk_overlap?: number
  embedding_model?: string
  vector_store?: string
  similarity_metric?: 'COSINE' | 'IP' | 'L2'
  retrieval_mode?: 'vector' | 'keyword' | 'hybrid'
  default_top_k?: number
  default_min_score?: number
  vector_weight?: number
  bm25_weight?: number
  title_weight?: number
  core_weight?: number
}

export function listKnowledgeBases(params?: { keyword?: string; include_public?: boolean }) {
  return request.get<KnowledgeBase[]>('/rag/knowledge/bases', { params })
}

export function createKnowledgeBase(data: KnowledgeBasePayload) {
  return request.post<KnowledgeBase>('/rag/knowledge/bases', data)
}

export function updateKnowledgeBase(id: number, data: Partial<KnowledgeBasePayload & { status: number }>) {
  return request.put<KnowledgeBase>(`/rag/knowledge/bases/${id}`, data)
}

export function deleteKnowledgeBase(id: number) {
  return request.delete(`/rag/knowledge/bases/${id}`)
}

export function listKnowledgeDocuments(kbId: number) {
  return request.get<KnowledgeDocument[]>(`/rag/knowledge/bases/${kbId}/documents`)
}

export function getKnowledgeBaseDetail(kbId: number) {
  return request.get<Record<string, any>>(`/rag/knowledge/bases/${kbId}/detail`)
}

export function evaluateKnowledgeBase(kbId: number) {
  return request.post<Record<string, any>>(`/rag/knowledge/bases/${kbId}/evaluate`, {}, { timeout: 120000 })
}

export function importKnowledgeText(data: { kb_id: number; title: string; text: string }) {
  return request.post<KnowledgeDocument>('/rag/knowledge/documents/text', data, { timeout: 0 })
}

export function importKnowledgePath(data: { kb_id: number; title?: string; path: string }) {
  return request.post<KnowledgeDocument>('/rag/knowledge/documents/path', data, { timeout: 0 })
}

export function uploadKnowledgeDocument(kbId: number, file: File, title?: string) {
  const form = new FormData()
  form.append('kb_id', String(kbId))
  if (title) form.append('title', title)
  form.append('file', file)
  return request.post<KnowledgeDocument>('/rag/knowledge/documents/upload', form, {
    timeout: 0,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteKnowledgeDocument(id: number) {
  return request.delete(`/rag/knowledge/documents/${id}`)
}

export function askKnowledge(data: { question: string; kb_ids?: number[]; top_k?: number; min_score?: number }) {
  return request.post<KnowledgeAskResponse>('/rag/knowledge/ask', data, { timeout: 120000 })
}

export function knowledgeHealth() {
  return request.get('/rag/knowledge/health')
}
