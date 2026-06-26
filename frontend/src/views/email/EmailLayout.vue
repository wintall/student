<template>
  <div class="email-container">
    <div class="email-sidebar">
      <div class="sidebar-header">
        <span style="font-size: 18px; font-weight: 700;">内部邮件</span>
      </div>
      <div class="sidebar-menu">
        <el-menu
          :default-active="activeMenu"
          router
          background-color="transparent"
          text-color="#606266"
          active-text-color="#409eff"
        >
          <el-menu-item index="/email/inbox">
            <el-icon><Message /></el-icon>
            <span>收件箱</span>
            <el-badge v-if="unreadCount > 0" :value="unreadCount" class="ml-auto" style="margin-left: auto;" />
          </el-menu-item>
          <el-menu-item index="/email/sent">
            <el-icon><Promotion /></el-icon>
            <span>已发送</span>
          </el-menu-item>
          <el-menu-item index="/email/compose">
            <el-icon><EditPen /></el-icon>
            <span>写信</span>
          </el-menu-item>
        </el-menu>
      </div>
    </div>

    <div class="email-content">
      <router-view />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { getUnreadCount } from '@/api/email'

const route = useRoute()
const activeMenu = ref('/email/inbox')
const unreadCount = ref(0)

let timer: number | null = null

async function loadUnread() {
  try {
    const res = await getUnreadCount()
    // 兼容两种字段名（后端可能返回 unread 或 unread_count）
    unreadCount.value = Number(res.data?.unread_count ?? res.data?.unread ?? 0) || 0
  } catch (e) {
    unreadCount.value = 0
  }
}

onMounted(() => {
  activeMenu.value = route.path
  loadUnread()
  timer = window.setInterval(loadUnread, 60000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.email-container {
  display: flex;
  height: calc(100vh - 100px);
  background: #f5f7fa;
}

.email-sidebar {
  width: 220px;
  background: #fff;
  border-right: 1px solid #ebeef5;
  padding: 20px 0;
}

.sidebar-header {
  padding: 0 24px 20px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 12px;
}

.sidebar-menu :deep(.el-menu-item) {
  height: 44px;
  display: flex;
  align-items: center;
  margin: 2px 12px;
  border-radius: 8px;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.12), rgba(118, 75, 162, 0.12));
  color: #409eff;
}

.email-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}
</style>
