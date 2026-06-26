<template>
  <div class="login-container">
    <div class="login-bg">
      <div class="bg-circle bg-circle-1"></div>
      <div class="bg-circle bg-circle-2"></div>
      <div class="bg-circle bg-circle-3"></div>
    </div>
    <div class="login-card">
      <div class="login-header">
        <div class="logo-icon">
          <el-icon :size="40" color="#409eff"><School /></el-icon>
        </div>
        <h1>学生信息管理系统</h1>
        <p class="subtitle">Student Information Management System</p>
      </div>

      <div class="login-tabs">
        <span 
          class="tab-item" 
          :class="{ active: loginMode === 'password' }"
          @click="loginMode = 'password'"
        >密码登录</span>
        <span 
          class="tab-item" 
          :class="{ active: loginMode === 'face' }"
          @click="loginMode = 'face'"
        >人脸登录</span>
      </div>

      <el-form
        v-if="loginMode === 'password'"
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-form"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="account">
          <el-input
            v-model="form.account"
            placeholder="用户名 / 手机号 / 身份证号"
            :prefix-icon="User"
            size="large"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            size="large"
            show-password
            @keyup.enter="handleLogin"
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="login-btn"
            @click="handleLogin"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <FaceLogin 
        v-else 
        @login-success="handleFaceLoginSuccess" 
        @close="loginMode = 'password'" 
      />

      <div class="login-footer">
        <span>管理员: admin / admin123</span>
        <span class="forget-link" @click="openResetDialog">忘记密码？</span>
      </div>
    </div>
    <div class="copyright">
      &copy; 2026 学生信息管理系统 v1.0.0
    </div>

    <!-- 密码重置弹窗 -->
    <el-dialog
      v-model="resetVisible"
      title="重置密码"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="resetFormRef"
        :model="resetForm"
        :rules="resetRules"
        label-width="90px"
      >
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="resetForm.email" placeholder="请输入邮箱" />
          <el-button
            v-if="codeCountdown <= 0"
            type="primary"
            link
            :loading="resetCodeSending"
            class="send-code-btn"
            @click="handleSendCode"
          >发送验证码</el-button>
          <span v-else class="countdown-text">{{ codeCountdown }}s 后重发</span>
        </el-form-item>
        <el-form-item label="验证码" prop="code">
          <el-input v-model="resetForm.code" placeholder="请输入验证码" maxlength="6" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="resetForm.new_password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="resetForm.confirm_password" type="password" show-password placeholder="请再次输入" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetSubmitting" @click="handleResetPassword">
          确认重置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, School } from '@element-plus/icons-vue'
import { login, sendResetCode, resetPassword } from '@/api/auth'
import { useUserStore } from '@/stores/user'
import FaceLogin from '@/components/FaceLogin.vue'
import { getCurrentLocation, getCityByLocation } from '@/utils/geolocation'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const loginMode = ref<'password' | 'face'>('password')

const form = reactive({
  account: '',
  password: '',
})

const rules: FormRules = {
  account: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  // 1. 表单验证
  if (!form.account || !form.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }

  // 2. 调用登录接口
  loading.value = true
  try {
    const res = await login({
      account: form.account.trim(),
      password: form.password,
    })

    if (!res || !res.data || !res.data.access_token) {
      throw new Error('登录响应异常')
    }

    // 3. 保存 token + 用户信息
    userStore.setToken(res.data.access_token, res.data.refresh_token)
    if (res.data.user) {
      userStore.setUserInfo(res.data.user)
    }

    // 4. 加载菜单（失败不影响登录）
    try {
      await userStore.fetchMenus()
    } catch (e) {
      console.warn('菜单加载失败')
    }

    // 5. 获取地理位置（最多等待3秒）
    fetchLocationAndWeather()

    // 6. 跳转首页
    ElMessage.success('登录成功，欢迎回来！')
    router.push('/dashboard')
  } catch (e: any) {
    console.error('登录出错:', e)
  } finally {
    loading.value = false
  }
}

const handleFaceLoginSuccess = async () => {
  fetchLocationAndWeather()
  ElMessage.success('登录成功，欢迎回来！')
  router.push('/dashboard')
}

async function fetchLocationAndWeather() {
  try {
    const location = await getCurrentLocation(3000)
    if (location.latitude && location.longitude) {
      const city = await getCityByLocation(location.latitude, location.longitude)
      if (city) {
        sessionStorage.setItem('weather_city', city.replace('市', ''))
        console.log('获取地理位置成功:', city)
      }
    } else if (location.error) {
      console.log('地理位置获取失败:', location.error)
    }
  } catch (e) {
    console.log('获取地理位置失败，将使用IP定位')
  }
}

// ============== 重置密码 ==============
const resetVisible = ref(false)
const resetFormRef = ref<FormInstance>()
const resetCodeSending = ref(false)
const resetSubmitting = ref(false)
const codeCountdown = ref(0)
let countdownTimer: number | null = null

const resetForm = reactive({
  email: '',
  code: '',
  new_password: '',
  confirm_password: '',
})

const validateConfirm = (_: any, value: string, cb: any) => {
  if (!value) {
    cb(new Error('请再次输入新密码'))
  } else if (value !== resetForm.new_password) {
    cb(new Error('两次输入的密码不一致'))
  } else {
    cb()
  }
}

const validateNewPwd = (_: any, value: string, cb: any) => {
  if (!value) {
    cb(new Error('请输入新密码'))
  } else if (value.length < 8) {
    cb(new Error('密码至少 8 位'))
  } else if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
    cb(new Error('密码必须包含字母和数字'))
  } else {
    cb()
  }
}

const resetRules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  new_password: [{ validator: validateNewPwd, trigger: 'blur' }],
  confirm_password: [{ validator: validateConfirm, trigger: 'blur' }],
}

function openResetDialog() {
  resetVisible.value = true
  resetForm.email = ''
  resetForm.code = ''
  resetForm.new_password = ''
  resetForm.confirm_password = ''
}

async function handleSendCode() {
  if (!resetForm.email) {
    ElMessage.warning('请先输入邮箱')
    return
  }
  resetCodeSending.value = true
  try {
    await sendResetCode(resetForm.email)
    ElMessage.success('验证码已发送到您的邮箱')
    codeCountdown.value = 60
    countdownTimer = window.setInterval(() => {
      codeCountdown.value--
      if (codeCountdown.value <= 0 && countdownTimer) {
        clearInterval(countdownTimer)
        countdownTimer = null
      }
    }, 1000)
  } catch (e) {
    // 错误已在拦截器中显示
  } finally {
    resetCodeSending.value = false
  }
}

async function handleResetPassword() {
  const ok = await resetFormRef.value?.validate().catch(() => false)
  if (ok === false) return

  resetSubmitting.value = true
  try {
    await resetPassword({
      email: resetForm.email,
      code: resetForm.code,
      new_password: resetForm.new_password,
      confirm_password: resetForm.confirm_password,
    })
    ElMessage.success('密码重置成功，请使用新密码登录')
    resetVisible.value = false
  } catch (e) {
    // 错误已在拦截器中显示
  } finally {
    resetSubmitting.value = false
  }
}

onBeforeUnmount(() => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
})
</script>

<style scoped>
.login-container {
  position: relative;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #1e3a8a 0%, #409eff 50%, #1e3a8a 100%);
  z-index: 0;
}

.bg-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.2;
  background: rgba(255, 255, 255, 0.5);
}

.bg-circle-1 {
  width: 400px;
  height: 400px;
  top: -150px;
  left: -150px;
}

.bg-circle-2 {
  width: 300px;
  height: 300px;
  bottom: -100px;
  right: -100px;
}

.bg-circle-3 {
  width: 200px;
  height: 200px;
  bottom: 30%;
  left: 20%;
}

.login-card {
  position: relative;
  z-index: 1;
  width: 420px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.98);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(10px);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.logo-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: linear-gradient(135deg, #409eff, #1e3a8a);
  margin-bottom: 16px;
}

.login-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.login-tabs {
  display: flex;
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.tab-item {
  flex: 1;
  text-align: center;
  padding: 8px;
  cursor: pointer;
  font-size: 15px;
  color: #6b7280;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
}

.tab-item:hover {
  color: #409eff;
}

.tab-item.active {
  color: #409eff;
  border-bottom-color: #409eff;
  font-weight: 600;
}

.subtitle {
  color: #6b7280;
  font-size: 13px;
  margin: 0;
}

.login-form {
  margin-top: 8px;
}

.login-form :deep(.el-input__wrapper) {
  padding: 8px 12px;
  box-shadow: 0 0 0 1px #d1d5db !important;
  border-radius: 8px;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px #409eff !important;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  font-weight: 600;
  margin-top: 8px;
  border-radius: 8px;
}

.login-btn:hover {
  opacity: 0.92;
}

.login-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  font-size: 13px;
  color: #6b7280;
}

.forget-link {
  color: #409eff;
  cursor: pointer;
  transition: opacity 0.2s;
}

.forget-link:hover {
  opacity: 0.8;
  text-decoration: underline;
}

.send-code-btn {
  margin-left: 8px;
}

.countdown-text {
  margin-left: 8px;
  color: #909399;
  font-size: 13px;
}

.copyright {
  position: absolute;
  bottom: 16px;
  left: 0;
  right: 0;
  text-align: center;
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  z-index: 1;
}
</style>
