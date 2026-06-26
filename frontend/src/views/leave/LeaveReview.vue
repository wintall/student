<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-input v-model="query.keyword" placeholder="搜索申请人/原因" clearable style="width: 220px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px" @change="fetchData">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="query.applicant_type" placeholder="申请身份" clearable style="width: 140px" @change="fetchData">
          <el-option label="学生" value="student" />
          <el-option label="教职工" value="teacher" />
        </el-select>
        <el-select v-model="query.leave_type" placeholder="请假类型" clearable style="width: 140px" @change="fetchData">
          <el-option v-for="item in leaveTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="applicant_name" label="申请人" width="110" />
        <el-table-column label="身份" width="90">
          <template #default="{ row }">{{ row.applicant_type === 'student' ? '学生' : '教职工' }}</template>
        </el-table-column>
        <el-table-column label="院系/班级" min-width="150">
          <template #default="{ row }">
            {{ row.department_name || '-' }}<span v-if="row.clazz_name"> / {{ row.clazz_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ leaveTypeText(row.leave_type) }}</template>
        </el-table-column>
        <el-table-column label="时间" min-width="220">
          <template #default="{ row }">
            <div class="time-cell">{{ row.start_time }}</div>
            <div class="time-cell muted">至 {{ row.end_time }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button v-if="row.status === 'pending'" link type="success" @click="openReview(row, 'approve')">通过</el-button>
            <el-button v-if="row.status === 'pending'" link type="danger" @click="openReview(row, 'reject')">驳回</el-button>
          </template>
        </el-table-column>
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

    <el-dialog v-model="detailVisible" title="请假详情" width="580px">
      <el-descriptions v-if="current" :column="1" border>
        <el-descriptions-item label="申请人">{{ current.applicant_name }}</el-descriptions-item>
        <el-descriptions-item label="身份">{{ current.applicant_type === 'student' ? '学生' : '教职工' }}</el-descriptions-item>
        <el-descriptions-item label="院系">{{ current.department_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="班级">{{ current.clazz_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="请假类型">{{ leaveTypeText(current.leave_type) }}</el-descriptions-item>
        <el-descriptions-item label="请假时间">{{ current.start_time }} 至 {{ current.end_time }}</el-descriptions-item>
        <el-descriptions-item label="时长">{{ current.duration_hours }} 小时</el-descriptions-item>
        <el-descriptions-item label="状态">{{ statusText(current.status) }}</el-descriptions-item>
        <el-descriptions-item label="原因">{{ current.reason }}</el-descriptions-item>
        <el-descriptions-item label="去向">{{ current.destination || '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系电话">{{ current.contact_phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="审批人">{{ current.reviewer_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="审批意见">{{ current.review_comment || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="reviewVisible" :title="reviewAction === 'approve' ? '审批通过' : '驳回申请'" width="480px">
      <el-form label-width="80px">
        <el-form-item label="审批意见" :required="reviewAction === 'reject'">
          <el-input v-model="reviewComment" type="textarea" :rows="4" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button :type="reviewAction === 'approve' ? 'success' : 'danger'" @click="handleReview">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { approveLeaveRequest, getReviewLeaveRequests, rejectLeaveRequest } from '@/api/leave'

const leaveTypeOptions = [
  { label: '病假', value: 'sick' },
  { label: '事假', value: 'personal' },
  { label: '公假', value: 'official' },
  { label: '丧假', value: 'funeral' },
  { label: '婚假', value: 'marriage' },
  { label: '产假', value: 'maternity' },
  { label: '其他', value: 'other' },
]

const statusOptions = [
  { label: '待审批', value: 'pending' },
  { label: '已通过', value: 'approved' },
  { label: '已驳回', value: 'rejected' },
  { label: '已撤销', value: 'cancelled' },
]

const loading = ref(false)
const detailVisible = ref(false)
const reviewVisible = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const current = ref<any>()
const reviewAction = ref<'approve' | 'reject'>('approve')
const reviewComment = ref('')

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  status: 'pending' as string | undefined,
  applicant_type: undefined as string | undefined,
  leave_type: undefined as string | undefined,
})

function leaveTypeText(value: string) {
  return leaveTypeOptions.find((item) => item.value === value)?.label || value || '-'
}

function statusText(value: string) {
  return statusOptions.find((item) => item.value === value)?.label || value || '-'
}

function statusTag(value: string) {
  if (value === 'approved') return 'success'
  if (value === 'rejected') return 'danger'
  if (value === 'cancelled') return 'info'
  return 'warning'
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getReviewLeaveRequests(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function openDetail(row: any) {
  current.value = row
  detailVisible.value = true
}

function openReview(row: any, action: 'approve' | 'reject') {
  current.value = row
  reviewAction.value = action
  reviewComment.value = ''
  reviewVisible.value = true
}

async function handleReview() {
  if (!current.value) return
  if (reviewAction.value === 'reject' && !reviewComment.value.trim()) {
    ElMessage.warning('请填写驳回原因')
    return
  }
  if (reviewAction.value === 'approve') {
    await approveLeaveRequest(current.value.id, reviewComment.value)
    ElMessage.success('已审批通过')
  } else {
    await rejectLeaveRequest(current.value.id, reviewComment.value)
    ElMessage.success('已驳回')
  }
  reviewVisible.value = false
  fetchData()
}

onMounted(fetchData)
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
.time-cell { line-height: 20px; white-space: nowrap; }
.muted { color: #909399; }
</style>
