<template>
  <div class="floating-weather" :style="{ left: `${offsetLeft}px` }" v-loading="weatherLoading">
    <div class="weather-main">
      <div class="weather-icon">{{ weather?.current?.icon || '☁️' }}</div>
      <div class="weather-info">
        <div class="weather-top">
          <el-icon><LocationInformation /></el-icon>
          <span class="weather-city">{{ weatherCity }}</span>
        </div>
        <div class="weather-temp">
          <span>{{ weather?.current?.temperature ?? '--' }}</span>
          <small>°C</small>
          <em>{{ weather?.current?.description || '天气' }}</em>
        </div>
      </div>
    </div>
    <div class="weather-actions">
      <el-tooltip content="刷新天气" placement="top">
        <el-button circle size="small" :icon="Refresh" @click="reloadWeather" />
      </el-tooltip>
      <el-tooltip content="切换城市" placement="top">
        <el-button circle size="small" :icon="Search" @click="openCityDialog" />
      </el-tooltip>
    </div>

    <el-dialog v-model="cityDialogVisible" title="切换天气城市" width="360px">
      <el-input
        v-model="cityQuery"
        placeholder="输入城市名称，如：北京 / Shanghai"
        clearable
        @keyup.enter="handleQueryCity"
      />
      <template #footer>
        <el-button @click="cityDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleQueryCity">查询</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { LocationInformation, Refresh, Search } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { getCurrentLocation, getCityByLocation } from '@/utils/geolocation'

defineProps({
  offsetLeft: {
    type: Number,
    default: 240,
  },
})

const weather = ref<any>(null)
const weatherCity = ref('定位中...')
const weatherLoading = ref(false)
const cityDialogVisible = ref(false)
const cityQuery = ref('')

function normalizeWeatherCity(city?: string | null) {
  return (city || '').trim().replace(/\s+/g, '').replace(/市$/, '')
}

async function loadWeather(city?: string) {
  weatherLoading.value = true
  try {
    const params: Record<string, any> = {}
    const normalizedCity = normalizeWeatherCity(city)
    if (normalizedCity) params.city = normalizedCity
    const res = await request.get('/weather', { params })
    if (res.data?.current) {
      weather.value = res.data
      weatherCity.value = res.data.current?.city || normalizedCity || '本地'
    } else {
      weather.value = null
      weatherCity.value = normalizedCity || '暂不可用'
    }
  } catch (e) {
    weather.value = null
    weatherCity.value = normalizeWeatherCity(city) || '暂不可用'
  } finally {
    weatherLoading.value = false
  }
}

async function autoDetectCityAndLoadWeather() {
  try {
    const location = await getCurrentLocation(5000)
    if (location.latitude && location.longitude) {
      const city = await getCityByLocation(location.latitude, location.longitude)
      if (city) {
        const normalizedCity = normalizeWeatherCity(city)
        sessionStorage.setItem('weather_city', normalizedCity)
        loadWeather(normalizedCity)
        return
      }
    }
  } catch (e) {
    console.log('浏览器定位失败，使用IP定位')
  }
  loadWeather()
}

function openCityDialog() {
  cityQuery.value = ''
  cityDialogVisible.value = true
}

function handleQueryCity() {
  const q = normalizeWeatherCity(cityQuery.value)
  if (!q) return
  cityDialogVisible.value = false
  sessionStorage.setItem('weather_city', q)
  loadWeather(q)
}

function reloadWeather() {
  const savedCity = sessionStorage.getItem('weather_city')
  loadWeather(savedCity || undefined)
}

onMounted(() => {
  const savedCity = sessionStorage.getItem('weather_city')
  if (savedCity) {
    loadWeather(savedCity)
  } else {
    autoDetectCityAndLoadWeather()
  }
})
</script>

<style scoped>
.floating-weather {
  position: fixed;
  bottom: 18px;
  z-index: 1200;
  width: 236px;
  min-height: 86px;
  padding: 12px 12px 10px;
  color: #fff;
  background: linear-gradient(135deg, #2f80ed 0%, #16a085 100%);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(31, 45, 61, 0.22);
  transition: left 0.25s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

.floating-weather:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 34px rgba(31, 45, 61, 0.28);
}

.weather-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.weather-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  font-size: 34px;
  line-height: 1;
}

.weather-info {
  min-width: 0;
  flex: 1;
}

.weather-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  font-size: 13px;
  opacity: 0.95;
}

.weather-city {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.weather-temp {
  display: flex;
  align-items: baseline;
  gap: 3px;
  margin-top: 4px;
}

.weather-temp span {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.weather-temp small {
  font-size: 14px;
}

.weather-temp em {
  min-width: 0;
  margin-left: 6px;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.88);
  font-size: 12px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.weather-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 8px;
}

.weather-actions :deep(.el-button) {
  color: #fff;
  background: rgba(255, 255, 255, 0.16);
  border-color: rgba(255, 255, 255, 0.24);
}

.weather-actions :deep(.el-button:hover) {
  background: rgba(255, 255, 255, 0.26);
}

@media (max-width: 768px) {
  .floating-weather {
    right: 14px;
    left: 14px !important;
    bottom: 14px;
    width: auto;
  }
}
</style>
