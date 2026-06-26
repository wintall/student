<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-select v-model="query.term_id" placeholder="学期" clearable filterable style="width: 220px" @change="fetchData">
          <el-option v-for="t in termOptions" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-select v-model="query.weekday" placeholder="星期" clearable style="width: 120px" @change="fetchData">
          <el-option v-for="d in weekdays" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
        <el-input v-model="query.keyword" placeholder="搜索课程" clearable style="width: 180px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增课表</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="term_name" label="学期" min-width="180" show-overflow-tooltip />
        <el-table-column prop="course_name" label="课程" min-width="150" />
        <el-table-column prop="clazz_name" label="班级" min-width="130" />
        <el-table-column prop="teacher_name" label="教师" width="110" />
        <el-table-column prop="classroom_name" label="教室" width="120" />
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">
            {{ weekdayText(row.weekday) }} 第{{ row.start_section }}-{{ row.end_section }}节
          </template>
        </el-table-column>
        <el-table-column label="周次" width="130">
          <template #default="{ row }">
            {{ row.start_week }}-{{ row.end_week }}周 {{ weekTypeText(row.week_type) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '正常' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-popconfirm title="确定删除该课表？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size"
          :total="total" :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchData" @current-change="fetchData" />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑课表' : '新增课表'" width="680px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="86px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="学期" prop="term_id">
              <el-select v-model="form.term_id" filterable placeholder="选择学期" style="width: 100%">
                <el-option v-for="t in termOptions" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="课程" prop="course_id">
              <el-select v-model="form.course_id" filterable placeholder="选择课程" style="width: 100%">
                <el-option v-for="c in courseOptions" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="班级" prop="clazz_id">
              <el-select v-model="form.clazz_id" filterable placeholder="选择班级" style="width: 100%">
                <el-option v-for="c in clazzOptions" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="教师" prop="teacher_id">
              <el-select v-model="form.teacher_id" filterable placeholder="选择教师" style="width: 100%">
                <el-option v-for="t in teacherOptions" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="教室">
              <el-select v-model="form.classroom_id" filterable clearable placeholder="选择教室" style="width: 100%">
                <el-option v-for="c in classroomOptions" :key="c.id" :label="`${c.name} (${c.capacity}人)`" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="星期" prop="weekday">
              <el-select v-model="form.weekday" style="width: 100%">
                <el-option v-for="d in weekdays" :key="d.value" :label="d.label" :value="d.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="节次" required>
              <div class="range-row">
                <el-input-number v-model="form.start_section" :min="1" :max="20" />
                <span>至</span>
                <el-input-number v-model="form.end_section" :min="1" :max="20" />
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="周次" required>
              <div class="range-row">
                <el-input-number v-model="form.start_week" :min="1" :max="60" />
                <span>至</span>
                <el-input-number v-model="form.end_week" :min="1" :max="60" />
              </div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="单双周">
              <el-select v-model="form.week_type" style="width: 100%">
                <el-option label="每周" value="all" />
                <el-option label="单周" value="odd" />
                <el-option label="双周" value="even" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="类型">
              <el-select v-model="form.schedule_type" style="width: 100%">
                <el-option label="正常" value="normal" />
                <el-option label="补课" value="makeup" />
                <el-option label="临时" value="temporary" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">正常</el-radio>
            <el-radio :value="0">停用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" />
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
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { clazzApi, courseApi, teacherApi } from '@/api/common'
import { classroomApi, courseScheduleApi, termApi } from '@/api/schedule'

const weekdays = [
  { label: '周一', value: 1 },
  { label: '周二', value: 2 },
  { label: '周三', value: 3 },
  { label: '周四', value: 4 },
  { label: '周五', value: 5 },
  { label: '周六', value: 6 },
  { label: '周日', value: 7 },
]

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const editId = ref(0)
const termOptions = ref<any[]>([])
const courseOptions = ref<any[]>([])
const clazzOptions = ref<any[]>([])
const teacherOptions = ref<any[]>([])
const classroomOptions = ref<any[]>([])

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  term_id: undefined as number | undefined,
  weekday: undefined as number | undefined,
})
const form = reactive({
  term_id: null as number | null,
  course_id: null as number | null,
  clazz_id: null as number | null,
  teacher_id: null as number | null,
  classroom_id: null as number | null,
  weekday: 1,
  start_section: 1,
  end_section: 2,
  start_week: 1,
  end_week: 16,
  week_type: 'all',
  schedule_type: 'normal',
  status: 1,
  remark: '',
})

const rules = {
  term_id: [{ required: true, message: '请选择学期', trigger: 'change' }],
  course_id: [{ required: true, message: '请选择课程', trigger: 'change' }],
  clazz_id: [{ required: true, message: '请选择班级', trigger: 'change' }],
  teacher_id: [{ required: true, message: '请选择教师', trigger: 'change' }],
  weekday: [{ required: true, message: '请选择星期', trigger: 'change' }],
}

function weekdayText(value: number) {
  return weekdays.find(item => item.value === value)?.label || '-'
}

function weekTypeText(value: string) {
  return ({ all: '每周', odd: '单周', even: '双周' } as any)[value] || value
}

async function fetchOptions() {
  const [termRes, courseRes, clazzRes, teacherRes, classroomRes] = await Promise.all([
    termApi.list({ page: 1, page_size: 100, status: 1 }),
    courseApi.list({ page: 1, page_size: 100 }),
    clazzApi.list({ page: 1, page_size: 100 }),
    teacherApi.list({ page: 1, page_size: 100 }),
    classroomApi.list({ page: 1, page_size: 100, status: 1 }),
  ])
  termOptions.value = termRes.data.items || []
  courseOptions.value = courseRes.data.items || []
  clazzOptions.value = clazzRes.data.items || []
  teacherOptions.value = teacherRes.data.items || []
  classroomOptions.value = classroomRes.data.items || []
  const current = termOptions.value.find(item => item.is_current)
  if (current && !query.term_id) query.term_id = current.id
}

async function fetchData() {
  loading.value = true
  try {
    const res = await courseScheduleApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function openDialog(row?: any) {
  isEdit.value = !!row
  editId.value = row?.id || 0
  Object.assign(form, {
    term_id: row?.term_id || query.term_id || null,
    course_id: row?.course_id || null,
    clazz_id: row?.clazz_id || null,
    teacher_id: row?.teacher_id || null,
    classroom_id: row?.classroom_id || null,
    weekday: row?.weekday ?? 1,
    start_section: row?.start_section ?? 1,
    end_section: row?.end_section ?? 2,
    start_week: row?.start_week ?? 1,
    end_week: row?.end_week ?? 16,
    week_type: row?.week_type || 'all',
    schedule_type: row?.schedule_type || 'normal',
    status: row?.status ?? 1,
    remark: row?.remark || '',
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (form.start_section > form.end_section) {
    ElMessage.warning('开始节次不能大于结束节次')
    return
  }
  if (form.start_week > form.end_week) {
    ElMessage.warning('开始周不能大于结束周')
    return
  }
  if (isEdit.value) await courseScheduleApi.update(editId.value, form)
  else await courseScheduleApi.create(form)
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await courseScheduleApi.delete(id)
  ElMessage.success('删除成功')
  fetchData()
}

fetchOptions().then(fetchData)
</script>

<style scoped>
.page-card { border-radius: 8px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
.range-row { display: flex; align-items: center; gap: 8px; width: 100%; }
.range-row :deep(.el-input-number) { width: 110px; }
</style>
