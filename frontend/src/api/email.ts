import request from '@/utils/request'

// ============== 邮件系统 API ==============

// 收件箱
export function getInbox(params?: { page?: number; page_size?: number; keyword?: string }) {
  return request.get('/emails/inbox', { params })
}

// 已发送
export function getSentEmails(params?: { page?: number; page_size?: number; keyword?: string }) {
  return request.get('/emails/sent', { params })
}

// 未读数量
export function getUnreadCount() {
  return request.get('/emails/unread-count')
}

// 邮件详情
export function getEmailDetail(id: number) {
  return request.get(`/emails/${id}`)
}

// 发送邮件（带附件）
export function sendEmail(data: {
  recipient_email: string
  subject: string
  body: string
  files?: File[]
}) {
  const formData = new FormData()
  formData.append('recipient_email', data.recipient_email)
  formData.append('subject', data.subject)
  formData.append('body', data.body)
  if (data.files) {
    data.files.forEach((f) => {
      formData.append('files', f)
    })
  }
  return request.post('/emails/send', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 删除邮件
export function deleteEmail(id: number, as_recipient: boolean = true) {
  return request.delete(`/emails/${id}`, { params: { as_recipient } })
}

// 搜索用户建议（写信时搜索收件人）
export function suggestUsers(keyword: string) {
  return request.get('/emails/users/suggest', { params: { keyword } })
}

// 下载附件（备选方案，实际由后端静态文件或 download 端点处理）
export function getAttachmentDownloadUrl(id: number) {
  const token = localStorage.getItem('access_token') || ''
  return `/api/v1/emails/attachments/${id}/download`
}
