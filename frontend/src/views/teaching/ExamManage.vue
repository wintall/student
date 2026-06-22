<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-select v-model="query.course_id" placeholder="选择课程" clearable style="width: 200px" @change="fetchData">
          <el-option v-for="c in courseOptions" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增考试</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="考试名称" min-width="150" />
        <el-table-column label="所属课程" width="150">
          <template #default="{ row }">{{ row.course?.name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="exam_date" label="考试日期" width="120" />
        <el-table-column label="考试类型" width="100">
          <template #default="{ row }">
            {{ ['','期中','期末','补考','模拟','测验'][row.exam_type] || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="location" label="考场地点" min-width="130" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 0 ? 'info' : row.status === 1 ? 'success' : 'warning'" size="small">
              {{ ['未开始','进行中','已结束'][row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-popconfirm title="确定删除？" @confirm="handleDelete(row.id)">
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑考试' : '新增考试'" width="520px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="考试名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="所属课程" prop="course_id">
          <el-select v-model="form.course_id" placeholder="选择课程" style="width: 100%">
            <el-option v-for="c in courseOptions" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="考试日期">
              <el-date-picker v-model="form.exam_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="考试类型">
              <el-select v-model="form.exam_type" style="width: 100%">
                <el-option label="期中" :value="1" />
                <el-option label="期末" :value="2" />
                <el-option label="补考" :value="3" />
                <el-option label="模拟" :value="4" />
                <el-option label="测验" :value="5" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="考场地点">
          <el-input v-model="form.location" />
        </el-form-item>
        <el-form-item label="满分">
          <el-input-number v-model="form.total_score" :min="1" :max="1000" />
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { examApi, courseApi } from '@/api/common'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const courseOptions = ref<any[]>([])
const editId = ref(0)

const query = reactive({ page: 1, page_size: 10, course_id: undefined as number | undefined })

const form = reactive({
  name: '', course_id: null as number | null, exam_date: '',
  exam_type: 1, location: '', total_score: 100,
})
const rules = {
  name: [{ required: true, message: '请输入考试名称', trigger: 'blur' }],
  course_id: [{ required: true, message: '请选择课程', trigger: 'change' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await examApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally { loading.value = false }
}

async function fetchCourses() {
  const res = await courseApi.list({ page: 1, page_size: 100 })
  courseOptions.value = res.data.items || res.data
}

function openDialog(row?: any) {
  isEdit.value = !!row
  editId.value = row?.id || 0
  Object.assign(form, {
    name: row?.name || '', course_id: row?.course_id || null,
    exam_date: row?.exam_date || '', exam_type: row?.exam_type ?? 1,
    location: row?.location || '', total_score: row?.total_score ?? 100,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (isEdit.value) {
    await examApi.update(editId.value, form)
  } else {
    await examApi.create(form)
  }
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await examApi.delete(id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(() => { fetchData(); fetchCourses() })
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
