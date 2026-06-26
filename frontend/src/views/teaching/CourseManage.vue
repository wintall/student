<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-input v-model="query.keyword" placeholder="搜索课程名称/编号" clearable style="width: 240px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button v-permission="'teaching:course:create'" type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增课程</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="课程名称" min-width="150" />
        <el-table-column prop="code" label="课程编号" width="120" />
        <el-table-column prop="credit" label="学分" width="80" />
        <el-table-column prop="hours" label="学时" width="80" />
        <el-table-column label="授课教师" width="120">
          <template #default="{ row }">{{ row.teacher?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small">{{ row.course_type === 1 ? '必修' : '选修' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="canManage" label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="'teaching:course:update'" link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-popconfirm v-if="hasPermission('teaching:course:delete')" title="确定删除？" @confirm="handleDelete(row.id)">
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑课程' : '新增课程'" width="520px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="课程名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="课程编号" prop="code">
          <el-input v-model="form.code" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="学分">
              <el-input-number v-model="form.credit" :min="0" :max="10" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="学时">
              <el-input-number v-model="form.hours" :min="0" :max="200" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="课程类型">
          <el-radio-group v-model="form.course_type">
            <el-radio :value="1">必修</el-radio>
            <el-radio :value="2">选修</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="授课教师">
          <el-select v-model="form.teacher_id" placeholder="选择教师" clearable style="width: 100%">
            <el-option v-for="t in teacherOptions" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
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
import { courseApi, teacherApi } from '@/api/common'
import { hasPermission } from '@/utils/permission'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const teacherOptions = ref<any[]>([])
const editId = ref(0)
const canManage = hasPermission(['teaching:course:update', 'teaching:course:delete'])

const query = reactive({ page: 1, page_size: 10, keyword: '' })

const form = reactive({
  name: '', code: '', credit: 4, hours: 64,
  course_type: 1, teacher_id: null as number | null,
})
const rules = {
  name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入课程编号', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await courseApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally { loading.value = false }
}

async function fetchTeachers() {
  const res = await teacherApi.list({ page: 1, page_size: 100 })
  teacherOptions.value = res.data.items || res.data
}

function openDialog(row?: any) {
  isEdit.value = !!row
  editId.value = row?.id || 0
  Object.assign(form, {
    name: row?.name || '', code: row?.code || '',
    credit: row?.credit ?? 4, hours: row?.hours ?? 64,
    course_type: row?.course_type ?? 1, teacher_id: row?.teacher_id || null,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (isEdit.value) {
    await courseApi.update(editId.value, form)
  } else {
    await courseApi.create(form)
  }
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await courseApi.delete(id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(() => { fetchData(); fetchTeachers() })
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
