<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
          @change="handleDateChange"
        />
        <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px" @change="fetchData">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="attendance_date" label="日期" width="120" />
        <el-table-column label="身份" width="90">
          <template #default="{ row }">{{ row.person_type === 'student' ? '学生' : '教职工' }}</template>
        </el-table-column>
        <el-table-column label="时段" width="100">
          <template #default="{ row }">{{ periodText(row.period_type) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="checkin_time" label="签到时间" width="170" />
        <el-table-column prop="checkout_time" label="签退时间" width="170" />
        <el-table-column prop="source" label="来源" width="110">
          <template #default="{ row }">{{ sourceText(row.source) }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="200" show-overflow-tooltip />
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { getMyAttendance } from '@/api/attendance'

const statusOptions = [
  { label: '正常', value: 'normal' },
  { label: '迟到', value: 'late' },
  { label: '早退', value: 'early_leave' },
  { label: '缺勤', value: 'absent' },
  { label: '请假', value: 'leave' },
  { label: '公出', value: 'official' },
  { label: '节假日', value: 'holiday' },
  { label: '手工', value: 'manual' },
]

const loading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const dateRange = ref<string[]>([])
const query = reactive({
  page: 1,
  page_size: 10,
  status: undefined as string | undefined,
  start_date: undefined as string | undefined,
  end_date: undefined as string | undefined,
})

function statusText(value: string) {
  return statusOptions.find((item) => item.value === value)?.label || value || '-'
}

function statusTag(value: string) {
  if (value === 'normal') return 'success'
  if (value === 'leave' || value === 'official' || value === 'holiday') return 'info'
  if (value === 'absent') return 'danger'
  return 'warning'
}

function periodText(value: string) {
  return ({ day: '全天', morning: '上午', afternoon: '下午', course: '课程', custom: '自定义' } as any)[value] || value || '-'
}

function sourceText(value: string) {
  return ({ manual: '手工', leave_sync: '请假同步', import: '导入', system: '系统' } as any)[value] || value || '-'
}

function handleDateChange(value: string[]) {
  query.start_date = value?.[0]
  query.end_date = value?.[1]
  fetchData()
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getMyAttendance(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.page-card { border-radius: 8px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
