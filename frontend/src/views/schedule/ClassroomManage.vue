<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-input v-model="query.keyword" placeholder="搜索教室/楼栋" clearable style="width: 220px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="query.room_type" placeholder="类型" clearable style="width: 140px" @change="fetchData">
          <el-option label="普通教室" value="normal" />
          <el-option label="实验室" value="lab" />
          <el-option label="机房" value="computer" />
          <el-option label="多媒体" value="multimedia" />
          <el-option label="其他" value="other" />
        </el-select>
        <el-select v-model="query.status" placeholder="状态" clearable style="width: 120px" @change="fetchData">
          <el-option label="可用" :value="1" />
          <el-option label="停用" :value="0" />
          <el-option label="维修" :value="2" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增教室</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="name" label="教室名称" min-width="140" />
        <el-table-column prop="campus" label="校区" width="120" />
        <el-table-column prop="building" label="楼栋" width="140" />
        <el-table-column prop="room_no" label="房间号" width="100" />
        <el-table-column prop="capacity" label="容量" width="90" />
        <el-table-column label="类型" width="110">
          <template #default="{ row }">{{ roomTypeText(row.room_type) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-popconfirm title="确定删除该教室？" @confirm="handleDelete(row.id)">
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑教室' : '新增教室'" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="86px">
        <el-form-item label="教室名称" prop="name">
          <el-input v-model="form.name" placeholder="如 逸夫楼 A101" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="校区">
              <el-input v-model="form.campus" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="楼栋">
              <el-input v-model="form.building" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="房间号">
              <el-input v-model="form.room_no" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="容量">
              <el-input-number v-model="form.capacity" :min="0" :max="1000" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="类型">
              <el-select v-model="form.room_type" style="width: 100%">
                <el-option label="普通教室" value="normal" />
                <el-option label="实验室" value="lab" />
                <el-option label="机房" value="computer" />
                <el-option label="多媒体" value="multimedia" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option label="可用" :value="1" />
                <el-option label="停用" :value="0" />
                <el-option label="维修" :value="2" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
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
import { classroomApi } from '@/api/schedule'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const editId = ref(0)

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  status: undefined as number | undefined,
  room_type: undefined as string | undefined,
})
const form = reactive({
  name: '',
  building: '',
  room_no: '',
  campus: '',
  capacity: 50,
  room_type: 'normal',
  status: 1,
  remark: '',
})

const rules = {
  name: [{ required: true, message: '请输入教室名称', trigger: 'blur' }],
}

function roomTypeText(type: string) {
  return ({ normal: '普通教室', lab: '实验室', computer: '机房', multimedia: '多媒体', other: '其他' } as any)[type] || type
}

function statusText(status: number) {
  return ({ 0: '停用', 1: '可用', 2: '维修' } as any)[status] || '-'
}

function statusType(status: number) {
  return status === 1 ? 'success' : status === 2 ? 'warning' : 'info'
}

async function fetchData() {
  loading.value = true
  try {
    const res = await classroomApi.list(query)
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
    building: row?.building || '',
    room_no: row?.room_no || '',
    campus: row?.campus || '',
    capacity: row?.capacity ?? 50,
    room_type: row?.room_type || 'normal',
    status: row?.status ?? 1,
    remark: row?.remark || '',
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (isEdit.value) await classroomApi.update(editId.value, form)
  else await classroomApi.create(form)
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await classroomApi.delete(id)
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
