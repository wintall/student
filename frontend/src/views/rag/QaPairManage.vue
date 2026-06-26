<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <!-- 搜索栏 -->
      <div class="search-bar">
        <el-input v-model="query.keyword" placeholder="搜索问题/答案/关键词" clearable style="width: 260px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="query.category" placeholder="分类" clearable style="width: 140px" @change="fetchData">
          <el-option label="通用" value="通用" />
          <el-option label="西游记" value="xiyouji" />
          <el-option label="三国演义" value="sanguoyanyi" />
          <el-option label="水浒传" value="shuihuzhuan" />
          <el-option label="红楼梦" value="hongloumeng" />
        </el-select>
        <el-select v-model="query.status" placeholder="状态" clearable style="width: 120px" @change="fetchData">
          <el-option label="启用" :value="1" />
          <el-option label="禁用" :value="0" />
        </el-select>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
        <el-button type="success" @click="openDialog()"><el-icon><Plus /></el-icon> 新增问答对</el-button>
      </div>

      <!-- 表格 -->
      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="分类" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ getCategoryName(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="question" label="问题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="question_variants" label="问题变体" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.question_variants" class="variants-text">{{ row.question_variants }}</span>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="answer" label="答案" min-width="250" show-overflow-tooltip />
        <el-table-column prop="keywords" label="关键词" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.keywords" class="keywords-text">{{ row.keywords }}</span>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="hit_count" label="命中次数" width="90" align="center">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.hit_count || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.status" :active-value="1" :inactive-value="0" @change="toggleStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button link type="info" @click="testMatch(row)">测试</el-button>
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
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑问答对' : '新增问答对'" width="680px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="分类" prop="category">
          <el-select v-model="form.category" placeholder="选择分类" style="width: 100%">
            <el-option label="通用" value="通用" />
            <el-option label="西游记" value="xiyouji" />
            <el-option label="三国演义" value="sanguoyanyi" />
            <el-option label="水浒传" value="shuihuzhuan" />
            <el-option label="红楼梦" value="hongloumeng" />
          </el-select>
        </el-form-item>
        <el-form-item label="标准问题" prop="question">
          <el-input v-model="form.question" placeholder="请输入标准问题，如：孙悟空是谁？" />
        </el-form-item>
        <el-form-item label="问题变体" prop="question_variants">
          <el-input
            v-model="form.question_variants"
            type="textarea"
            :rows="2"
            placeholder="问题变体，用分号(;)分隔，如：齐天大圣是谁？;孙行者是谁？"
          />
        </el-form-item>
        <el-form-item label="答案" prop="answer">
          <el-input v-model="form.answer" type="textarea" :rows="4" placeholder="请输入标准答案" />
        </el-form-item>
        <el-form-item label="关键词" prop="keywords">
          <el-input v-model="form.keywords" placeholder="关键词，用逗号分隔，如：孙悟空,齐天大圣,孙行者" />
        </el-form-item>
        <el-form-item label="来源/出处" prop="source">
          <el-input v-model="form.source" placeholder="如：西游记第1回" />
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

    <!-- 测试匹配对话框 -->
    <el-dialog v-model="testDialogVisible" title="测试问答对匹配" width="500px" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="测试问题">
          <el-input v-model="testQuestion" placeholder="输入一个问题，测试是否能匹配到该问答对" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="testLoading" @click="doTestMatch">测试匹配</el-button>
        </el-form-item>
      </el-form>
      <div v-if="testResult" class="test-result">
        <el-divider>匹配结果</el-divider>
        <div v-if="testResult.length > 0">
          <div v-for="(m, idx) in testResult" :key="idx" class="match-item">
            <div class="match-score">
              <el-tag :type="m.score >= 0.85 ? 'success' : m.score >= 0.6 ? 'warning' : 'info'">
                匹配度: {{ (m.score * 100).toFixed(0) }}%
              </el-tag>
            </div>
            <div class="match-q"><strong>匹配的问题:</strong> {{ m.question }}</div>
            <div class="match-answer"><strong>答案:</strong> {{ m.answer }}</div>
          </div>
        </div>
        <el-empty v-else description="未匹配到任何问答对" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listQaPairs, createQaPair, updateQaPair, deleteQaPair, matchQaPairs, type QaPair } from '@/api/rag-qa'

const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const testDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const tableData = ref<QaPair[]>([])
const total = ref(0)
const testLoading = ref(false)
const testQuestion = ref('')
const testResult = ref<any[]>([])
const currentRow = ref<QaPair | null>(null)

const query = reactive({
  keyword: '',
  category: '',
  status: null as number | null,
  page: 1,
  page_size: 20,
})

const form = reactive({
  id: null as number | null,
  category: '通用',
  question: '',
  question_variants: '',
  answer: '',
  keywords: '',
  source: '',
  status: 1,
})

const rules = {
  question: [{ required: true, message: '请输入标准问题', trigger: 'blur' }],
  answer: [{ required: true, message: '请输入答案', trigger: 'blur' }],
}

const getCategoryName = (cat: string) => {
  const map: Record<string, string> = {
    'xiyouji': '西游记',
    'sanguoyanyi': '三国演义',
    'shuihuzhuan': '水浒传',
    'hongloumeng': '红楼梦',
    '通用': '通用',
  }
  return map[cat] || cat || '通用'
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await listQaPairs({
      page: query.page,
      page_size: query.page_size,
      keyword: query.keyword || undefined,
      category: query.category || undefined,
      status: query.status ?? undefined,
    })
    tableData.value = res.data.items
    total.value = res.data.total
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const openDialog = (row?: QaPair) => {
  if (row) {
    isEdit.value = true
    Object.assign(form, {
      id: row.id,
      category: row.category || '通用',
      question: row.question,
      question_variants: row.question_variants || '',
      answer: row.answer,
      keywords: row.keywords || '',
      source: row.source || '',
      status: row.status,
    })
  } else {
    isEdit.value = false
    Object.assign(form, {
      id: null,
      category: '通用',
      question: '',
      question_variants: '',
      answer: '',
      keywords: '',
      source: '',
      status: 1,
    })
  }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate()
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateQaPair(form.id!, form)
      ElMessage.success('更新成功')
    } else {
      await createQaPair(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch {
    ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await deleteQaPair(id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    ElMessage.error('删除失败')
  }
}

const toggleStatus = async (row: QaPair) => {
  try {
    await updateQaPair(row.id, { status: row.status })
    ElMessage.success(row.status === 1 ? '已启用' : '已禁用')
  } catch {
    row.status = row.status === 1 ? 0 : 1
    ElMessage.error('操作失败')
  }
}

const testMatch = (row: QaPair) => {
  currentRow.value = row
  testQuestion.value = row.question
  testResult.value = []
  testDialogVisible.value = true
}

const doTestMatch = async () => {
  if (!testQuestion.value.trim()) {
    ElMessage.warning('请输入测试问题')
    return
  }
  testLoading.value = true
  try {
    const res = await matchQaPairs(testQuestion.value, currentRow.value?.category || undefined, 3)
    testResult.value = res.data.matches || []
    if (testResult.value.length === 0) {
      ElMessage.info('未匹配到问答对')
    }
  } catch {
    ElMessage.error('测试失败')
  } finally {
    testLoading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.variants-text,
.keywords-text {
  font-size: 12px;
  color: #909399;
}
.text-gray {
  color: #c0c4cc;
}
.test-result {
  margin-top: 16px;
}
.match-item {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 12px;
}
.match-score {
  margin-bottom: 8px;
}
.match-q,
.match-answer {
  font-size: 13px;
  margin-top: 4px;
}
</style>
