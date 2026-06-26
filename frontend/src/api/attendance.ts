import request from '@/utils/request'

export interface AttendanceQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: string
  start_date?: string
  end_date?: string
  department_id?: number
  clazz_id?: number
  student_id?: number
  teacher_id?: number
}

export interface AttendancePayload {
  person_type: 'student' | 'teacher'
  user_id?: number
  student_id?: number
  teacher_id?: number
  attendance_date: string
  period_type: string
  course_schedule_id?: number
  checkin_time?: string
  checkout_time?: string
  status: string
  remark?: string
}

export interface AttendanceCandidateQuery {
  keyword?: string
  limit?: number
}

export function getMyAttendance(params?: AttendanceQuery) {
  return request.get('/attendance/my', { params })
}

export function getStudentAttendance(params?: AttendanceQuery) {
  return request.get('/attendance/students', { params })
}

export function getTeacherAttendance(params?: AttendanceQuery) {
  return request.get('/attendance/teachers', { params })
}

export function getStudentAttendanceCandidates(params?: AttendanceCandidateQuery) {
  return request.get('/attendance/candidates/students', { params })
}

export function getTeacherAttendanceCandidates(params?: AttendanceCandidateQuery) {
  return request.get('/attendance/candidates/teachers', { params })
}

export function createAttendance(data: AttendancePayload) {
  return request.post('/attendance', data)
}

export function updateAttendance(id: number, data: Partial<AttendancePayload>) {
  return request.put(`/attendance/${id}`, data)
}

export function deleteAttendance(id: number) {
  return request.delete(`/attendance/${id}`)
}
