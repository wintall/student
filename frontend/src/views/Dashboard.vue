<template>
  <div class="page-container">
    <!-- 欢迎卡片 + 天气 -->
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card class="welcome-card" shadow="hover">
          <div class="welcome-content">
            <div>
              <h2>欢迎回来 👋</h2>
              <p class="welcome-desc">学生信息管理系统 — 高效管理，智慧校园</p>
            </div>
            <div class="welcome-date">{{ currentDate }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="weather-card" shadow="hover" v-loading="weatherLoading">
          <div class="weather-header">
            <div class="weather-location">
              <el-icon><LocationInformation /></el-icon>
              <span>{{ weatherCity }}</span>
            </div>
            <el-input
              v-if="false"
              v-model="cityQuery"
              size="small"
              placeholder="切换城市"
              style="width: 140px"
            />
            <el-button size="small" text @click="openCityDialog">切换</el-button>
          </div>
          <div v-if="weather" class="weather-main">
            <div class="weather-icon">{{ weather.current.icon }}</div>
            <div class="weather-temp">
              <span class="temp">{{ weather.current.temperature }}</span>
              <span class="unit">°C</span>
            </div>
          </div>
          <div v-if="weather" class="weather-desc">{{ weather.current.description }}</div>
          <div v-if="weather && weather.forecast.length" class="weather-forecast">
            <div
              v-for="(day, idx) in weather.forecast.slice(0, 3)"
              :key="idx"
              class="forecast-item"
            >
              <div class="forecast-day">{{ formatForecastDay(day.date) }}</div>
              <div class="forecast-icon">{{ day.icon }}</div>
              <div class="forecast-temp">{{ day.min_temp }}° ~ {{ day.max_temp }}°</div>
            </div>
          </div>
          <div v-if="!weather && !weatherLoading" class="weather-empty">
            <el-empty description="暂无法获取天气" :image-size="80" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6" v-for="item in stats" :key="item.label">
        <el-card shadow="hover" class="stat-card" :style="{ borderTop: `3px solid ${item.color}` }">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-value">{{ item.value }}</div>
              <div class="stat-label">{{ item.label }}</div>
            </div>
            <el-icon :size="48" :color="item.color" :style="{ opacity: 0.2 }">
              <component :is="item.icon" />
            </el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷操作 + 公告 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span style="font-weight: 600;">快捷操作</span>
          </template>
          <div class="quick-actions">
            <el-button type="primary" @click="$router.push('/email/inbox')">
              <el-icon><Message /></el-icon> 收件箱
            </el-button>
            <el-button type="success" @click="$router.push('/email/compose')">
              <el-icon><Edit /></el-icon> 写邮件
            </el-button>
            <el-button type="warning" @click="$router.push('/people/student')">
              <el-icon><Postcard /></el-icon> 学生管理
            </el-button>
            <el-button type="info" @click="$router.push('/people/teacher')">
              <el-icon><Avatar /></el-icon> 教职工
            </el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span style="font-weight: 600;">系统信息</span>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="系统版本">v1.0.0</el-descriptions-item>
            <el-descriptions-item label="后端框架">FastAPI + SQLAlchemy</el-descriptions-item>
            <el-descriptions-item label="前端框架">Vue 3 + Element Plus</el-descriptions-item>
            <el-descriptions-item label="数据库">MySQL + Redis</el-descriptions-item>
            <el-descriptions-item label="API 文档">
              <el-link type="primary" href="/api/docs" target="_blank">Swagger 文档</el-link>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <!-- 城市切换弹窗 -->
    <el-dialog v-model="cityDialogVisible" title="切换天气城市" width="360px">
      <el-input v-model="cityQuery" placeholder="输入城市名称，如：北京 / Shanghai" clearable />
      <template #footer>
        <el-button @click="cityDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleQueryCity">查询</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'

const stats = reactive([
  { label: '学生总数', value: 0, icon: 'Postcard', color: '#409eff' },
  { label: '教职工数', value: 0, icon: 'Avatar', color: '#67c23a' },
  { label: '院系总数', value: 0, icon: 'School', color: '#e6a23c' },
  { label: '班级总数', value: 0, icon: 'Collection', color: '#f56c6c' },
])

const currentDate = ref(new Date().toLocaleDateString('zh-CN', {
  year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
}))

// ============== 天气 ==============
const weather = ref<any>(null)
const weatherCity = ref('定位中...')
const weatherLoading = ref(false)
const cityDialogVisible = ref(false)
const cityQuery = ref('')

async function loadWeather(city?: string) {
  weatherLoading.value = true
  try {
    const params: Record<string, any> = {}
    if (city) params.city = city
    const res = await request.get('/weather', { params })
    if (res.data) {
      weather.value = res.data
      weatherCity.value = res.data.current?.city || city || '本地'
    }
  } catch (e) {
    weather.value = null
    weatherCity.value = '暂不可用'
  } finally {
    weatherLoading.value = false
  }
}

function openCityDialog() {
  cityQuery.value = ''
  cityDialogVisible.value = true
}

function handleQueryCity() {
  const q = cityQuery.value.trim()
  if (!q) return
  cityDialogVisible.value = false
  loadWeather(q)
}

function formatForecastDay(dateStr: string) {
  if (!dateStr) return ''
  // wttr.in 格式 YYYY-MM-DD
  const today = new Date()
  const d = new Date(dateStr)
  if (d.toDateString() === today.toDateString()) return '今天'
  const tomorrow = new Date(today.getTime() + 86400000)
  if (d.toDateString() === tomorrow.toDateString()) return '明天'
  const after = new Date(today.getTime() + 86400000 * 2)
  if (d.toDateString() === after.toDateString()) return '后天'
  return dateStr
}

onMounted(async () => {
  // 统计数据
  try {
    const [studentRes, teacherRes, deptRes, clazzRes] = await Promise.all([
      request.get('/students', { params: { page: 1, page_size: 1 } }),
      request.get('/teachers', { params: { page: 1, page_size: 1 } }),
      request.get('/departments'),
      request.get('/clazzes', { params: { page: 1, page_size: 1 } }),
    ])
    stats[0].value = studentRes.data?.total ?? 0
    stats[1].value = teacherRes.data?.total ?? 0
    stats[2].value = Array.isArray(deptRes.data) ? deptRes.data.length : (deptRes.data?.total || 0)
    stats[3].value = clazzRes.data?.total ?? 0
  } catch (e) {
    stats[0].value = 0
    stats[1].value = 0
    stats[2].value = 0
    stats[3].value = 0
  }

  // 天气
  loadWeather()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
}

.welcome-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 12px;
  margin-bottom: 20px;
  color: #fff;
}
.welcome-card :deep(.el-card__body) { color: #fff; }
.welcome-content { display: flex; justify-content: space-between; align-items: center; }
.welcome-content h2 { margin: 0 0 8px; font-size: 22px; }
.welcome-desc { opacity: 0.85; margin: 0; }
.welcome-date { font-size: 14px; opacity: 0.8; }

/* 天气卡片 */
.weather-card {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  border: none;
  border-radius: 12px;
  margin-bottom: 20px;
  color: #fff;
}
.weather-card :deep(.el-card__body) { color: #fff; padding: 20px; }
.weather-card :deep(.el-empty__description) { color: rgba(255, 255, 255, 0.7); }

.weather-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px;
}
.weather-location {
  display: flex; align-items: center; gap: 6px; font-size: 14px;
}

.weather-main {
  display: flex; align-items: center; gap: 18px;
}
.weather-icon { font-size: 48px; line-height: 1; }
.weather-temp { display: flex; align-items: flex-start; }
.weather-temp .temp { font-size: 48px; font-weight: 700; line-height: 1; }
.weather-temp .unit { font-size: 18px; margin-left: 4px; opacity: 0.9; }

.weather-desc { margin-top: 8px; opacity: 0.9; font-size: 14px; }

.weather-forecast {
  display: flex; gap: 12px; margin-top: 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.2); padding-top: 14px;
}
.forecast-item {
  flex: 1; text-align: center; font-size: 12px;
}
.forecast-day { opacity: 0.9; }
.forecast-icon { font-size: 22px; margin: 6px 0; }
.forecast-temp { opacity: 0.85; }

.stat-row { margin-top: 0; }
.stat-card { border-radius: 12px; }
.stat-content { display: flex; justify-content: space-between; align-items: center; }
.stat-value { font-size: 32px; font-weight: 700; color: #1a1a2e; }
.stat-label { font-size: 14px; color: #909399; margin-top: 4px; }

.quick-actions { display: flex; flex-wrap: wrap; gap: 12px; }
</style>
