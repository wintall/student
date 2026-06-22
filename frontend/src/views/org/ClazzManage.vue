<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-select v-model="query.department_id" placeholder="选择院系" clearable style="width: 180px" @change="fetchData">
          <el-option v-for="d in deptOptions" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增班级</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="班级名称" min-width="150" />
        <el-table-column prop="grade" label="年级" width="100" />
        <el-table-column label="所属院系" width="150">
          <template #default="{ row }">
            {{ row.department?.name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑班级' : '新增班级'" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="班级名称" prop="name">
          <el-input v-model="form.name" placeholder="如: 计算机2024-1班" />
        </el-form-item>
        <el-form-item label="年级" prop="grade">
          <el-input v-model="form.grade" placeholder="如: 2024" />
        </el-form-item>
        <el-form-item label="所属院系" prop="department_id">
          <el-select v-model="form.department_id" placeholder="选择院系" style="width: 100%">
            <el-option v-for="d in deptOptions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="辅导员">
          <el-input v-model="form.counselor" />
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
import { clazzApi, departmentApi } from '@/api/common'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const deptOptions = ref<any[]>([])

const query = reactive({ page: 1, page_size: 10, department_id: undefined as number | undefined })

const form = reactive({ name: '', grade: '', department_id: null as number | null, counselor: '' })
const rules = {
  name: [{ required: true, message: '请输入班级名称', trigger: 'blur' }],
  department_id: [{ required: true, message: '请选择院系', trigger: 'change' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await clazzApi.list(query)
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
  Object.assign(form, {
    name: row?.name || '', grade: row?.grade || '',
    department_id: row?.department_id || null, counselor: row?.counselor || '',
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (isEdit.value) {
    await clazzApi.update(tableData.value.find(r => r.name === form.name)?.id, form)
  } else {
    await clazzApi.create(form)
  }
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await clazzApi.delete(id)
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
