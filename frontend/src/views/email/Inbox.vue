<template>
  <div>
    <div class="email-toolbar">
      <h2 style="margin: 0;">📥 收件箱</h2>
      <el-input
        v-model="keyword"
        placeholder="搜索主题/发件人"
        aria-label="搜索邮件"
        clearable
        style="width: 240px"
        @keyup.enter="loadList"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <el-card v-loading="loading" shadow="hover" style="border-radius: 10px;">
      <el-table :data="list" @row-click="openDetail" style="width: 100%" empty-text="暂无邮件">
        <el-table-column width="50" label="">
          <template #default="{ row }">
            <span v-if="!row.is_read" class="unread-dot" aria-label="未读"></span>
          </template>
        </el-table-column>
        <el-table-column label="发件人" prop="sender_name" width="180" />
        <el-table-column label="主题" prop="subject" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span :style="{ fontWeight: row.is_read ? 'normal' : '600' }">{{ row.subject }}</span>
          </template>
        </el-table-column>
        <el-table-column label="附件" width="80">
          <template #default="{ row }">
            <el-icon v-if="row.attachments && row.attachments.length" aria-label="有附件"><Paperclip /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="时间" prop="sent_at" width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" text type="danger" @click.stop="handleDelete(row)" aria-label="删除邮件">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          :total="total"
          background
          @current-change="loadList"
          @size-change="loadList"
        />
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" :title="currentDetail?.subject || '邮件详情'" width="640px" top="8vh" destroy-on-close>
      <div v-if="currentDetail">
        <div class="detail-meta">
          <div><strong>发件人：</strong>{{ currentDetail.sender_name }} &lt;{{ currentDetail.sender_email || '-' }}&gt;</div>
          <div class="detail-date">{{ currentDetail.sent_at || currentDetail.created_at || '' }}</div>
        </div>
        <div class="detail-body" v-html="safeBody(currentDetail.body)"></div>

        <div v-if="currentDetail.attachments && currentDetail.attachments.length" class="detail-attachments">
          <h4>📎 附件</h4>
          <el-space wrap>
            <el-button
              v-for="att in currentDetail.attachments"
              :key="att.id"
              @click="downloadAttachment(att)"
            >
              <el-icon><Download /></el-icon>
              {{ att.original_filename || att.file_name || '下载' }}
            </el-button>
          </el-space>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getInbox, getEmailDetail, deleteEmail } from '@/api/email'

const list = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const keyword = ref('')

const detailVisible = ref(false)
const currentDetail = ref<any>(null)

async function loadList() {
  loading.value = true
  try {
    const res = await getInbox({ page: page.value, page_size: pageSize.value, keyword: keyword.value })
    list.value = res.data?.items || res.data?.data || []
    total.value = res.data?.total || 0
  } catch (e) {
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function openDetail(row: any) {
  try {
    const res = await getEmailDetail(row.id)
    currentDetail.value = res.data || row
    detailVisible.value = true
    if (!row.is_read) row.is_read = true
  } catch (e) {
    currentDetail.value = row
    detailVisible.value = true
  }
}

function safeBody(body: string) {
  if (!body) return ''
  // 简单 XSS 防御，防止非文本内容注入
  if (body.includes('<')) return body
  return body.replace(/\n/g, '<br>')
}

function downloadAttachment(att: any) {
  const token = localStorage.getItem('access_token') || ''
  const baseUrl = '/api/v1/emails/attachments'
  const url = att.download_url || `${baseUrl}/${att.id}/download?access_token=${token}`
  window.open(url, '_blank')
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除邮件「${row.subject}」吗？`, '提示', { type: 'warning' })
    await deleteEmail(row.id, true)
    ElMessage.success('已删除')
    loadList()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.message || '删除失败')
  }
}

onMounted(loadList)
</script>

<style scoped>
.email-toolbar {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;
}

.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }

.unread-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #409eff;
  vertical-align: middle;
}

.detail-meta {
  display: flex; justify-content: space-between; padding-bottom: 12px; border-bottom: 1px solid #ebeef5;
  color: #606266; font-size: 14px; margin-bottom: 18px;
}
.detail-date { color: #909399; }

.detail-body {
  font-size: 14px; line-height: 1.8; min-height: 200px;
  white-space: pre-wrap; word-break: break-word; padding: 10px 0;
}

.detail-attachments { margin-top: 20px; padding-top: 14px; border-top: 1px solid #ebeef5; }
.detail-attachments h4 { margin: 0 0 12px; font-size: 14px; color: #303133; font-weight: 600; }
</style>
