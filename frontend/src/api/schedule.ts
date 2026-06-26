import request from '@/utils/request'
import { createCrudApi } from '@/api/common'

export const termApi = createCrudApi('terms')
export const classroomApi = createCrudApi('classrooms')
export const courseScheduleApi = {
  ...createCrudApi('course-schedules'),
  my: (params?: any) => request.get('/course-schedules/my', { params }),
}
