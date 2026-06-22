<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-button type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增角色</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="角色名称" min-width="120" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button link type="warning" @click="openPermDialog(row)">权限配置</el-button>
            <el-popconfirm title="确定删除？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button link type="danger" :disabled="row.name === 'admin'">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 角色编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑角色' : '新增角色'" width="460px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="角色名" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 权限配置对话框 -->
    <el-dialog v-model="permVisible" title="权限配置" width="460px">
      <el-tree
        ref="treeRef"
        :data="menuTree"
        show-checkbox
        node-key="id"
        :default-checked-keys="checkedKeys"
        :props="{ label: 'name', children: 'children' }"
        default-expand-all
      />
      <template #footer>
        <el-button @click="permVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPerms">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { roleApi, getRoleMenus } from '@/api/common'
import request from '@/utils/request'

const loading = ref(false)
const dialogVisible = ref(false)
const permVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const treeRef = ref()
const tableData = ref<any[]>([])
const menuTree = ref<any[]>([])
const checkedKeys = ref<number[]>([])
const currentRoleId = ref(0)

const form = reactive({ name: '', description: '' })
const rules = { name: [{ required: true, message: '请输入角色名', trigger: 'blur' }] }

async function fetchData() {
  loading.value = true
  try {
    const res = await roleApi.list()
    tableData.value = res.data.items || res.data
  } finally { loading.value = false }
}

function openDialog(row?: any) {
  isEdit.value = !!row
  Object.assign(form, { name: row?.name || '', description: row?.description || '' })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (isEdit.value) {
    const row = tableData.value.find(r => r.name === form.name)
    await roleApi.update(row?.id, form)
  } else {
    await roleApi.create(form)
  }
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await roleApi.delete(id)
  ElMessage.success('删除成功')
  fetchData()
}

async function openPermDialog(row: any) {
  currentRoleId.value = row.id
  const res = await request.get('/roles/menus/tree')
  menuTree.value = res.data
  const roleRes = await request.get(`/roles/${row.id}`)
  checkedKeys.value = roleRes.data.menu_ids || []
  permVisible.value = true
}

async function submitPerms() {
  const checked = treeRef.value.getCheckedKeys(false)
  const halfChecked = treeRef.value.getHalfCheckedKeys()
  const menuIds = [...checked, ...halfChecked]
  await request.post('/roles/assign-menus', { role_id: currentRoleId.value, menu_ids: menuIds })
  ElMessage.success('权限配置成功')
  permVisible.value = false
}

onMounted(() => fetchData())
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; }
</style>
