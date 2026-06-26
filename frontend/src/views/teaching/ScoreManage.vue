<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-select v-model="query.exam_id" placeholder="选择考试" clearable style="width: 220px" @change="fetchData">
          <el-option v-for="e in examOptions" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button v-permission="'teaching:score:create'" type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 录入成绩</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="学生" width="120">
          <template #default="{ row }">{{ row.student?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="考试" min-width="150">
          <template #default="{ row }">{{ row.exam?.name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="score" label="得分" width="100">
          <template #default="{ row }">
            <span :style="{ color: row.score < 60 ? '#f56c6c' : row.score >= 90 ? '#67c23a' : '#409eff', fontWeight: 600 }">
              {{ row.score }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="total_score" label="满分" width="80" />
        <el-table-column label="等级" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.score >= 90" type="success" size="small">优秀</el-tag>
            <el-tag v-else-if="row.score >= 80" type="primary" size="small">良好</el-tag>
            <el-tag v-else-if="row.score >= 70" type="info" size="small">中等</el-tag>
            <el-tag v-else-if="row.score >= 60" type="warning" size="small">及格</el-tag>
            <el-tag v-else type="danger" size="small">不及格</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="canManage" label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="'teaching:score:update'" link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-popconfirm v-if="hasPermission('teaching:score:delete')" title="确定删除？" @confirm="handleDelete(row.id)">
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑成绩' : '录入成绩'" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="学生" prop="student_id">
          <el-select v-model="form.student_id" placeholder="选择学生" style="width: 100%">
            <el-option v-for="s in studentOptions" :key="s.id" :label="`${s.name} (${s.student_no})`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="考试" prop="exam_id">
          <el-select v-model="form.exam_id" placeholder="选择考试" style="width: 100%">
            <el-option v-for="e in examOptions" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="得分" prop="score">
          <el-input-number v-model="form.score" :min="0" :max="1000" :precision="1" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
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
import { scoreApi, examApi, studentApi } from '@/api/common'
import { hasPermission } from '@/utils/permission'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<any[]>([])
const total = ref(0)
const examOptions = ref<any[]>([])
const studentOptions = ref<any[]>([])
const editId = ref(0)
const canManage = hasPermission(['teaching:score:update', 'teaching:score:delete'])

const query = reactive({ page: 1, page_size: 10, exam_id: undefined as number | undefined })

const form = reactive({
  student_id: null as number | null, exam_id: null as number | null,
  score: 0, remark: '',
})
const rules = {
  student_id: [{ required: true, message: '请选择学生', trigger: 'change' }],
  exam_id: [{ required: true, message: '请选择考试', trigger: 'change' }],
  score: [{ required: true, message: '请输入得分', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await scoreApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally { loading.value = false }
}

async function fetchOptions() {
  const [examRes, stuRes] = await Promise.all([
    examApi.list({ page: 1, page_size: 100 }),
    studentApi.list({ page: 1, page_size: 100 }),
  ])
  examOptions.value = examRes.data.items || examRes.data
  studentOptions.value = stuRes.data.items || stuRes.data
}

function openDialog(row?: any) {
  isEdit.value = !!row
  editId.value = row?.id || 0
  Object.assign(form, {
    student_id: row?.student_id || null, exam_id: row?.exam_id || null,
    score: row?.score ?? 0, remark: row?.remark || '',
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  if (isEdit.value) {
    await scoreApi.update(editId.value, form)
  } else {
    await scoreApi.create(form)
  }
  ElMessage.success('操作成功')
  dialogVisible.value = false
  fetchData()
}

async function handleDelete(id: number) {
  await scoreApi.delete(id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(() => { fetchData(); fetchOptions() })
</script>

<style scoped>
.page-card { border-radius: 12px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
