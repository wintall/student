<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <template #header>
        <span>数据导出</span>
      </template>

      <el-row :gutter="16">
        <el-col v-for="item in visibleExports" :key="item.type" :xs="24" :sm="12" :md="8">
          <div class="export-item">
            <div>
              <div class="export-title">{{ item.title }}</div>
              <div class="export-desc">{{ item.desc }}</div>
            </div>
            <el-button type="primary" @click="download(item.type)">
              <el-icon><Download /></el-icon>
              导出
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getExportUrl } from '@/api/operations'
import { hasPermission } from '@/utils/permission'

const exports = [
  { type: 'students', permission: 'operations:export:students', title: '学生列表', desc: '导出当前权限范围内学生基础信息' },
  { type: 'teachers', permission: 'operations:export:teachers', title: '教师列表', desc: '导出教师基础信息' },
  { type: 'courses', permission: 'operations:export:courses', title: '课程列表', desc: '导出课程和任课教师信息' },
  { type: 'schedules', permission: 'operations:export:schedules', title: '课表', desc: '导出课程、班级、教师、教室和时间' },
  { type: 'scores', permission: 'operations:export:scores', title: '成绩列表', desc: '导出当前权限范围内成绩' },
  { type: 'transcript', permission: 'operations:export:transcript', title: '成绩单', desc: '学生导出本人，管理员可按接口参数扩展' },
]

const visibleExports = computed(() => exports.filter((item) => hasPermission(item.permission)))

function download(type: string) {
  const token = localStorage.getItem('access_token') || ''
  const url = getExportUrl(type)
  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then(async (response) => {
      if (!response.ok) {
        let message = '导出失败，请检查权限或稍后再试'
        try {
          const data = await response.json()
          message = data?.message || message
        } catch (e) {}
        ElMessage.error(message)
        return
      }
      const blob = await response.blob()
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `${type}.csv`
      link.click()
      URL.revokeObjectURL(link.href)
    })
}
</script>

<style scoped>
.page-container { padding: 20px; }
.page-card { border-radius: 8px; }
.export-item {
  min-height: 116px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.export-title { font-weight: 600; color: #303133; margin-bottom: 8px; }
.export-desc { color: #909399; font-size: 13px; line-height: 1.5; }
</style>
