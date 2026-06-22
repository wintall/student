<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-input v-model="query.keyword" placeholder="搜索公告标题" clearable style="width: 240px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="query.type" placeholder="公告类型" clearable style="width: 130px" @change="fetchData">
          <el-option label="通知" :value="1" />
          <el-option label="公告" :value="2" />
          <el-option label="紧急" :value="3" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 发布公告</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="title" label="公告标题" min-width="200" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.type === 3 ? 'danger' : row.type === 2 ? '' : 'info'" size="small">
              {{ ['','通知','公告','紧急'][row.type] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="置顶" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.is_top" @change="toggleTop(row)" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '已发布' : '草稿' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="published_at" label="发布时间" width="170" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewDetail(row)">查看</el-button>
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

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑公告' : '发布公告'" width="640px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="公告标题" prop="title">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="类型">
              <el-select v-model="form.type" style="width: 100%">
                <el-option label="通知" :value="1" />
                <el-option label="公告" :value="2" />
                <el-option label="紧急" :value="3" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-radio-group v-model="form.status">
                <el-radio :value="1">发布</el-radio>
                <el-radio :value="0">草稿</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="8" placeholder="公告内容..." />
        </el-form-item>
        <el-form-item label="置顶">
          <el-switch v-model="form.is_top" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 查看对话框 -->
    <el-dialog v-model="viewVisible" :title="viewData.title" width="600px">
      <div class="view-meta">
        <el-tag size="small">{{ ['','通知','公告','紧急'][viewData.type] }}</el-tag>
        <span class="view-time">{{ viewData.published_at || '未发布' }}</span>
      </div>
      <el-divider />
      <div class="view-content">{{ viewData.content }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { announcementApi } from '@/api/common'

const loading = ref(false)
const dialogVisible = ref(false)
const viewVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const editId = ref(0)

const query = reactive({ page: 1, page_size: 10, keyword: '', type: undefined as number | undefined })

const form = reactive({ title: '', content: '', type: 1, status: 1, is_top: false })
const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
}

const viewData = reactive<any>({ title: '', content: '', type: 1, published_at: '' })

async function fetchData() {
  loading.value = true
  try {
    const res = await announcementApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally { loading.value = false }
}

function openDialog(row?: any) {
  isEdit.value = !!row
  editId.value = row?.id || 0
  Object.assign(form, {
    title: row?.title || '', content: row?.content || '',
    type: row?.type ?? 1, status: row?.status ?? 1, is_top: row?.is_top ?? false,
  })
  dialogVisible.value = true
}

function viewDetail(row: any) {
  Object.assign(viewData, { title: row.title, content: row.content, type: row.type, published_at: row.published_at })
  viewVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (isEdit.value) {
    await announcementApi.update(editId.value, form)
  } else {
    await announcementApi.create(form)
  }
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await announcementApi.delete(id)
  ElMessage.success('删除成功')
  fetchData()
}

async function toggleTop(row: any) {
  await announcementApi.update(row.id, { is_top: row.is_top })
}

onMounted(() => fetchData())
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
.view-meta { display: flex; align-items: center; gap: 12px; }
.view-time { color: #909399; font-size: 13px; }
.view-content { line-height: 1.8; white-space: pre-wrap; color: #303133; }
</style>
