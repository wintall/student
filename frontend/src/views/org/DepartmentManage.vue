<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-input v-model="query.keyword" placeholder="搜索院系名称" clearable style="width: 260px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增院系</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="院系名称" min-width="150" />
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
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
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑院系' : '新增院系'" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="院系名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" placeholder="如: CS, MATH" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">禁用</el-radio>
          </el-radio-group>
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
import { departmentApi } from '@/api/common'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const query = reactive({ keyword: '' })

const form = reactive({ name: '', code: '', status: 1 })
const rules = {
  name: [{ required: true, message: '请输入院系名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await departmentApi.list(query)
    tableData.value = res.data.items || res.data
  } finally { loading.value = false }
}

function openDialog(row?: any) {
  isEdit.value = !!row
  Object.assign(form, { name: row?.name || '', code: row?.code || '', status: row?.status ?? 1 })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (isEdit.value) {
    const row = tableData.value.find(r => r.name === form.name)
    await departmentApi.update(row.id, form)
  } else {
    await departmentApi.create(form)
  }
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await departmentApi.delete(id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(() => fetchData())
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
</style>
