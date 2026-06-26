<template>
  <div class="page-container">
    <!-- 欢迎卡片 -->
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card class="welcome-card" shadow="hover">
          <div class="welcome-content">
            <div>
              <h2>欢迎回来 👋</h2>
              <p class="welcome-desc">学生信息管理系统 — 高效管理，智慧校园</p>
            </div>
            <div class="welcome-date">{{ currentDate }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6" v-for="item in stats" :key="item.label">
        <el-card shadow="hover" class="stat-card" :style="{ borderTop: `3px solid ${item.color}` }">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-value">{{ item.value }}</div>
              <div class="stat-label">{{ item.label }}</div>
            </div>
            <el-icon :size="48" :color="item.color" :style="{ opacity: 0.2 }">
              <component :is="item.icon" />
            </el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷操作 + 公告 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span style="font-weight: 600;">快捷操作</span>
          </template>
          <div class="quick-actions">
            <el-button type="primary" @click="$router.push('/email/inbox')">
              <el-icon><Message /></el-icon> 收件箱
            </el-button>
            <el-button type="success" @click="$router.push('/email/compose')">
              <el-icon><Edit /></el-icon> 写邮件
            </el-button>
            <el-button v-if="hasPermission('people:student:list')" type="warning" @click="$router.push('/people/student')">
              <el-icon><Postcard /></el-icon> 学生管理
            </el-button>
            <el-button v-if="hasPermission('people:teacher:list')" type="info" @click="$router.push('/people/teacher')">
              <el-icon><Avatar /></el-icon> 教职工
            </el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span style="font-weight: 600;">待办事项</span>
          </template>
          <el-empty v-if="!workbench.todos.length" description="暂无待办" :image-size="80" />
          <div v-else class="todo-list">
            <div v-for="todo in workbench.todos" :key="todo.type" class="todo-item" @click="$router.push(todo.path)">
              <span>{{ todo.title }}</span>
              <el-tag type="warning">{{ todo.count }}</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span style="font-weight: 600;">数据健康</span>
          </template>
          <div class="health-summary">
            <div>
              <div class="health-value">{{ workbench.health.total_issue_count }}</div>
              <div class="health-label">异常总数</div>
            </div>
            <el-button type="primary" plain @click="$router.push('/operations/health')">查看体检</el-button>
          </div>
          <div class="health-issues">
            <el-tag v-for="item in workbench.health.top_issues" :key="item.code" type="warning">
              {{ item.title }} {{ item.count }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span style="font-weight: 600;">最近通知</span>
          </template>
          <el-empty v-if="!workbench.notifications.length" description="暂无通知" :image-size="80" />
          <div v-else class="notice-list">
            <div v-for="item in workbench.notifications" :key="item.id" class="notice-item">
              <span>{{ item.title }}</span>
              <small>{{ item.created_at }}</small>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { getDashboardSummary } from '@/api/operations'
import { hasPermission } from '@/utils/permission'

const stats = reactive([
  { label: '学生数', key: 'students', value: 0, icon: 'Postcard', color: '#409eff' },
  { label: '教职工数', key: 'teachers', value: 0, icon: 'Avatar', color: '#67c23a' },
  { label: '课程数', key: 'courses', value: 0, icon: 'School', color: '#e6a23c' },
  { label: '课表数', key: 'schedules', value: 0, icon: 'Collection', color: '#f56c6c' },
])

const currentDate = ref(new Date().toLocaleDateString('zh-CN', {
  year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
}))

const workbench = reactive({
  todos: [] as any[],
  notifications: [] as any[],
  health: { total_issue_count: 0, issue_type_count: 0, top_issues: [] as any[] },
})

onMounted(async () => {
  try {
    const workbenchRes = await getDashboardSummary()
    const data = workbenchRes.data || {}
    const summaryStats = data.stats || {}
    stats.forEach((item) => {
      item.value = summaryStats[item.key] ?? 0
    })
    workbench.todos = data.todos || []
    workbench.notifications = data.notifications || []
    workbench.health = data.health || workbench.health
  } catch (e) {}
})
</script>

<style scoped>
.page-container {
  padding: 20px;
}

.welcome-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 12px;
  margin-bottom: 20px;
  color: #fff;
}
.welcome-card :deep(.el-card__body) { color: #fff; }
.welcome-content { display: flex; justify-content: space-between; align-items: center; }
.welcome-content h2 { margin: 0 0 8px; font-size: 22px; }
.welcome-desc { opacity: 0.85; margin: 0; }
.welcome-date { font-size: 14px; opacity: 0.8; }

.stat-row { margin-top: 0; }
.stat-card { border-radius: 12px; }
.stat-content { display: flex; justify-content: space-between; align-items: center; }
.stat-value { font-size: 32px; font-weight: 700; color: #1a1a2e; }
.stat-label { font-size: 14px; color: #909399; margin-top: 4px; }

.quick-actions { display: flex; flex-wrap: wrap; gap: 12px; }
.todo-list, .notice-list { display: flex; flex-direction: column; gap: 10px; }
.todo-item, .notice-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; border: 1px solid #ebeef5; border-radius: 8px;
  background: #fff; cursor: pointer;
}
.notice-item { cursor: default; }
.notice-item small { color: #909399; }
.health-summary { display: flex; align-items: center; justify-content: space-between; }
.health-value { font-size: 32px; font-weight: 700; color: #e6a23c; }
.health-label { color: #909399; margin-top: 4px; }
.health-issues { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
</style>
