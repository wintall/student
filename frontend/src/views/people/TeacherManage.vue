<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-input v-model="query.keyword" placeholder="搜索姓名/工号" clearable style="width: 220px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="query.department_id" placeholder="选择院系" clearable style="width: 160px" @change="fetchData">
          <el-option v-for="d in deptOptions" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增教职工</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="employee_no" label="工号" width="120" />
        <el-table-column label="性别" width="70">
          <template #default="{ row }">{{ row.gender === 1 ? '男' : '女' }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column label="所属院系" min-width="130">
          <template #default="{ row }">{{ row.department?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="职务" width="100">
          <template #default="{ row }">{{ ['教师','系主任','院长','副校长'][row.position] || '-' }}</template>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑教职工' : '新增教职工'" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="姓名" prop="name">
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工号" prop="employee_no">
              <el-input v-model="form.employee_no" />
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
            <el-form-item label="职务">
              <el-select v-model="form.position" style="width: 100%">
                <el-option label="教师" :value="0" />
                <el-option label="系主任" :value="1" />
                <el-option label="院长" :value="2" />
                <el-option label="副校长" :value="3" />
              </el-select>
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
        <el-form-item label="所属院系" prop="department_id">
          <el-select v-model="form.department_id" placeholder="选择院系" style="width: 100%">
            <el-option v-for="d in deptOptions" :key="d.id" :label="d.name" :value="d.id" />
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
import { teacherApi, departmentApi } from '@/api/common'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const deptOptions = ref<any[]>([])
const editId = ref(0)

const query = reactive({ page: 1, page_size: 10, keyword: '', department_id: undefined as number | undefined })

const form = reactive({
  name: '', employee_no: '', gender: 1, phone: '', email: '',
  department_id: null as number | null, position: 0,
})
const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  employee_no: [{ required: true, message: '请输入工号', trigger: 'blur' }],
  department_id: [{ required: true, message: '请选择院系', trigger: 'change' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await teacherApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally { loading.value = false }
}

async function fetchDepts() {
  const res = await departmentApi.list()
  deptOptions.value = res.data.items || res.data
}

function openDialog(row?: any) {
  isEdit.value = !!row
  editId.value = row?.id || 0
  Object.assign(form, {
    name: row?.name || '', employee_no: row?.employee_no || '',
    gender: row?.gender ?? 1, phone: row?.phone || '', email: row?.email || '',
    department_id: row?.department_id || null, position: row?.position ?? 0,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (isEdit.value) {
    await teacherApi.update(editId.value, form)
  } else {
    await teacherApi.create(form)
  }
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await teacherApi.delete(id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(() => { fetchData(); fetchDepts() })
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
