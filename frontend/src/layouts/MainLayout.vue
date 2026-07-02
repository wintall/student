<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar">
      <div class="sidebar-header" @click="isCollapse = !isCollapse">
        <el-icon :size="28" color="#409eff"><School /></el-icon>
        <span v-show="!isCollapse" class="sidebar-title">学生管理系统</span>
      </div>
      <el-scrollbar>
        <el-menu
          :default-active="activeMenu"
          :collapse="isCollapse"
          :unique-opened="true"
          router
          background-color="#1d1e2c"
          text-color="#a3a6b4"
          active-text-color="#409eff"
        >
          <!-- 首页（始终显示） -->
          <el-menu-item index="/dashboard">
            <el-icon><HomeFilled /></el-icon>
            <template #title>首页概览</template>
          </el-menu-item>

          <!-- 名著问答（始终显示，前端固定菜单项） -->
          <el-menu-item index="/rag/book-qa">
            <el-icon><Reading /></el-icon>
            <template #title>名著问答</template>
          </el-menu-item>
          <el-menu-item index="/rag/knowledge">
            <el-icon><Collection /></el-icon>
            <template #title>综合知识库</template>
          </el-menu-item>

          <!-- 从后端加载的菜单 -->
          <template v-for="item in menuItems" :key="item.path || item.id">
            <el-sub-menu
              v-if="item.children && item.children.length > 0"
              :index="'m_' + (item.path || item.id)"
            >
              <template #title>
                <el-icon>
                  <component :is="getIconComponent(item.icon)" />
                </el-icon>
                <span>{{ item.name }}</span>
              </template>
              <el-menu-item
                v-for="child in item.children"
                :key="child.path || child.id"
                :index="child.path"
              >
                <el-icon>
                  <component :is="getIconComponent(child.icon)" />
                </el-icon>
                <span>{{ child.name }}</span>
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else-if="item.path && item.path !== '/dashboard'" :index="item.path">
              <el-icon>
                <component :is="getIconComponent(item.icon)" />
              </el-icon>
              <template #title>{{ item.name }}</template>
            </el-menu-item>
          </template>
        </el-menu>
      </el-scrollbar>
    </el-aside>

    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click" @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" :icon="UserFilled" />
              <span class="user-name">{{ displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled style="color:#909399; font-size:12px">
                  角色：{{ roleNames }}
                </el-dropdown-item>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>

  <!-- AI 助手气泡 -->
  <FloatingWeather :offset-left="isCollapse ? 84 : 240" />
  <AIAssistant />

  <!-- 修改密码对话框 -->
  <el-dialog v-model="pwdVisible" title="修改密码" width="420px">
    <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="80px">
      <el-form-item label="旧密码" prop="old_password">
        <el-input v-model="pwdForm.old_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码" prop="new_password">
        <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="至少8位，需包含字母和数字" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="pwdVisible = false">取消</el-button>
      <el-button type="primary" @click="submitPassword">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, markRaw } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { changePassword } from '@/api/auth'
import AIAssistant from '@/components/AIAssistant.vue'
import FloatingWeather from '@/components/FloatingWeather.vue'
import { 
  UserFilled, HomeFilled, Folder, Document, 
  Lock, Reading, Collection, Camera,
  Menu, Search, Plus, Edit, Delete,
  PieChart, Calendar, Bell,
  Download, Upload,
  ArrowLeft, ArrowRight, ArrowUp, ArrowDown,
  Check, CircleCheck, CircleClose,
  InfoFilled,
  Message, Phone,
  MapLocation, Link,
  Monitor, Mouse,
  Printer, Cpu,
  Grid, List,
  VideoPlay, VideoPause,
  Picture, CameraFilled,
  User,
  Unlock, Key,
  Setting, Tools,
  Clock, Timer,
  Ticket,
  ShoppingCart,
  BellFilled,
  Help, HelpFilled,
  CirclePlus,
  School, OfficeBuilding, Avatar, Postcard, Notebook,
  Tickets, DataAnalysis, Promotion, EditPen,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const iconMap: Record<string, any> = {
  UserFilled, HomeFilled, Folder, Document,
  Lock, Reading, Collection, Camera,
  Menu, Search, Plus, Edit, Delete,
  PieChart, Calendar, Bell,
  Download, Upload,
  ArrowLeft, ArrowRight, ArrowUp, ArrowDown,
  Check, CircleCheck, CircleClose,
  InfoFilled,
  Message, Phone,
  MapLocation, Link,
  Monitor, Mouse,
  Printer, Cpu,
  Grid, List,
  VideoPlay, VideoPause,
  Picture, CameraFilled,
  User,
  Unlock, Key,
  Setting, Tools,
  Clock, Timer,
  Ticket,
  ShoppingCart,
  BellFilled,
  Help, HelpFilled,
  CirclePlus,
  School, OfficeBuilding, Avatar, Postcard, Notebook,
  Tickets, DataAnalysis, Promotion, EditPen,
}

const getIconComponent = (iconName: string | undefined) => {
  if (!iconName) return Document
  return iconMap[iconName] || Document
}

const isCollapse = ref(false)
const pwdVisible = ref(false)
const pwdFormRef = ref()

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => (route.meta?.title as string) || '')

const displayName = computed(() => {
  return userStore.userInfo?.real_name || userStore.userInfo?.username || '管理员'
})

const roleNames = computed(() => {
  const roles = userStore.userInfo?.roles || []
  if (!roles.length) return '未分配'
  return roles.map((r: any) => r.name).join('、')
})

// 菜单项：从 store 获取后端返回的菜单树
const menuItems = computed(() => {
  const normalize = (items: any[]): any[] => {
    return (items || [])
      .filter((item: any) => item.type !== 3 && item.path)
      .map((item: any) => ({
        ...item,
        children: normalize(item.children || []),
      }))
      .filter((item: any) => item.type === 2 || item.children.length > 0)
  }
  return normalize(userStore.menus || [])
})

const validateNewPwd = (_: any, value: string, cb: any) => {
  if (!value) {
    cb(new Error('请输入新密码'))
  } else if (value.length < 8) {
    cb(new Error('密码长度至少为8位'))
  } else if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
    cb(new Error('密码必须同时包含字母和数字'))
  } else {
    cb()
  }
}

const pwdForm = reactive({ old_password: '', new_password: '' })
const pwdRules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [{ validator: validateNewPwd, trigger: 'blur' }],
}

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning' })
      .then(() => {
        userStore.logout().then(() => router.push('/login'))
      })
      .catch(() => {})
  } else if (cmd === 'password') {
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdVisible.value = true
  }
}

async function submitPassword() {
  await pwdFormRef.value?.validate()
  try {
    await changePassword(pwdForm)
    ElMessage.success('密码修改成功，请重新登录')
    pwdVisible.value = false
    userStore.clearAuth()
    router.push('/login')
  } catch (e) {}
}

onMounted(async () => {
  // 页面加载时，如已登录但无菜单，则自动拉取
  if (userStore.token && (!userStore.menus || userStore.menus.length === 0)) {
    try {
      await userStore.fetchMenus()
    } catch (e) {}
  }
  if (userStore.token && !userStore.userInfo) {
    try {
      await userStore.fetchUserInfo()
    } catch (e) {}
  }
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.sidebar {
  background: #1d1e2c;
  transition: width 0.3s;
  overflow: hidden;
}

.sidebar-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.sidebar-title {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.el-menu {
  border-right: none;
}

.header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  padding: 0 20px;
  z-index: 10;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #606266;
}

.user-name {
  font-size: 14px;
}

.main-content {
  background: #f0f2f5;
  overflow-y: auto;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
