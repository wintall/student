<template>
  <div>
    <div class="email-toolbar">
      <h2 style="margin: 0;">✏️ 写邮件</h2>
    </div>

    <el-card shadow="hover" style="border-radius: 10px;">
      <el-form :model="form" label-width="80px">
        <el-form-item label="收件人" required>
          <el-autocomplete
            v-model="form.recipient_email"
            :fetch-suggestions="fetchSuggestions"
            placeholder="输入姓名/邮箱；内部用户可直接选择，外部邮箱也支持"
            clearable
            style="width: 100%"
            value-key="email"
          >
            <template #default="{ item }">
              <div class="suggestion-item">
                <span class="suggestion-name">{{ item.name }}</span>
                <span class="suggestion-role">{{ item.role }}</span>
                <span class="suggestion-email">{{ item.email }}</span>
              </div>
            </template>
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-autocomplete>
        </el-form-item>

        <el-form-item label="主题" required>
          <el-input v-model="form.subject" placeholder="邮件主题" maxlength="200" />
        </el-form-item>

        <el-form-item label="正文" required>
          <div
            class="drop-zone"
            :class="{ 'drop-zone-active': dragOver }"
            @dragover.prevent="dragOver = true"
            @dragleave="dragOver = false"
            @drop.prevent="handleDrop"
          >
            <el-input
              v-model="form.body"
              type="textarea"
              :rows="12"
              placeholder="请输入邮件正文...拖拽文件到此处可直接添加附件"
              resize="vertical"
            />
          </div>
        </el-form-item>

        <el-form-item label="附件">
          <div>
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
              :file-list="fileList"
              multiple
              drag
              :limit="10"
              :max-size="50"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">点击或拖拽文件到此处上传<em>（单个文件 ≤ 50MB，最多 10 个）</em></div>
            </el-upload>
            <div v-if="fileList.length" class="file-tips">
              <el-tag v-for="f in fileList" :key="f.uid" style="margin: 4px 4px 0 0;" closable @close="removeFile(f)">
                {{ f.name }} ({{ formatSize(f.size) }})
              </el-tag>
            </div>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="sending" @click="handleSend">
            <el-icon><Promotion /></el-icon> 发送
          </el-button>
          <el-button @click="handleClear">清空</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { sendEmail, suggestUsers } from '@/api/email'

const form = reactive({
  recipient_email: '',
  subject: '',
  body: '',
})

const fileList = ref<UploadFile[]>([])
const sending = ref(false)
const dragOver = ref(false)

async function fetchSuggestions(keyword: string, cb: (list: any[]) => void) {
  if (!keyword || keyword.length < 1) {
    cb([])
    return
  }
  try {
    const res = await suggestUsers(keyword)
    const users = res.data?.items || res.data || []
    cb(
      users.map((u: any) => ({
        email: u.email,
        name: u.name || u.username || u.email,
        role: u.role || u.role_name || '',
        // el-autocomplete 需要 value 字段
        value: `${u.name || u.username || ''} (${u.email})`,
      }))
    )
  } catch (e) {
    cb([])
  }
}

function handleFileChange(uploadFile: UploadFile) {
  if (uploadFile.size && uploadFile.size > 50 * 1024 * 1024) {
    ElMessage.warning(`${uploadFile.name} 超过 50MB 限制`)
    return
  }
}

function handleFileRemove(file: UploadFile) {
  fileList.value = fileList.value.filter((f) => f.uid !== file.uid)
}

function removeFile(file: UploadFile) {
  fileList.value = fileList.value.filter((f) => f.uid !== file.uid)
}

function handleDrop(e: DragEvent) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (!files || !files.length) return
  Array.from(files).forEach((rawFile) => {
    if (rawFile.size > 50 * 1024 * 1024) {
      ElMessage.warning(`${rawFile.name} 超过 50MB 限制`)
      return
    }
    const uploadFile: UploadFile = {
      uid: Date.now() + Math.floor(Math.random() * 1000),
      name: rawFile.name,
      size: rawFile.size,
      raw: rawFile as any,
      status: 'ready',
      percentage: 0,
    }
    fileList.value.push(uploadFile)
  })
}

function formatSize(size?: number) {
  if (!size) return '0B'
  if (size < 1024) return size + 'B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + 'KB'
  return (size / 1024 / 1024).toFixed(2) + 'MB'
}

async function handleSend() {
  if (!form.recipient_email.trim()) {
    ElMessage.warning('请填写收件人邮箱')
    return
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(form.recipient_email.trim())) {
    ElMessage.warning('邮箱格式不正确')
    return
  }
  if (!form.subject.trim()) {
    ElMessage.warning('请填写邮件主题')
    return
  }
  if (!form.body.trim()) {
    ElMessage.warning('请填写邮件正文')
    return
  }

  sending.value = true
  try {
    const files = fileList.value
      .map((f) => f.raw as File)
      .filter(Boolean)
    await sendEmail({
      recipient_email: form.recipient_email.trim(),
      subject: form.subject.trim(),
      body: form.body,
      files: files.length ? files : undefined,
    })
    ElMessage.success('邮件发送成功')
    handleClear()
  } catch (e: any) {
    ElMessage.error(e?.message || '发送失败')
  } finally {
    sending.value = false
  }
}

function handleClear() {
  form.recipient_email = ''
  form.subject = ''
  form.body = ''
  fileList.value = []
}
</script>

<style scoped>
.email-toolbar { margin-bottom: 16px; }

.drop-zone {
  padding: 4px;
  border-radius: 8px;
  transition: all 0.2s;
}

.drop-zone-active {
  background: rgba(64, 158, 255, 0.08);
  outline: 2px dashed #409eff;
  outline-offset: -2px;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}

.suggestion-name {
  font-weight: 600;
  color: #303133;
  min-width: 80px;
}

.suggestion-role {
  color: #409eff;
  background: rgba(64, 158, 255, 0.12);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  min-width: 50px;
  text-align: center;
}

.suggestion-email {
  color: #909399;
  font-size: 12px;
  margin-left: auto;
}

.file-tips {
  margin-top: 8px;
}
</style>
