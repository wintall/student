import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

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
        meta: { title: '用户管理', icon: 'User' },
      },
      {
        path: 'system/role',
        name: 'RoleManage',
        component: () => import('@/views/system/RoleManage.vue'),
        meta: { title: '角色管理', icon: 'UserFilled' },
      },
      {
        path: 'system/menu',
        name: 'MenuManage',
        component: () => import('@/views/system/MenuManage.vue'),
        meta: { title: '菜单管理', icon: 'Menu' },
      },
      // 组织架构
      {
        path: 'org/department',
        name: 'DepartmentManage',
        component: () => import('@/views/org/DepartmentManage.vue'),
        meta: { title: '院系管理', icon: 'School' },
      },
      {
        path: 'org/clazz',
        name: 'ClazzManage',
        component: () => import('@/views/org/ClazzManage.vue'),
        meta: { title: '班级管理', icon: 'Collection' },
      },
      // 人员管理
      {
        path: 'people/teacher',
        name: 'TeacherManage',
        component: () => import('@/views/people/TeacherManage.vue'),
        meta: { title: '教职工管理', icon: 'Avatar' },
      },
      {
        path: 'people/student',
        name: 'StudentManage',
        component: () => import('@/views/people/StudentManage.vue'),
        meta: { title: '学生管理', icon: 'Postcard' },
      },
      // 教学管理
      {
        path: 'teaching/course',
        name: 'CourseManage',
        component: () => import('@/views/teaching/CourseManage.vue'),
        meta: { title: '课程管理', icon: 'Notebook' },
      },
      {
        path: 'teaching/exam',
        name: 'ExamManage',
        component: () => import('@/views/teaching/ExamManage.vue'),
        meta: { title: '考试管理', icon: 'Tickets' },
      },
      {
        path: 'teaching/score',
        name: 'ScoreManage',
        component: () => import('@/views/teaching/ScoreManage.vue'),
        meta: { title: '成绩管理', icon: 'DataAnalysis' },
      },
      // 公告管理
      {
        path: 'announcement',
        name: 'AnnouncementManage',
        component: () => import('@/views/announcement/AnnouncementManage.vue'),
        meta: { title: '公告管理', icon: 'Bell' },
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
            meta: { title: '收件箱', icon: 'Inbox' },
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
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  NProgress.start()
  const token = localStorage.getItem('access_token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

router.afterEach(() => {
  NProgress.done()
})

export default router
