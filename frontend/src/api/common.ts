import request from '@/utils/request'

// 通用 CRUD API 工厂
export function createCrudApi(prefix: string) {
  return {
    list: (params?: any) => request.get(`/${prefix}`, { params }),
    get: (id: number) => request.get(`/${prefix}/${id}`),
    create: (data: any) => request.post(`/${prefix}`, data),
    update: (id: number, data: any) => request.put(`/${prefix}/${id}`, data),
    delete: (id: number) => request.delete(`/${prefix}/${id}`),
  }
}

export const userApi = createCrudApi('users')
export const roleApi = createCrudApi('roles')
export const departmentApi = createCrudApi('departments')
export const clazzApi = createCrudApi('clazzes')
export const teacherApi = createCrudApi('teachers')
export const studentApi = createCrudApi('students')
export const courseApi = createCrudApi('courses')
export const examApi = createCrudApi('exams')
export const scoreApi = createCrudApi('scores')
export const announcementApi = {
  ...createCrudApi('announcements'),
  markRead: (id: number) => request.post(`/announcements/${id}/read`),
}

export function getEnums() {
  return request.get('/enums')
}

export function getRoleMenus() {
  return request.get('/roles/menus/all')
}

export function createMenu(data: any) {
  return request.post('/roles/menus', data)
}

export function updateMenu(id: number, data: any) {
  return request.put(`/roles/menus/${id}`, data)
}

export function deleteMenu(id: number) {
  return request.delete(`/roles/menus/${id}`)
}
