<template>
  <div class="page-container">
    <el-card shadow="never" class="page-card">
      <template #header>
        <div class="card-header">
          <span>数据体检</span>
          <el-button type="primary" :loading="loading" @click="fetchData">
            <el-icon><Refresh /></el-icon>
            重新体检
          </el-button>
        </div>
      </template>

      <el-alert
        v-if="summary"
        :title="summary.total_issue_count ? `发现 ${summary.total_issue_count} 个异常，涉及 ${summary.issue_type_count} 类问题` : '当前范围内数据健康'"
        :type="summary.total_issue_count ? 'warning' : 'success'"
        show-icon
        :closable="false"
        class="summary-alert"
      />

      <el-table v-loading="loading" :data="issues" row-key="code" empty-text="暂无异常">
        <el-table-column label="严重级别" width="110">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'high' ? 'danger' : row.severity === 'medium' ? 'warning' : 'info'">
              {{ severityText(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="问题" min-width="220" />
        <el-table-column prop="count" label="数量" width="100" />
        <el-table-column label="样例" min-width="320">
          <template #default="{ row }">
            <div class="sample-list">
              <el-tag v-for="(sample, index) in row.samples" :key="index" type="info">
                {{ sampleText(sample) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDataHealth } from '@/api/operations'

const loading = ref(false)
const summary = ref<any>(null)
const issues = computed(() => summary.value?.issues || [])

function severityText(value: string) {
  return value === 'high' ? '高' : value === 'medium' ? '中' : '低'
}

function sampleText(sample: any) {
  return sample.name || sample.exam_name || sample.title || sample.student_no || sample.code || `ID ${sample.id || sample.exam_id || ''}`
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getDataHealth()
    summary.value = res.data
  } catch (e: any) {
    ElMessage.error(e?.message || '数据体检失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.page-container { padding: 20px; }
.page-card { border-radius: 8px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.summary-alert { margin-bottom: 16px; }
.sample-list { display: flex; flex-wrap: wrap; gap: 6px; }
</style>
