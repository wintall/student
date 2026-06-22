<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <!-- 搜索栏 -->
      <div class="search-bar">
        <el-input v-model="query.keyword" placeholder="搜索用户名/姓名/手机号" clearable style="width: 260px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="query.status" placeholder="状态" clearable style="width: 120px" @change="fetchData">
          <el-option label="启用" :value="1" />
          <el-option label="禁用" :value="0" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增用户</el-button>
      </div>

      <!-- 表格 -->
      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="real_name" label="姓名" width="100" />
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag v-for="r in row.roles" :key="r.id" size="small" style="margin-right:4px">{{ r.name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.status" :active-value="1" :inactive-value="0" @change="toggleStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button link type="warning" @click="resetPwd(row)">重置密码</el-button>
            <el-popconfirm title="确定删除？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新增用户'" width="520px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少8位，需包含字母和数字" />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="角色" prop="role_ids">
          <el-select v-model="form.role_ids" multiple placeholder="选择角色" style="width: 100%">
            <el-option v-for="r in roleOptions" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
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
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { userApi, roleApi } from '@/api/common'

const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const roleOptions = ref<any[]>([])

const query = reactive({ page: 1, page_size: 10, keyword: '', status: undefined as number | undefined })

const form = reactive({
  username: '', password: '', real_name: '', phone: '', email: '',
  role_ids: [] as number[], status: 1,
})

const validatePwd = (_: any, value: string, cb: any) => {
  if (!value) {
    cb()
  } else if (value.length < 8) {
    cb(new Error('密码长度至少为8位'))
  } else if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
    cb(new Error('密码必须同时包含字母和数字'))
  } else {
    cb()
  }
}

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ validator: validatePwd, trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await userApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function fetchRoles() {
  const res = await roleApi.list()
  roleOptions.value = res.data.items || res.data
}

function openDialog(row?: any) {
  isEdit.value = !!row
  if (row) {
    Object.assign(form, {
      username: row.username, real_name: row.real_name, phone: row.phone,
      email: row.email, status: row.status,
      role_ids: row.roles?.map((r: any) => r.id) || [],
    })
  } else {
    Object.assign(form, { username: '', password: '', real_name: '', phone: '', email: '', role_ids: [], status: 1 })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitLoading.value = true
  try {
    if (isEdit.value) {
      const row = tableData.value.find(r => r.username === form.username)
      await userApi.update(row.id, form)
    } else {
      await userApi.create(form)
    }
    ElMessage.success(isEdit.value ? '编辑成功' : '创建成功')
    dialogVisible.value = false
    fetchData()
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(id: number) {
  await userApi.delete(id)
  ElMessage.success('删除成功')
  fetchData()
}

async function toggleStatus(row: any) {
  await userApi.update(row.id, { status: row.status })
  ElMessage.success('状态已更新')
}

async function resetPwd(row: any) {
  await userApi.update(row.id, { password: '123456Ab', must_change_pwd: true })
  ElMessage.success('密码已重置为 123456Ab')
}

onMounted(() => { fetchData(); fetchRoles() })
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
