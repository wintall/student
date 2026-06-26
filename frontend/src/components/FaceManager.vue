<template>
  <div class="face-manager">
    <el-card title="人脸管理" class="manager-card">
      <div v-if="!template" class="no-face-state">
        <div class="no-face-icon">
          <el-icon :size="64" color="#9ca3af"><User /></el-icon>
        </div>
        <p>您尚未录入人脸信息</p>
        <el-button type="primary" @click="showEnroll = true">录入人脸</el-button>
      </div>

      <div v-else class="has-face-state">
        <div class="face-info">
          <div class="face-icon">
            <el-icon :size="64" color="#409eff"><CircleCheck /></el-icon>
          </div>
          <div class="face-details">
            <p class="face-title">人脸已录入</p>
            <p class="face-meta">录入时间：{{ formatTime(template.created_at) }}</p>
            <p class="face-meta">置信度：{{ (template.confidence * 100).toFixed(1) }}%</p>
          </div>
        </div>

        <el-button type="danger" plain @click="handleDelete">删除人脸</el-button>
        <el-button type="primary" @click="showEnroll = true">重新录入</el-button>
      </div>
    </el-card>

    <el-dialog
      v-model="showEnroll"
      title="录入人脸"
      width="520px"
      :close-on-click-modal="false"
      @close="handleEnrollClose"
    >
      <FaceEnroll @success="handleEnrollSuccess" @close="showEnroll = false" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, CircleCheck } from '@element-plus/icons-vue'
import { getFaceTemplate, deleteFace } from '@/api/face'
import FaceEnroll from './FaceEnroll.vue'

interface FaceTemplate {
  id: number
  confidence: number
  status: number
  created_at: string
}

const template = ref<FaceTemplate | null>(null)
const showEnroll = ref(false)

const loadTemplate = async () => {
  try {
    const response = await getFaceTemplate()
    if (response.data) {
      template.value = response.data
    }
  } catch (error) {
    console.error('获取人脸模板失败:', error)
  }
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm('确定要删除人脸模板吗？删除后将无法使用人脸登录', '确认删除', {
      type: 'warning',
    })

    await deleteFace()
    template.value = null
    ElMessage.success('人脸模板已删除')
  } catch (error) {
    // 用户取消删除
  }
}

const handleEnrollSuccess = () => {
  showEnroll.value = false
  loadTemplate()
}

const handleEnrollClose = () => {
  showEnroll.value = false
}

const formatTime = (timeStr: string) => {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadTemplate()
})
</script>

<style scoped>
.face-manager {
  padding: 20px;
}

.manager-card {
  max-width: 400px;
  margin: 0 auto;
}

.no-face-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 0;
}

.no-face-icon {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.no-face-state p {
  color: #6b7280;
  margin-bottom: 20px;
}

.has-face-state {
  padding: 20px 0;
}

.face-info {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
}

.face-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: #dcfce7;
  display: flex;
  align-items: center;
  justify-content: center;
}

.face-details {
  flex: 1;
}

.face-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.face-meta {
  font-size: 14px;
  color: #6b7280;
  margin: 4px 0;
}

.has-face-state .el-button {
  margin-right: 12px;
}
</style>