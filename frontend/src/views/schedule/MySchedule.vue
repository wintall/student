<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <div class="search-bar">
        <el-select v-model="query.term_id" placeholder="学期" clearable filterable style="width: 240px" @change="fetchData">
          <el-option v-for="t in termOptions" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-input v-model="query.keyword" placeholder="搜索课程" clearable style="width: 200px" @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="fetchData"><el-icon><Search /></el-icon> 搜索</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
        <el-table-column label="星期" width="90">
          <template #default="{ row }">{{ weekdayText(row.weekday) }}</template>
        </el-table-column>
        <el-table-column label="节次" width="120">
          <template #default="{ row }">第{{ row.start_section }}-{{ row.end_section }}节</template>
        </el-table-column>
        <el-table-column prop="course_name" label="课程" min-width="160" />
        <el-table-column prop="clazz_name" label="班级" min-width="130" />
        <el-table-column prop="teacher_name" label="教师" width="110" />
        <el-table-column prop="classroom_name" label="教室" width="130" />
        <el-table-column label="周次" width="150">
          <template #default="{ row }">
            {{ row.start_week }}-{{ row.end_week }}周 {{ weekTypeText(row.week_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
      </el-table>

      <div class="pagination-wrap">
        <el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size"
          :total="total" :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchData" @current-change="fetchData" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { courseScheduleApi, termApi } from '@/api/schedule'

const weekdays = [
  { label: '周一', value: 1 },
  { label: '周二', value: 2 },
  { label: '周三', value: 3 },
  { label: '周四', value: 4 },
  { label: '周五', value: 5 },
  { label: '周六', value: 6 },
  { label: '周日', value: 7 },
]

const loading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const termOptions = ref<any[]>([])

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  term_id: undefined as number | undefined,
})

function weekdayText(value: number) {
  return weekdays.find(item => item.value === value)?.label || '-'
}

function weekTypeText(value: string) {
  return ({ all: '每周', odd: '单周', even: '双周' } as any)[value] || value
}

async function fetchTerms() {
  const res = await termApi.list({ page: 1, page_size: 100, status: 1 })
  termOptions.value = res.data.items || []
  const current = termOptions.value.find(item => item.is_current)
  if (current && !query.term_id) query.term_id = current.id
}

async function fetchData() {
  loading.value = true
  try {
    const res = await courseScheduleApi.my(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    tableData.value = []
    total.value = 0
    if (String(e?.message || '').includes('未关联')) {
      ElMessage.info('当前账号未关联学生或教师信息，暂无个人课表')
    }
  } finally {
    loading.value = false
  }
}

fetchTerms().then(fetchData)
</script>

<style scoped>
.page-card { border-radius: 8px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
