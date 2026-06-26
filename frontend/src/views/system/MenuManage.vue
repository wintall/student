<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-button type="primary" @click="openDialog()"><el-icon><Plus /></el-icon> 新增菜单</el-button>
        <el-button @click="toggleExpand">{{ expandAll ? '全部折叠' : '全部展开' }}</el-button>
      </div>

      <el-table
        :data="menuTree"
        v-loading="loading"
        row-key="id"
        :default-expand-all="expandAll"
        :tree-props="{ children: 'children' }"
        border
        style="width: 100%"
      >
        <el-table-column prop="name" label="菜单标题" min-width="180" />
        <el-table-column prop="type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.type === 1 ? 'primary' : row.type === 2 ? 'warning' : 'info'" size="small">
              {{ row.type === 1 ? '目录' : row.type === 2 ? '菜单' : '按钮' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column prop="path" label="路由" min-width="160" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button link type="success" @click="openDialog(undefined, row.id)">添加子级</el-button>
            <el-popconfirm title="确定删除？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑菜单' : '新增菜单'" width="500px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="上级菜单">
          <el-tree-select
            v-model="form.parent_id"
            :data="parentOptions"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            check-strictly
            placeholder="无（顶级）"
            clearable
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-radio-group v-model="form.type">
            <el-radio :value="1">目录</el-radio>
            <el-radio :value="2">菜单</el-radio>
            <el-radio :value="3">按钮</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="路由">
          <el-input v-model="form.path" placeholder="/system/user" />
        </el-form-item>
        <el-form-item label="权限标识">
          <el-input v-model="form.permission" placeholder="system:user:list" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" />
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
import { createMenu, updateMenu, deleteMenu } from '@/api/common'
import request from '@/utils/request'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const expandAll = ref(true)
const formRef = ref()
const menuTree = ref<any[]>([])
const parentOptions = ref<any[]>([])

const form = reactive({
  parent_id: null as number | null, type: 2, name: '', path: '',
  permission: '', sort_order: 0,
})
const rules = {
  name: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await request.get('/roles/menus/tree')
    menuTree.value = res.data
    parentOptions.value = [{ id: null, name: '顶级菜单', children: res.data }]
  } finally { loading.value = false }
}

function toggleExpand() { expandAll.value = !expandAll.value; fetchData() }

function openDialog(row?: any, parentId?: number) {
  isEdit.value = !!row
  if (row) {
    Object.assign(form, { parent_id: row.parent_id, type: row.type, name: row.name, path: row.path, permission: row.permission, sort_order: row.sort_order })
  } else {
    Object.assign(form, { parent_id: parentId || null, type: 2, name: '', path: '', permission: '', sort_order: 0 })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (isEdit.value) {
    const row = findNode(menuTree.value, form.name)
    if (row) await updateMenu(row.id, form)
  } else {
    await createMenu(form)
  }
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await deleteMenu(id)
  ElMessage.success('删除成功')
  fetchData()
}

function findNode(tree: any[], title: string): any {
  for (const node of tree) {
    if (node.name === title) return node
    if (node.children) {
      const found = findNode(node.children, title)
      if (found) return found
    }
  }
  return null
}

onMounted(() => fetchData())
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; }
</style>
