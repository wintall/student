<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <template #header>
        <div class="card-header">
          <span>通知中心</span>
          <el-button @click="markAllRead">全部已读</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="list" empty-text="暂无通知">
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_read ? 'info' : 'primary'">{{ row.is_read ? '已读' : '未读' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="content" label="内容" min-width="320" show-overflow-tooltip />
        <el-table-column prop="category" label="类型" width="120" />
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button v-if="!row.is_read" link type="primary" @click="markRead(row)">标记已读</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="fetchData"
          @size-change="fetchData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listNotifications, markAllNotificationsRead, markNotificationRead } from '@/api/operations'

const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

async function fetchData() {
  loading.value = true
  try {
    const res = await listNotifications({ page: page.value, page_size: pageSize.value })
    list.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

async function markRead(row: any) {
  await markNotificationRead(row.id)
  row.is_read = true
  ElMessage.success('已标记为已读')
}

async function markAllRead() {
  await markAllNotificationsRead()
  ElMessage.success('已全部标记为已读')
  fetchData()
}

onMounted(fetchData)
</script>

<style scoped>
.page-container { padding: 20px; }
.page-card { border-radius: 8px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
