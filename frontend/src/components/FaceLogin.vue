<template>
  <div class="face-login-container">
    <div v-if="!initialized" class="loading-state">
      <el-icon :size="32" color="#409eff"><Loading /></el-icon>
      <p>正在加载人脸识别模型...</p>
    </div>

    <div v-show="initialized" class="camera-container">
      <video
        ref="videoRef"
        class="camera-feed"
        autoplay
        muted
        playsinline
      ></video>

      <div class="camera-status" :class="{ 'detecting': detecting, 'success': detectSuccess, 'error': detectError }">
        <el-icon :size="20">
          <Loading v-if="detecting" />
          <CircleCheck v-else-if="detectSuccess" />
          <CircleClose v-else-if="detectError" />
          <Camera v-else />
        </el-icon>
        <span>{{ statusText }}</span>
      </div>

      <div class="camera-controls">
        <el-button
          type="primary"
          size="large"
          :loading="detecting"
          :disabled="!initialized"
          class="detect-btn"
          @click="handleDetect"
        >
          {{ detecting ? '识别中...' : '开始人脸识别' }}
        </el-button>

        <el-button
          size="large"
          @click="handleClose"
        >
          返回密码登录
        </el-button>
      </div>

      <div class="camera-tips">
        <p>💡 请确保光线充足，正对摄像头</p>
        <p>💡 保持面部在画面中央</p>
        <p>💡 请摘掉帽子和口罩</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading, CircleCheck, CircleClose, Camera } from '@element-plus/icons-vue'
import { initFaceApi, detectAndExtract } from '@/utils/faceDetection'
import { faceLogin } from '@/api/face'
import { useUserStore } from '@/stores/user'

const emit = defineEmits<{
  (e: 'login-success'): void
  (e: 'close'): void
}>()

const userStore = useUserStore()

const videoRef = ref<HTMLVideoElement | null>(null)
const initialized = ref(false)
const detecting = ref(false)
const detectSuccess = ref(false)
const detectError = ref(false)
const statusText = ref('请点击开始人脸识别')

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

    statusText.value = '摄像头已就绪'
  } catch (error: any) {
    console.error('摄像头初始化失败:', error.name, error.message, error.constraint)
    if (error.name === 'NotAllowedError') {
      ElMessage.error('摄像头权限被拒绝，请在浏览器设置中允许访问摄像头')
    } else if (error.name === 'NotFoundError') {
      ElMessage.error('未检测到摄像头设备')
    } else if (error.name === 'OverconstrainedError') {
      ElMessage.error('摄像头配置参数不支持，请尝试刷新页面')
    } else {
      ElMessage.error('无法访问摄像头: ' + (error.message || '未知错误'))
    }
    statusText.value = '无法访问摄像头'
  }
}

const handleDetect = async () => {
  if (!videoRef.value || !initialized.value) return

  detecting.value = true
  detectSuccess.value = false
  detectError.value = false
  statusText.value = '正在检测人脸...'

  try {
    const result = await detectAndExtract(videoRef.value)

    if (!result.success) {
      detectError.value = true
      statusText.value = result.message
      return
    }

    statusText.value = '人脸特征提取成功，正在比对...'

    const response = await faceLogin({
      feature_vector: result.featureVector!,
      device_info: navigator.userAgent,
    })

    if (response.data && response.data.access_token) {
      userStore.setToken(response.data.access_token, response.data.refresh_token)
      if (response.data.user) {
        userStore.setUserInfo(response.data.user)
      }

      await userStore.fetchMenus()

      detectSuccess.value = true
      statusText.value = '人脸识别成功！'
      ElMessage.success('人脸识别登录成功')

      setTimeout(() => {
        emit('login-success')
      }, 1000)
    }
  } catch (error: any) {
    detectError.value = true
    statusText.value = error.message || '人脸识别失败，请重试'
    console.error('人脸登录失败:', error)
  } finally {
    detecting.value = false
  }
}

const handleClose = () => {
  if (stream) {
    stream.getTracks().forEach(track => track.stop())
  }
  emit('close')
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
.face-login-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: #6b7280;
}

.camera-container {
  position: relative;
  width: 100%;
  max-width: 480px;
}

.camera-feed {
  width: 100%;
  height: 360px;
  object-fit: cover;
  border-radius: 12px;
  background: #1f2937;
}

.camera-status {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.7);
  border-radius: 20px;
  color: #fff;
  font-size: 14px;
}

.camera-status.detecting {
  background: rgba(64, 158, 255, 0.9);
}

.camera-status.success {
  background: rgba(67, 160, 71, 0.9);
}

.camera-status.error {
  background: rgba(239, 68, 68, 0.9);
}

.camera-controls {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.detect-btn {
  flex: 1;
}

.camera-tips {
  margin-top: 16px;
  padding: 12px;
  background: #f3f4f6;
  border-radius: 8px;
}

.camera-tips p {
  margin: 4px 0;
  font-size: 12px;
  color: #6b7280;
}
</style>