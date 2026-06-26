<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-input v-model="query.keyword" placeholder="搜索原因/申请人" clearable style="width: 220px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px" @change="fetchData">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="query.leave_type" placeholder="请假类型" clearable style="width: 140px" @change="fetchData">
          <el-option v-for="item in leaveTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button type="success" @click="openCreate"><el-icon><Plus /></el-icon> 提交请假</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ leaveTypeText(row.leave_type) }}</template>
        </el-table-column>
        <el-table-column label="时间" min-width="220">
          <template #default="{ row }">
            <div class="time-cell">{{ row.start_time }}</div>
            <div class="time-cell muted">至 {{ row.end_time }}</div>
          </template>
        </el-table-column>
        <el-table-column label="时长" width="90">
          <template #default="{ row }">{{ row.duration_hours }} 小时</template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审批人" width="110">
          <template #default="{ row }">{{ row.reviewer_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-popconfirm v-if="row.status === 'pending'" title="确定撤销这条请假吗？" @confirm="handleCancel(row.id)">
              <template #reference>
                <el-button link type="danger">撤销</el-button>
              </template>
            </el-popconfirm>
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

    <el-dialog v-model="createVisible" title="提交请假" width="620px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="请假类型" prop="leave_type">
              <el-select v-model="form.leave_type" style="width: 100%">
                <el-option v-for="item in leaveTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="申请身份">
              <el-select v-model="form.applicant_type" clearable placeholder="自动识别" style="width: 100%">
                <el-option label="学生" value="student" />
                <el-option label="教职工" value="teacher" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="请假时间" prop="time_range">
          <el-date-picker
            v-model="form.time_range"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
            class="leave-range-picker"
          />
        </el-form-item>
        <el-form-item label="请假原因" prop="reason">
          <el-input v-model="form.reason" type="textarea" :rows="4" maxlength="1000" show-word-limit />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="去向/地点">
              <el-input v-model="form.destination" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="form.contact_phone" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="紧急联系人">
              <el-input v-model="form.emergency_contact" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="证明材料">
              <el-input v-model="form.attachment_url" placeholder="附件地址，可选" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.remark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="请假详情" width="560px">
      <el-descriptions v-if="current" :column="1" border>
        <el-descriptions-item label="申请人">{{ current.applicant_name }}</el-descriptions-item>
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
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { cancelLeaveRequest, createLeaveRequest, getMyLeaveRequests } from '@/api/leave'

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
const createVisible = ref(false)
const detailVisible = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const current = ref<any>()

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  status: undefined as string | undefined,
  leave_type: undefined as string | undefined,
})

const form = reactive({
  applicant_type: '',
  leave_type: 'personal',
  time_range: [] as string[],
  reason: '',
  destination: '',
  contact_phone: '',
  emergency_contact: '',
  attachment_url: '',
  remark: '',
})

const rules = {
  leave_type: [{ required: true, message: '请选择请假类型', trigger: 'change' }],
  time_range: [{ required: true, message: '请选择请假时间', trigger: 'change' }],
  reason: [{ required: true, message: '请输入请假原因', trigger: 'blur' }],
}

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
    const res = await getMyLeaveRequests(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, {
    applicant_type: '',
    leave_type: 'personal',
    time_range: [],
    reason: '',
    destination: '',
    contact_phone: '',
    emergency_contact: '',
    attachment_url: '',
    remark: '',
  })
  createVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  await createLeaveRequest({
    applicant_type: form.applicant_type || undefined,
    leave_type: form.leave_type,
    start_time: form.time_range[0],
    end_time: form.time_range[1],
    reason: form.reason,
    destination: form.destination,
    contact_phone: form.contact_phone,
    emergency_contact: form.emergency_contact,
    attachment_url: form.attachment_url,
    remark: form.remark,
  })
  ElMessage.success('提交成功')
  createVisible.value = false
  fetchData()
}

function openDetail(row: any) {
  current.value = row
  detailVisible.value = true
}

async function handleCancel(id: number) {
  await cancelLeaveRequest(id)
  ElMessage.success('撤销成功')
  fetchData()
}

onMounted(fetchData)
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
.leave-range-picker { width: 100%; max-width: 100%; }
.time-cell { line-height: 20px; white-space: nowrap; }
.muted { color: #909399; }
</style>
