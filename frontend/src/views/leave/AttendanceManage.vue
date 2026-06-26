<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-input
          v-model="query.keyword"
          :placeholder="personType === 'student' ? '搜索学生/学号' : '搜索教职工/工号'"
          clearable
          style="width: 220px"
          @keyup.enter="fetchData"
          @clear="fetchData"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
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
        <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px" @change="fetchData">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button v-if="canCreate" type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增考勤</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="attendance_date" label="日期" width="115" />
        <el-table-column prop="person_name" :label="personType === 'student' ? '学生' : '教职工'" width="110" />
        <el-table-column v-if="personType === 'student'" prop="student_no" label="学号" width="130" />
        <el-table-column v-else prop="employee_no" label="工号" width="120" />
        <el-table-column prop="department_name" label="院系" min-width="130" show-overflow-tooltip />
        <el-table-column v-if="personType === 'student'" prop="clazz_name" label="班级" min-width="130" show-overflow-tooltip />
        <el-table-column label="时段" width="90">
          <template #default="{ row }">{{ periodText(row.period_type) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="100">
          <template #default="{ row }">{{ sourceText(row.source) }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="170" show-overflow-tooltip />
        <el-table-column v-if="canManage" label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canUpdate" link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-popconfirm v-if="canDelete" title="确定删除该考勤记录？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑考勤' : '新增考勤'" width="620px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="personType === 'student' ? '学生' : '教职工'" :prop="personType === 'student' ? 'student_id' : 'teacher_id'">
              <el-select
                v-if="personType === 'student'"
                v-model="form.student_id"
                filterable
                remote
                reserve-keyword
                :remote-method="remoteSearchCandidates"
                :loading="candidateLoading"
                :disabled="isEdit"
                placeholder="搜索姓名或学号"
                style="width: 100%"
                @focus="loadCandidates()"
              >
                <el-option
                  v-for="item in candidateOptions"
                  :key="item.id"
                  :label="studentCandidateLabel(item)"
                  :value="item.id"
                />
              </el-select>
              <el-select
                v-else
                v-model="form.teacher_id"
                filterable
                remote
                reserve-keyword
                :remote-method="remoteSearchCandidates"
                :loading="candidateLoading"
                :disabled="isEdit"
                placeholder="搜索姓名或工号"
                style="width: 100%"
                @focus="loadCandidates()"
              >
                <el-option
                  v-for="item in candidateOptions"
                  :key="item.id"
                  :label="teacherCandidateLabel(item)"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="考勤日期" prop="attendance_date">
              <el-date-picker v-model="form.attendance_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="时段" prop="period_type">
              <el-select v-model="form.period_type" style="width: 100%">
                <el-option label="全天" value="day" />
                <el-option label="上午" value="morning" />
                <el-option label="下午" value="afternoon" />
                <el-option label="课程" value="course" />
                <el-option label="自定义" value="custom" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" style="width: 100%">
                <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="签到时间">
              <el-date-picker v-model="form.checkin_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="签退时间">
              <el-date-picker v-model="form.checkout_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import {
  createAttendance,
  deleteAttendance,
  getStudentAttendance,
  getStudentAttendanceCandidates,
  getTeacherAttendance,
  getTeacherAttendanceCandidates,
  updateAttendance,
} from '@/api/attendance'
import { hasPermission } from '@/utils/permission'

const props = defineProps<{ personType: 'student' | 'teacher' }>()
const personType = computed(() => props.personType)

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
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const editId = ref(0)
const dateRange = ref<string[]>([])
const candidateLoading = ref(false)
const candidateOptions = ref<any[]>([])

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  status: undefined as string | undefined,
  start_date: undefined as string | undefined,
  end_date: undefined as string | undefined,
})

const form = reactive({
  person_type: 'student' as 'student' | 'teacher',
  student_id: undefined as number | undefined,
  teacher_id: undefined as number | undefined,
  attendance_date: '',
  period_type: 'day',
  checkin_time: '',
  checkout_time: '',
  status: 'normal',
  remark: '',
})

const rules = {
  student_id: [{ required: true, message: '请选择学生', trigger: 'change' }],
  teacher_id: [{ required: true, message: '请选择教职工', trigger: 'change' }],
  attendance_date: [{ required: true, message: '请选择考勤日期', trigger: 'change' }],
  period_type: [{ required: true, message: '请选择时段', trigger: 'change' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

const canCreate = computed(() => hasPermission(`attendance:${personType.value}:create`))
const canUpdate = computed(() => hasPermission(`attendance:${personType.value}:update`))
const canDelete = computed(() => hasPermission(`attendance:${personType.value}:delete`))
const canManage = computed(() => canUpdate.value || canDelete.value)

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

function studentCandidateLabel(item: any) {
  return `${item.name}（${item.student_no}）${item.clazz_name ? ` - ${item.clazz_name}` : ''}`
}

function teacherCandidateLabel(item: any) {
  return `${item.name}（${item.employee_no}）${item.department_name ? ` - ${item.department_name}` : ''}`
}

function handleDateChange(value: string[]) {
  query.start_date = value?.[0]
  query.end_date = value?.[1]
  fetchData()
}

async function fetchData() {
  loading.value = true
  try {
    const res = personType.value === 'student'
      ? await getStudentAttendance(query)
      : await getTeacherAttendance(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function loadCandidates(keyword = '') {
  if (!canCreate.value) return
  candidateLoading.value = true
  try {
    const params = { keyword: keyword || undefined, limit: 20 }
    const res = personType.value === 'student'
      ? await getStudentAttendanceCandidates(params)
      : await getTeacherAttendanceCandidates(params)
    candidateOptions.value = res.data || []
  } finally {
    candidateLoading.value = false
  }
}

function remoteSearchCandidates(keyword: string) {
  loadCandidates(keyword)
}

function ensureCurrentCandidate(row: any) {
  if (!row) return
  candidateOptions.value = [{
    id: personType.value === 'student' ? row.student_id : row.teacher_id,
    name: row.person_name,
    student_no: row.student_no,
    employee_no: row.employee_no,
    clazz_name: row.clazz_name,
    department_name: row.department_name,
  }].filter((item) => item.id)
}

function openDialog(row?: any) {
  isEdit.value = !!row
  editId.value = row?.id || 0
  if (row) ensureCurrentCandidate(row)
  else loadCandidates()
  Object.assign(form, {
    person_type: personType.value,
    student_id: row?.student_id,
    teacher_id: row?.teacher_id,
    attendance_date: row?.attendance_date || '',
    period_type: row?.period_type || 'day',
    checkin_time: row?.checkin_time ? row.checkin_time.replace(' ', 'T') : '',
    checkout_time: row?.checkout_time ? row.checkout_time.replace(' ', 'T') : '',
    status: row?.status || 'normal',
    remark: row?.remark || '',
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  const payload: any = {
    person_type: personType.value,
    attendance_date: form.attendance_date,
    period_type: form.period_type,
    checkin_time: form.checkin_time || undefined,
    checkout_time: form.checkout_time || undefined,
    status: form.status,
    remark: form.remark,
  }
  if (personType.value === 'student') payload.student_id = form.student_id
  else payload.teacher_id = form.teacher_id

  if (isEdit.value) await updateAttendance(editId.value, payload)
  else await createAttendance(payload)
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await deleteAttendance(id)
  ElMessage.success('删除成功')
  fetchData()
}

watch(() => props.personType, () => {
  query.page = 1
  tableData.value = []
  candidateOptions.value = []
  fetchData()
}, { immediate: true })
</script>

<style scoped>
.page-card { border-radius: 8px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
