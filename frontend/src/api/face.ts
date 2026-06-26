import request from '@/utils/request'

export function faceLogin(data: {
  feature_vector: number[]
  device_info?: string
}) {
  return request.post('/face/login', data)
}

export function enrollFace(data: {
  feature_vector: number[]
  confidence: number
}) {
  return request.post('/face/enroll', data)
}

export function deleteFace() {
  return request.delete('/face/template')
}

export function getFaceTemplate() {
  return request.get('/face/template')
}

export function getFaceLoginLogs(params?: {
  user_id?: number
  page?: number
  page_size?: number
}) {
  return request.get('/face/logs', { params })
}