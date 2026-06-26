<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-input v-model="query.keyword" placeholder="搜索姓名/学号" clearable style="width: 220px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="query.clazz_id" placeholder="选择班级" clearable style="width: 180px" @change="fetchData">
          <el-option v-for="c in clazzOptions" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button v-permission="'people:student:create'" type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增学生</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="student_no" label="学号" width="130" />
        <el-table-column label="性别" width="70">
          <template #default="{ row }">{{ row.gender === 1 ? '男' : '女' }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column label="班级" min-width="150">
          <template #default="{ row }">{{ row.clazz?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="入学年份" width="100">
          <template #default="{ row }">{{ row.enrollment_year }}</template>
        </el-table-column>
        <el-table-column v-if="canManage" label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="'people:student:update'" link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-popconfirm v-if="hasPermission('people:student:delete')" title="确定删除？" @confirm="handleDelete(row.id)">
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑学生' : '新增学生'" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="姓名" prop="name">
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="学号" prop="student_no">
              <el-input v-model="form.student_no" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="性别">
              <el-radio-group v-model="form.gender">
                <el-radio :value="1">男</el-radio>
                <el-radio :value="2">女</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="入学年份">
              <el-input v-model="form.enrollment_year" placeholder="如: 2024" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="手机号" prop="phone">
              <el-input v-model="form.phone" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="所属班级" prop="clazz_id">
          <el-select v-model="form.clazz_id" placeholder="选择班级" style="width: 100%">
            <el-option v-for="c in clazzOptions" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="身份证号">
          <el-input v-model="form.id_card" />
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
import { studentApi, clazzApi } from '@/api/common'
import { hasPermission } from '@/utils/permission'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const clazzOptions = ref<any[]>([])
const editId = ref(0)
const canManage = hasPermission(['people:student:update', 'people:student:delete'])

const query = reactive({ page: 1, page_size: 10, keyword: '', clazz_id: undefined as number | undefined })

const form = reactive({
  name: '', student_no: '', gender: 1, phone: '', email: '',
  clazz_id: null as number | null, enrollment_year: '', id_card: '',
})
const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  student_no: [{ required: true, message: '请输入学号', trigger: 'blur' }],
  clazz_id: [{ required: true, message: '请选择班级', trigger: 'change' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await studentApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally { loading.value = false }
}

async function fetchClazzes() {
  const res = await clazzApi.list({ page: 1, page_size: 100 })
  clazzOptions.value = res.data.items || res.data
}

function openDialog(row?: any) {
  isEdit.value = !!row
  editId.value = row?.id || 0
  Object.assign(form, {
    name: row?.name || '', student_no: row?.student_no || '',
    gender: row?.gender ?? 1, phone: row?.phone || '', email: row?.email || '',
    clazz_id: row?.clazz_id || null, enrollment_year: row?.enrollment_year || '',
    id_card: row?.id_card || '',
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (isEdit.value) {
    await studentApi.update(editId.value, form)
  } else {
    await studentApi.create(form)
  }
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await studentApi.delete(id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(() => { fetchData(); fetchClazzes() })
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
