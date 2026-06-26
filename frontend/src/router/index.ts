import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { useUserStore } from '@/stores/user'
import { hasPermission } from '@/utils/permission'

NProgress.configure({ showSpinner: false })

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '首页', icon: 'HomeFilled' },
      },
      // 系统管理
      {
        path: 'system/user',
        name: 'UserManage',
        component: () => import('@/views/system/UserManage.vue'),
        meta: { title: '用户管理', icon: 'User', permission: 'system:user:list' },
      },
      {
        path: 'system/role',
        name: 'RoleManage',
        component: () => import('@/views/system/RoleManage.vue'),
        meta: { title: '角色管理', icon: 'UserFilled', permission: 'system:role:list' },
      },
      {
        path: 'system/menu',
        name: 'MenuManage',
        component: () => import('@/views/system/MenuManage.vue'),
        meta: { title: '菜单管理', icon: 'Menu', permission: 'system:menu:list' },
      },
      {
        path: 'system/face',
        name: 'FaceManage',
        component: () => import('@/views/FaceManage.vue'),
        meta: { title: '人脸管理', icon: 'Camera' },
      },
      // 组织架构
      {
        path: 'org/department',
        name: 'DepartmentManage',
        component: () => import('@/views/org/DepartmentManage.vue'),
        meta: { title: '院系管理', icon: 'School', permission: 'org:department:list' },
      },
      {
        path: 'org/clazz',
        name: 'ClazzManage',
        component: () => import('@/views/org/ClazzManage.vue'),
        meta: { title: '班级管理', icon: 'Collection', permission: 'org:clazz:list' },
      },
      // 人员管理
      {
        path: 'people/teacher',
        name: 'TeacherManage',
        component: () => import('@/views/people/TeacherManage.vue'),
        meta: { title: '教职工管理', icon: 'Avatar', permission: 'people:teacher:list' },
      },
      {
        path: 'people/student',
        name: 'StudentManage',
        component: () => import('@/views/people/StudentManage.vue'),
        meta: { title: '学生管理', icon: 'Postcard', permission: 'people:student:list' },
      },
      // 教学管理
      {
        path: 'teaching/course',
        name: 'CourseManage',
        component: () => import('@/views/teaching/CourseManage.vue'),
        meta: { title: '课程管理', icon: 'Notebook', permission: 'teaching:course:list' },
      },
      {
        path: 'teaching/exam',
        name: 'ExamManage',
        component: () => import('@/views/teaching/ExamManage.vue'),
        meta: { title: '考试管理', icon: 'Tickets', permission: 'teaching:exam:list' },
      },
      {
        path: 'teaching/score',
        name: 'ScoreManage',
        component: () => import('@/views/teaching/ScoreManage.vue'),
        meta: { title: '成绩管理', icon: 'DataAnalysis', permission: 'teaching:score:list' },
      },
      // 公告管理
      {
        path: 'academic-calendar/term',
        name: 'TermManage',
        component: () => import('@/views/schedule/TermManage.vue'),
        meta: { title: '学期管理', icon: 'Calendar', permission: 'academic-calendar:term:list' },
      },
      {
        path: 'schedule/classroom',
        name: 'ClassroomManage',
        component: () => import('@/views/schedule/ClassroomManage.vue'),
        meta: { title: '教室管理', icon: 'OfficeBuilding', permission: 'schedule:classroom:list' },
      },
      {
        path: 'schedule/timetable',
        name: 'TimetableManage',
        component: () => import('@/views/schedule/TimetableManage.vue'),
        meta: { title: '课表管理', icon: 'Grid', permission: 'schedule:timetable:list' },
      },
      {
        path: 'schedule/my',
        name: 'MySchedule',
        component: () => import('@/views/schedule/MySchedule.vue'),
        meta: { title: '我的课表', icon: 'Notebook', permission: 'schedule:my:list' },
      },
      {
        path: 'operations/health',
        name: 'DataHealth',
        component: () => import('@/views/operations/DataHealth.vue'),
        meta: { title: '数据体检', icon: 'CircleCheck', permission: 'operations:health' },
      },
      {
        path: 'operations/export',
        name: 'DataExport',
        component: () => import('@/views/operations/DataExport.vue'),
        meta: { title: '数据导出', icon: 'Download', permission: 'operations:export' },
      },
      {
        path: 'notifications',
        name: 'NotificationCenter',
        component: () => import('@/views/notifications/NotificationCenter.vue'),
        meta: { title: '通知中心', icon: 'Bell' },
      },
      {
        path: 'announcement',
        name: 'AnnouncementManage',
        component: () => import('@/views/announcement/AnnouncementManage.vue'),
        meta: { title: '公告管理', icon: 'Bell' },
      },
      // 请假考勤
      {
        path: 'leave/my',
        name: 'MyLeave',
        component: () => import('@/views/leave/MyLeave.vue'),
        meta: { title: '我的请假', icon: 'Calendar', permission: 'leave:request:list' },
      },
      {
        path: 'leave/review',
        name: 'LeaveReview',
        component: () => import('@/views/leave/LeaveReview.vue'),
        meta: { title: '请假审批', icon: 'CircleCheck', permission: 'leave:review:list' },
      },
      {
        path: 'attendance/my',
        name: 'MyAttendance',
        component: () => import('@/views/leave/MyAttendance.vue'),
        meta: { title: '我的考勤', icon: 'Clock', permission: 'attendance:my:list' },
      },
      {
        path: 'attendance/student',
        name: 'StudentAttendance',
        component: () => import('@/views/leave/AttendanceManage.vue'),
        props: { personType: 'student' },
        meta: { title: '学生考勤', icon: 'Postcard', permission: 'attendance:student:list' },
      },
      {
        path: 'attendance/teacher',
        name: 'TeacherAttendance',
        component: () => import('@/views/leave/AttendanceManage.vue'),
        props: { personType: 'teacher' },
        meta: { title: '教职工考勤', icon: 'Avatar', permission: 'attendance:teacher:list' },
      },
      // 邮件系统
      {
        path: 'email',
        component: () => import('@/views/email/EmailLayout.vue'),
        redirect: '/email/inbox',
        children: [
          {
            path: 'inbox',
            name: 'EmailInbox',
            component: () => import('@/views/email/Inbox.vue'),
            meta: { title: '收件箱', icon: 'Message' },
          },
          {
            path: 'sent',
            name: 'EmailSent',
            component: () => import('@/views/email/Sent.vue'),
            meta: { title: '已发送', icon: 'Promotion' },
          },
          {
            path: 'compose',
            name: 'EmailCompose',
            component: () => import('@/views/email/Compose.vue'),
            meta: { title: '写邮件', icon: 'EditPen' },
          },
        ],
      },
      // 名著问答 (RAG)
      {
        path: 'rag/book-qa',
        name: 'RagBookQA',
        component: () => import('@/views/rag/BookQA.vue'),
        meta: { title: '名著问答', icon: 'Reading' },
      },
      {
        path: 'rag/qa-pair',
        name: 'RagQaPair',
        component: () => import('@/views/rag/QaPairManage.vue'),
        meta: { title: '问答对管理', icon: 'Collection' },
      },
      // 智能数据助手
      {
        path: 'nl-db',
        name: 'NlDbChat',
        component: () => import('@/views/NlDbChat.vue'),
        meta: { title: '智能数据助手', icon: 'Database' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach(async (to, _from, next) => {
  NProgress.start()
  const token = localStorage.getItem('access_token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    const requiredPermission = to.meta?.permission as string | undefined
    if (!requiredPermission) {
      next()
      return
    }
    const userStore = useUserStore()
    if (!userStore.userInfo?.permissions) {
      await userStore.fetchUserInfo()
    }
    if (hasPermission(requiredPermission)) {
      next()
    } else {
      next('/dashboard')
    }
  }
})

router.afterEach(() => {
  NProgress.done()
})

export default router
