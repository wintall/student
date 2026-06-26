import request from '@/utils/request'

export interface LeaveQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: string
  applicant_type?: string
  leave_type?: string
}

export interface LeaveCreatePayload {
  applicant_type?: string
  leave_type: string
  start_time: string
  end_time: string
  reason: string
  destination?: string
  contact_phone?: string
  emergency_contact?: string
  attachment_url?: string
  remark?: string
}

export function createLeaveRequest(data: LeaveCreatePayload) {
  return request.post('/leave/requests', data)
}

export function getMyLeaveRequests(params?: LeaveQuery) {
  return request.get('/leave/requests/my', { params })
}

export function getReviewLeaveRequests(params?: LeaveQuery) {
  return request.get('/leave/requests/review', { params })
}

export function getLeaveRequest(id: number) {
  return request.get(`/leave/requests/${id}`)
}

export function cancelLeaveRequest(id: number) {
  return request.post(`/leave/requests/${id}/cancel`)
}

export function approveLeaveRequest(id: number, review_comment?: string) {
  return request.post(`/leave/requests/${id}/approve`, { review_comment })
}

export function rejectLeaveRequest(id: number, review_comment: string) {
  return request.post(`/leave/requests/${id}/reject`, { review_comment })
}
