<template>
  <div
    class="campus-assistant"
    :style="{ right: right + 'px', bottom: bottom + 'px' }"
  >
    <transition name="panel-pop">
      <section v-if="visible" class="assistant-panel">
        <header class="panel-header">
          <div>
            <div class="panel-title">校园助手</div>
            <div class="panel-subtitle">{{ activeMode?.description || '自然语言提问，助手会选择合适能力' }}</div>
          </div>
          <div class="panel-actions">
            <el-button text @click="clearContext">
              <el-icon><Delete /></el-icon>
            </el-button>
            <el-button text @click="visible = false">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
        </header>

        <main ref="messagesRef" class="message-list">
          <div v-if="!messages.length" class="welcome">
            <div class="welcome-ball">
              <span class="ball-pattern"></span>
            </div>
            <h3>想问什么，直接说就行</h3>
            <p>下面的模块不是跳转菜单，只是切换助手能力。也可以保持“自动”，让助手自己判断。</p>
            <div class="quick-row">
              <button
                v-for="question in activeQuickQuestions"
                :key="question"
                type="button"
                @click="sendMessage(question)"
              >
                {{ question }}
              </button>
            </div>
          </div>

          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="message-row"
            :class="msg.role"
          >
            <div class="avatar">
              <el-icon v-if="msg.role === 'user'"><User /></el-icon>
              <span v-else class="mini-ball"></span>
            </div>
            <div class="bubble" v-html="formatMessage(msg.content)"></div>
          </div>

          <div v-if="loading" class="message-row assistant">
            <div class="avatar"><span class="mini-ball"></span></div>
            <div class="bubble thinking">
              <span></span><span></span><span></span>
            </div>
          </div>
        </main>

        <div class="mode-strip">
          <button
            v-for="mode in modes"
            :key="mode.code"
            type="button"
            :class="{ active: mode.code === currentMode }"
            @click="switchMode(mode.code)"
          >
            <el-icon><component :is="mode.icon" /></el-icon>
            <span>{{ mode.name }}</span>
          </button>
        </div>

        <footer class="composer">
          <el-input
            v-model="inputText"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            :placeholder="activePlaceholder"
            resize="none"
            :disabled="loading"
            @keydown="handleKeydown"
          />
          <el-button type="primary" circle :loading="loading" @click="sendMessage()">
            <el-icon><Promotion /></el-icon>
          </el-button>
        </footer>
      </section>
    </transition>

    <button
      class="football-button"
      :class="{ open: visible, dragging: isDragging }"
      type="button"
      aria-label="校园助手"
      @mousedown="onMouseDown"
      @click="togglePanel"
    >
      <span class="football-fallback">
        <span class="fallback-core"></span>
      </span>
      <canvas ref="footballCanvas" class="football-canvas" aria-hidden="true"></canvas>
      <span class="football-shine"></span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Close,
  DataAnalysis,
  Delete,
  Document,
  MagicStick,
  Notebook,
  Promotion,
  Reading,
  Search,
  Soccer,
  Tools,
  User,
} from '@element-plus/icons-vue'
import { chatWithCampusAgent, clearCampusAgentContext, getCampusAgentModes } from '@/api/ai'

interface AssistantMode {
  code: string
  name: string
  description: string
  quick_questions: string[]
  icon?: any
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

const modeIcons: Record<string, any> = {
  auto: MagicStick,
  rag: Reading,
  academic_tools: Tools,
  study: Notebook,
  document: Document,
  emotion: User,
  data_analysis: DataAnalysis,
  worldcup: Soccer,
  ai_knowledge: Search,
}

const fallbackModes: AssistantMode[] = [
  { code: 'auto', name: '自动', description: '自动判断问题类型并选择合适能力', quick_questions: ['我的课表', '我的成绩怎么样', '最近有什么公告'] },
  { code: 'rag', name: 'RAG知识问答', description: '知识库检索问答', quick_questions: ['三打白骨精是哪一回', '帮我查一段名著知识'] },
  { code: 'academic_tools', name: '教务查询', description: '成绩、课表、请假、考勤、公告查询', quick_questions: ['查看我的考勤', '我的请假进度', '今天有什么课'] },
  { code: 'study', name: '学习辅导', description: '学习计划和复习建议', quick_questions: ['帮我制定复习计划', '数学怎么查漏补缺'] },
  { code: 'document', name: '文档处理', description: '总结、提纲和重点提取', quick_questions: ['帮我总结一份课程资料', '提取文档重点'] },
  { code: 'emotion', name: '情绪陪伴', description: '压力倾诉和状态调整', quick_questions: ['我最近考试压力很大', '帮我调整学习状态'] },
  { code: 'data_analysis', name: '数据分析', description: '数据体检和趋势分析', quick_questions: ['系统还有哪些高危异常', '分析一下学生成绩趋势'] },
  { code: 'worldcup', name: '世界杯问答', description: '世界杯知识问答', quick_questions: ['2022世界杯冠军是谁', '世界杯小组赛规则是什么'] },
  { code: 'ai_knowledge', name: 'AI知识问答', description: 'AI、后端、数据库等技术问答', quick_questions: ['LangGraph和LangChain区别', 'FastAPI常见面试题'] },
]

const visible = ref(false)
const inputText = ref('')
const messages = ref<ChatMessage[]>([])
const loading = ref(false)
const messagesRef = ref<HTMLElement | null>(null)
const modes = ref<AssistantMode[]>(fallbackModes.map((mode) => ({ ...mode, icon: modeIcons[mode.code] || MagicStick })))
const currentMode = ref('auto')
const sessionId = ref<string | undefined>()

const right = ref(28)
const bottom = ref(30)
const isDragging = ref(false)
const hasDragged = ref(false)
const startX = ref(0)
const startY = ref(0)
const startRight = ref(0)
const startBottom = ref(0)
const footballCanvas = ref<HTMLCanvasElement | null>(null)

let THREE_LIB: any = null
let footballRenderer: any = null
let footballScene: any = null
let footballCamera: any = null
let footballGroup: any = null
let footballFrame = 0

const activeMode = computed(() => modes.value.find((mode) => mode.code === currentMode.value) || modes.value[0])
const activeQuickQuestions = computed(() => activeMode.value?.quick_questions?.slice(0, 4) || [])
const activePlaceholder = computed(() => {
  if (currentMode.value === 'auto') return '问成绩、课表、请假、知识点、情绪压力都可以...'
  return `当前：${activeMode.value?.name}。输入你的问题，Enter 发送`
})

function onMouseDown(e: MouseEvent) {
  isDragging.value = false
  hasDragged.value = false
  startX.value = e.clientX
  startY.value = e.clientY
  startRight.value = right.value
  startBottom.value = bottom.value
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

function onMouseMove(e: MouseEvent) {
  const deltaX = e.clientX - startX.value
  const deltaY = e.clientY - startY.value
  if (!isDragging.value) {
    if (Math.abs(deltaX) > 5 || Math.abs(deltaY) > 5) {
      isDragging.value = true
      hasDragged.value = true
    }
    return
  }
  right.value = Math.max(8, Math.min(window.innerWidth - 64, startRight.value - deltaX))
  bottom.value = Math.max(8, Math.min(window.innerHeight - 64, startBottom.value - deltaY))
}

function onMouseUp() {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
  isDragging.value = false
}

function togglePanel() {
  if (hasDragged.value) {
    hasDragged.value = false
    return
  }
  visible.value = !visible.value
}

function switchMode(mode: string) {
  currentMode.value = mode
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  })
}

function formatMessage(text: string) {
  if (!text) return ''
  return text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')
}

async function sendMessage(presetText?: string) {
  const text = (presetText || inputText.value).trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  scrollToBottom()

  loading.value = true
  try {
    const res = await chatWithCampusAgent({
      message: text,
      mode: currentMode.value,
      session_id: sessionId.value,
    })
    sessionId.value = res.data?.session_id || sessionId.value
    const reply = res.data?.reply || '我收到了，但暂时没有生成有效回复。'
    messages.value.push({ role: 'assistant', content: reply })
  } catch (e: any) {
    messages.value.push({
      role: 'assistant',
      content: e?.message || '校园助手暂时不可用，请稍后再试。',
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

async function clearContext() {
  try {
    await clearCampusAgentContext(sessionId.value)
    messages.value = []
    sessionId.value = undefined
    ElMessage.success('对话已清空')
  } catch (e) {
    messages.value = []
    sessionId.value = undefined
  }
}

async function loadModes() {
  try {
    const res = await getCampusAgentModes()
    const remoteModes = (res.data || []) as AssistantMode[]
    if (remoteModes.length) {
      modes.value = remoteModes.map((mode) => ({ ...mode, icon: modeIcons[mode.code] || MagicStick }))
    }
  } catch (e) {}
}

function addBallPatch(direction: any, radius: number, sides: number) {
  const THREE = THREE_LIB
  if (!footballGroup) return
  const normal = direction.clone().normalize()
  const geometry = new THREE.CircleGeometry(radius, sides)
  const material = new THREE.MeshStandardMaterial({
    color: 0x101828,
    roughness: 0.72,
    metalness: 0,
    side: THREE.DoubleSide,
  })
  const patch = new THREE.Mesh(geometry, material)
  patch.position.copy(normal.multiplyScalar(1.015))
  patch.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), direction.clone().normalize())
  footballGroup.add(patch)
}

function addSeam(rotation: [number, number, number]) {
  const THREE = THREE_LIB
  if (!footballGroup) return
  const geometry = new THREE.TorusGeometry(1.012, 0.008, 8, 96)
  const material = new THREE.MeshStandardMaterial({
    color: 0x111827,
    roughness: 0.8,
  })
  const seam = new THREE.Mesh(geometry, material)
  seam.rotation.set(rotation[0], rotation[1], rotation[2])
  footballGroup.add(seam)
}

function drawTexturePanel(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  rotation: number,
  colors: [string, string, string],
  label: string,
) {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.rotate(rotation)

  const panelPath = new Path2D()
  panelPath.moveTo(-148, -62)
  panelPath.bezierCurveTo(-88, -126, 35, -104, 148, -32)
  panelPath.bezierCurveTo(125, 32, 74, 76, 5, 96)
  panelPath.bezierCurveTo(-66, 118, -142, 74, -158, 10)
  panelPath.bezierCurveTo(-165, -20, -162, -43, -148, -62)
  panelPath.closePath()

  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.strokeStyle = 'rgba(173, 187, 205, 0.36)'
  ctx.lineWidth = 28
  ctx.stroke(panelPath)
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.94)'
  ctx.lineWidth = 17
  ctx.stroke(panelPath)

  const gradient = ctx.createLinearGradient(-160, -80, 150, 90)
  gradient.addColorStop(0, colors[0])
  gradient.addColorStop(0.56, colors[1])
  gradient.addColorStop(1, colors[2])
  ctx.fillStyle = gradient
  ctx.fill(panelPath)

  ctx.save()
  ctx.clip(panelPath)
  ctx.globalAlpha = 0.22
  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = 2
  for (let i = -210; i < 230; i += 11) {
    ctx.beginPath()
    ctx.moveTo(i, -130)
    ctx.lineTo(i + 150, 120)
    ctx.stroke()
  }
  ctx.globalAlpha = 0.28
  ctx.strokeStyle = '#082f49'
  ctx.lineWidth = 1.4
  for (let i = -150; i < 180; i += 18) {
    ctx.beginPath()
    ctx.moveTo(i, 102)
    ctx.bezierCurveTo(i + 34, 32, i + 80, -24, i + 140, -82)
    ctx.stroke()
  }
  ctx.globalAlpha = 1
  ctx.fillStyle = 'rgba(255, 255, 255, 0.92)'
  ctx.fillRect(-42, -20, 74, 58)
  ctx.fillStyle = colors[2]
  ctx.font = '700 21px Arial'
  ctx.textAlign = 'center'
  ctx.fillText(label, -5, 16)
  ctx.fillStyle = 'rgba(255, 255, 255, 0.78)'
  ctx.font = '700 26px Arial'
  ctx.fillText('★', 72, -42)
  ctx.fillText('★', 100, 48)
  ctx.restore()

  ctx.restore()
}

function createTriondaTexture() {
  const THREE = THREE_LIB
  const canvas = document.createElement('canvas')
  canvas.width = 1024
  canvas.height = 512
  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  const baseGradient = ctx.createRadialGradient(370, 130, 20, 512, 256, 650)
  baseGradient.addColorStop(0, '#ffffff')
  baseGradient.addColorStop(0.58, '#f6f9fd')
  baseGradient.addColorStop(1, '#d9e2ee')
  ctx.fillStyle = baseGradient
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  ctx.strokeStyle = 'rgba(149, 164, 183, 0.28)'
  ctx.lineWidth = 5
  for (let i = -120; i < 1120; i += 190) {
    ctx.beginPath()
    ctx.moveTo(i, -40)
    ctx.bezierCurveTo(i + 150, 110, i + 12, 285, i + 170, 555)
    ctx.stroke()
  }
  for (let i = -60; i < 1060; i += 260) {
    ctx.beginPath()
    ctx.moveTo(i, 555)
    ctx.bezierCurveTo(i + 130, 390, i + 190, 158, i + 365, -50)
    ctx.stroke()
  }

  drawTexturePanel(ctx, 190, 185, -0.38, ['#d7192d', '#f04d2f', '#ff7a3a'], 'FIFA')
  drawTexturePanel(ctx, 520, 330, 0.1, ['#008c60', '#11b26d', '#74c043'], 'TRIONDA')
  drawTexturePanel(ctx, 830, 190, 0.42, ['#005bbb', '#0387df', '#23b7e5'], 'FIFA')
  drawTexturePanel(ctx, -120, 332, 0.14, ['#005bbb', '#0387df', '#23b7e5'], 'FIFA')
  drawTexturePanel(ctx, 1144, 182, -0.38, ['#d7192d', '#f04d2f', '#ff7a3a'], 'FIFA')

  ctx.globalAlpha = 0.25
  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = 16
  ctx.beginPath()
  ctx.moveTo(32, 118)
  ctx.bezierCurveTo(220, 36, 338, 82, 478, 208)
  ctx.bezierCurveTo(624, 340, 750, 418, 988, 392)
  ctx.stroke()
  ctx.globalAlpha = 1

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 4
  texture.needsUpdate = true
  return texture
}

function disposeFootball() {
  cancelAnimationFrame(footballFrame)
  if (footballScene) {
    footballScene.traverse((item) => {
      const mesh = item as any
      if (mesh.geometry) mesh.geometry.dispose()
      const material = mesh.material as any
      if (Array.isArray(material)) material.forEach((m) => m.dispose())
      else material?.dispose()
    })
  }
  footballRenderer?.dispose()
  footballRenderer = null
  footballScene = null
  footballCamera = null
  footballGroup = null
}

async function initFootball() {
  const canvas = footballCanvas.value
  if (!canvas || footballRenderer) return
  THREE_LIB = THREE_LIB || await import('three')
  const THREE = THREE_LIB

  footballScene = new THREE.Scene()
  footballCamera = new THREE.PerspectiveCamera(32, 1, 0.1, 20)
  footballCamera.position.set(0, 0, 5.2)

  footballRenderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    powerPreference: 'high-performance',
  })
  footballRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  footballRenderer.setSize(62, 62, false)
  footballRenderer.shadowMap.enabled = true
  footballRenderer.shadowMap.type = THREE.PCFSoftShadowMap

  const ambient = new THREE.AmbientLight(0xffffff, 1.9)
  footballScene.add(ambient)

  const keyLight = new THREE.DirectionalLight(0xffffff, 2.4)
  keyLight.position.set(2.6, 3.2, 4.5)
  footballScene.add(keyLight)

  const rimLight = new THREE.DirectionalLight(0x9ec5ff, 1.4)
  rimLight.position.set(-3.2, -1.2, 3)
  footballScene.add(rimLight)

  footballGroup = new THREE.Group()
  footballGroup.rotation.set(-0.25, 0.35, 0.08)
  footballScene.add(footballGroup)

  const ball = new THREE.Mesh(
    new THREE.SphereGeometry(1, 64, 64),
    new THREE.MeshStandardMaterial({
      color: 0xf9fafb,
      map: createTriondaTexture(),
      roughness: 0.3,
      metalness: 0.02,
    }),
  )
  footballGroup.add(ball)

  addSeam([0.12, 0.24, 0.18])
  addSeam([Math.PI / 2.24, 0.24, -0.16])
  addSeam([0.24, Math.PI / 2.28, 0.62])

  const animate = () => {
    if (!footballRenderer || !footballScene || !footballCamera || !footballGroup) return
    const speed = visible.value ? 0.018 : 0.01
    footballGroup.rotation.y += speed
    footballGroup.rotation.x += isDragging.value ? 0.012 : 0.004
    footballRenderer.render(footballScene, footballCamera)
    footballFrame = requestAnimationFrame(animate)
  }
  animate()
}

onMounted(() => {
  loadModes()
  initFootball()
})
onUnmounted(() => {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
  disposeFootball()
})
</script>

<style scoped>
.campus-assistant {
  position: fixed;
  z-index: 9999;
}

.football-button {
  width: 62px;
  height: 62px;
  border: 0;
  border-radius: 50%;
  padding: 0;
  cursor: pointer;
  background: radial-gradient(circle at 35% 26%, #ffffff 0 30%, #dfe7f2 72%, #b9c5d6 100%);
  border: 1px solid rgba(15, 23, 42, 0.16);
  box-shadow:
    0 14px 32px rgba(20, 32, 55, 0.28),
    inset -8px -10px 18px rgba(15, 23, 42, 0.18),
    inset 7px 8px 12px rgba(255, 255, 255, 0.92);
  display: grid;
  place-items: center;
  position: relative;
  overflow: hidden;
  animation: footballFloat 3.6s ease-in-out infinite;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.football-button:hover {
  transform: translateY(-3px) scale(1.05);
  box-shadow:
    0 18px 42px rgba(20, 32, 55, 0.34),
    inset -8px -10px 18px rgba(15, 23, 42, 0.18),
    inset 7px 8px 12px rgba(255, 255, 255, 0.92);
}

.football-button.dragging {
  cursor: grabbing;
  transform: scale(1.08);
}

.football-button.open {
  box-shadow:
    0 16px 40px rgba(45, 108, 223, 0.34),
    inset -8px -10px 18px rgba(15, 23, 42, 0.18),
    inset 7px 8px 12px rgba(255, 255, 255, 0.92);
}

.football-canvas {
  width: 62px;
  height: 62px;
  display: block;
  position: relative;
  z-index: 2;
}

.football-fallback {
  position: absolute;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background:
    radial-gradient(ellipse at 33% 22%, rgba(255, 255, 255, 0.92) 0 11%, transparent 12%),
    radial-gradient(ellipse at 26% 38%, #f04d2f 0 15%, transparent 16%),
    radial-gradient(ellipse at 55% 72%, #10a76c 0 18%, transparent 19%),
    radial-gradient(ellipse at 76% 36%, #0878d1 0 18%, transparent 19%),
    conic-gradient(from 25deg, #f8fafc 0 13%, #dce7f3 13% 16%, #ffffff 16% 32%, #dce7f3 32% 35%, #f8fafc 35% 56%, #dce7f3 56% 59%, #ffffff 59% 78%, #dce7f3 78% 81%, #f8fafc 81% 100%);
  border: 1px solid rgba(148, 163, 184, 0.55);
  box-shadow: inset -8px -9px 12px rgba(15, 23, 42, 0.2), inset 6px 6px 10px rgba(255, 255, 255, 0.9);
  animation: fallbackSpin 4.8s linear infinite;
  z-index: 1;
}

.fallback-core {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 34px;
  height: 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow:
    -13px -8px 0 -2px rgba(240, 77, 47, 0.95),
    11px -5px 0 -2px rgba(8, 120, 209, 0.95),
    1px 12px 0 -1px rgba(16, 167, 108, 0.95);
  transform: translate(-50%, -50%) rotate(-18deg);
}

.football-shine {
  position: absolute;
  width: 22px;
  height: 12px;
  left: 13px;
  top: 9px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.52);
  filter: blur(4px);
  pointer-events: none;
  z-index: 3;
}

@keyframes footballFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

@keyframes fallbackSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.assistant-panel {
  width: min(440px, calc(100vw - 28px));
  height: min(640px, calc(100vh - 116px));
  margin-bottom: 14px;
  background: #ffffff;
  border: 1px solid #d9e2ef;
  border-radius: 14px;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.24);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-pop-enter-active,
.panel-pop-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.panel-pop-enter-from,
.panel-pop-leave-to {
  opacity: 0;
  transform: translateY(16px) scale(0.98);
}

.panel-header {
  height: 72px;
  padding: 14px 16px;
  background: #0f172a;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-title {
  font-size: 17px;
  font-weight: 700;
}

.panel-subtitle {
  max-width: 300px;
  margin-top: 5px;
  color: #cbd5e1;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.panel-actions .el-button {
  color: #ffffff;
}

.message-list {
  flex: 1;
  min-height: 0;
  padding: 16px;
  overflow-y: auto;
  background: #f6f8fb;
}

.welcome {
  padding: 26px 8px 18px;
  text-align: center;
  color: #475467;
}

.welcome-ball {
  width: 58px;
  height: 58px;
  margin: 0 auto 14px;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid #111827;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.14);
  display: grid;
  place-items: center;
}

.ball-pattern {
  width: 23px;
  height: 23px;
  background: #111827;
  clip-path: polygon(50% 0, 100% 38%, 82% 100%, 18% 100%, 0 38%);
}

.welcome h3 {
  margin: 0 0 8px;
  color: #101828;
  font-size: 17px;
}

.welcome p {
  margin: 0 auto;
  max-width: 330px;
  font-size: 13px;
  line-height: 1.7;
}

.quick-row {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
}

.quick-row button {
  border: 1px solid #d0d7e2;
  background: #ffffff;
  color: #1d4ed8;
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 12px;
  cursor: pointer;
}

.message-row {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
  align-items: flex-start;
}

.message-row.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex: 0 0 32px;
  background: #1d4ed8;
  color: #ffffff;
}

.message-row.assistant .avatar {
  background: #ffffff;
  border: 1px solid #111827;
}

.mini-ball {
  width: 16px;
  height: 16px;
  background: #111827;
  clip-path: polygon(50% 0, 100% 38%, 82% 100%, 18% 100%, 0 38%);
}

.bubble {
  max-width: 304px;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
}

.message-row.assistant .bubble {
  background: #ffffff;
  color: #1f2937;
  border-top-left-radius: 3px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
}

.message-row.user .bubble {
  background: #1d4ed8;
  color: #ffffff;
  border-top-right-radius: 3px;
}

.thinking {
  display: flex;
  gap: 5px;
  padding: 14px;
}

.thinking span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
  animation: pulse 1.2s infinite ease-in-out;
}

.thinking span:nth-child(2) { animation-delay: 0.12s; }
.thinking span:nth-child(3) { animation-delay: 0.24s; }

@keyframes pulse {
  0%, 80%, 100% { transform: scale(0.55); opacity: 0.45; }
  40% { transform: scale(1); opacity: 1; }
}

.mode-strip {
  padding: 10px 12px;
  display: flex;
  gap: 8px;
  overflow-x: auto;
  border-top: 1px solid #e5e7eb;
  background: #ffffff;
}

.mode-strip button {
  min-width: max-content;
  height: 34px;
  border: 1px solid #d0d7e2;
  background: #ffffff;
  color: #344054;
  border-radius: 999px;
  padding: 0 11px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  cursor: pointer;
}

.mode-strip button.active {
  color: #ffffff;
  background: #0f172a;
  border-color: #0f172a;
}

.composer {
  padding: 12px;
  display: flex;
  gap: 9px;
  align-items: flex-end;
  border-top: 1px solid #e5e7eb;
  background: #ffffff;
}

.composer :deep(.el-textarea__inner) {
  border-radius: 10px;
  padding: 9px 12px;
}

@media (max-width: 560px) {
  .campus-assistant {
    right: 12px !important;
    bottom: 14px !important;
  }

  .assistant-panel {
    width: calc(100vw - 24px);
    height: min(660px, calc(100vh - 96px));
  }

  .panel-subtitle {
    max-width: 230px;
  }
}
</style>
