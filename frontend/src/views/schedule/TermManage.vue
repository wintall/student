<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-input v-model="query.keyword" placeholder="搜索学期/学年" clearable style="width: 220px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="query.status" placeholder="状态" clearable style="width: 120px" @change="fetchData">
          <el-option label="启用" :value="1" />
          <el-option label="停用" :value="0" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增学期</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="name" label="学期名称" min-width="180" />
        <el-table-column prop="academic_year" label="学年" width="130" />
        <el-table-column prop="semester" label="学期" width="80" />
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120" />
        <el-table-column prop="week_count" label="教学周" width="90" />
        <el-table-column label="当前" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_current" type="success" size="small">当前</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-popconfirm title="确定删除该学期？" @confirm="handleDelete(row.id)">
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑学期' : '新增学期'" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="92px">
        <el-form-item label="学期名称" prop="name">
          <el-input v-model="form.name" placeholder="如 2025-2026 学年第一学期" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="学年" prop="academic_year">
              <el-input v-model="form.academic_year" placeholder="2025-2026" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="学期" prop="semester">
              <el-input-number v-model="form.semester" :min="1" :max="3" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="起止日期" prop="date_range">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="教学周" prop="week_count">
              <el-input-number v-model="form.week_count" :min="1" :max="60" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option label="启用" :value="1" />
                <el-option label="停用" :value="0" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="当前学期">
          <el-switch v-model="form.is_current" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" />
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
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { termApi } from '@/api/schedule'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const editId = ref(0)
const dateRange = ref<string[]>([])

const query = reactive({ page: 1, page_size: 10, keyword: '', status: undefined as number | undefined })
const form = reactive({
  name: '',
  academic_year: '',
  semester: 1,
  start_date: '',
  end_date: '',
  week_count: 20,
  is_current: false,
  status: 1,
  remark: '',
})

const rules = {
  name: [{ required: true, message: '请输入学期名称', trigger: 'blur' }],
  academic_year: [{ required: true, message: '请输入学年', trigger: 'blur' }],
  semester: [{ required: true, message: '请选择学期', trigger: 'change' }],
  week_count: [{ required: true, message: '请输入教学周数', trigger: 'change' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await termApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function openDialog(row?: any) {
  isEdit.value = !!row
  editId.value = row?.id || 0
  Object.assign(form, {
    name: row?.name || '',
    academic_year: row?.academic_year || '',
    semester: row?.semester ?? 1,
    start_date: row?.start_date || '',
    end_date: row?.end_date || '',
    week_count: row?.week_count ?? 20,
    is_current: !!row?.is_current,
    status: row?.status ?? 1,
    remark: row?.remark || '',
  })
  dateRange.value = row?.start_date && row?.end_date ? [row.start_date, row.end_date] : []
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (!dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请选择起止日期')
    return
  }
  const payload = { ...form, start_date: dateRange.value[0], end_date: dateRange.value[1] }
  if (isEdit.value) await termApi.update(editId.value, payload)
  else await termApi.create(payload)
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await termApi.delete(id)
  ElMessage.success('删除成功')
  fetchData()
}

fetchData()
</script>

<style scoped>
.page-card { border-radius: 8px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
