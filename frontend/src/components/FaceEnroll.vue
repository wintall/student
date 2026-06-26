<template>
  <div class="face-enroll">
    <div v-if="!initialized" class="loading-state">
      <el-icon :size="32" color="#409eff"><Loading /></el-icon>
      <p>正在加载人脸识别模型...</p>
    </div>

    <div v-show="initialized" class="camera-area">
      <video
        ref="videoRef"
        class="enroll-video"
        autoplay
        muted
        playsinline
      ></video>

      <div class="enroll-status" :class="{ 'detecting': detecting, 'success': enrollSuccess }">
        <el-icon :size="20">
          <Loading v-if="detecting" />
          <Camera v-else />
        </el-icon>
        <span>{{ statusText }}</span>
      </div>

      <div class="enroll-controls">
        <el-button
          type="primary"
          :loading="detecting"
          :disabled="!initialized"
          @click="handleCapture"
        >
          {{ detecting ? '正在录入...' : '拍照录入' }}
        </el-button>
      </div>

      <div class="enroll-tips">
        <p>💡 请正对摄像头，保持面部清晰</p>
        <p>💡 请确保光线充足</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading, Camera } from '@element-plus/icons-vue'
import { initFaceApi, detectAndExtract } from '@/utils/faceDetection'
import { enrollFace } from '@/api/face'

const emit = defineEmits<{
  (e: 'success'): void
  (e: 'close'): void
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const initialized = ref(false)
const detecting = ref(false)
const enrollSuccess = ref(false)
const statusText = ref('点击拍照录入人脸')

let stream: MediaStream | null = null

const initCamera = async () => {
  try {
    await initFaceApi()

    initialized.value = true
    statusText.value = '正在初始化摄像头...'

    await nextTick()

    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: 'user' },
        width: { ideal: 640 },
        height: { ideal: 480 },
      },
      audio: false,
    })

    if (videoRef.value) {
      videoRef.value.srcObject = stream
      videoRef.value.addEventListener('loadedmetadata', () => {
        videoRef.value?.play().catch(() => {})
      })
    }

    statusText.value = '摄像头已就绪，请点击拍照'
  } catch (error: any) {
    console.error('摄像头初始化失败:', error.name, error.message)
    if (error.name === 'NotAllowedError') {
      ElMessage.error('摄像头权限被拒绝，请在浏览器设置中允许访问摄像头')
    } else if (error.name === 'NotFoundError') {
      ElMessage.error('未检测到摄像头设备')
    } else {
      ElMessage.error('无法访问摄像头: ' + (error.message || '未知错误'))
    }
  }
}

const handleCapture = async () => {
  if (!videoRef.value || !initialized.value) return

  detecting.value = true
  statusText.value = '正在检测人脸...'

  try {
    const result = await detectAndExtract(videoRef.value)

    if (!result.success) {
      statusText.value = result.message
      return
    }

    statusText.value = '正在上传人脸特征...'

    await enrollFace({
      feature_vector: result.featureVector!,
      confidence: result.confidence || 0.95,
    })

    statusText.value = '人脸录入成功！'
    enrollSuccess.value = true
    ElMessage.success('人脸录入成功')

    setTimeout(() => {
      emit('success')
    }, 1500)
  } catch (error: any) {
    statusText.value = error.message || '人脸录入失败，请重试'
    console.error('人脸录入失败:', error)
  } finally {
    detecting.value = false
  }
}

onMounted(() => {
  initCamera()
})

onBeforeUnmount(() => {
  if (stream) {
    stream.getTracks().forEach(track => track.stop())
  }
})
</script>

<style scoped>
.face-enroll {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px;
}

.camera-area {
  width: 100%;
}

.enroll-video {
  width: 100%;
  height: 320px;
  object-fit: cover;
  border-radius: 8px;
  background: #1f2937;
}

.enroll-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  margin-top: 16px;
  background: #f3f4f6;
  border-radius: 8px;
  color: #6b7280;
}

.enroll-status.detecting {
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
}

.enroll-status.success {
  background: rgba(67, 160, 71, 0.1);
  color: #43a047;
}

.enroll-controls {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.enroll-tips {
  margin-top: 16px;
  text-align: center;
}

.enroll-tips p {
  margin: 4px 0;
  font-size: 12px;
  color: #9ca3af;
}
</style>