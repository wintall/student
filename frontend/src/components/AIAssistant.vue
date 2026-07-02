<template>
  <div
    class="campus-assistant"
    :style="{ right: right + 'px', bottom: bottom + 'px' }"
  >
    <transition name="panel-pop">
      <section v-if="visible" class="assistant-panel">
        <header class="panel-header">
          <div>
            <div class="panel-title">{{ assistantTitle }}</div>
            <div class="panel-subtitle">{{ activeMode?.description || '自然语言提问，助手会选择合适能力' }}</div>
          </div>
          <div class="panel-actions">
            <el-popover
              v-model:visible="historyPopoverVisible"
              placement="bottom-end"
              trigger="click"
              width="340"
              popper-class="assistant-history-popper"
              @show="loadSessions"
            >
              <template #reference>
                <el-button text class="header-action history-action" title="历史会话">
                  <el-icon><Reading /></el-icon>
                  <span>历史</span>
                </el-button>
              </template>
              <div class="history-popover">
                <div class="history-popover-head">
                  <strong>历史会话</strong>
                  <button type="button" @click="startNewConversationFromHistory">新对话</button>
                </div>
                <div class="history-list">
                  <article
                    v-for="item in chatSessions"
                    :key="item.session_id"
                    class="history-item"
                    :class="{ active: item.session_id === sessionId }"
                  >
                    <button type="button" class="history-main" @click="restoreSession(item.session_id)">
                      <div class="history-card-title">
                        <strong>{{ item.title || '新的对话' }}</strong>
                        <small v-if="item.session_id === sessionId">当前</small>
                      </div>
                      <span>{{ item.last_user_message || item.last_message || '暂无消息' }}</span>
                      <em>{{ formatSessionTime(item.updated_at || item.created_at) }} · {{ item.message_count || 0 }} 条</em>
                    </button>
                    <button type="button" class="history-delete" title="删除会话" @click.stop="removeSession(item.session_id)">
                      <el-icon><Delete /></el-icon>
                    </button>
                  </article>
                  <div v-if="!chatSessions.length" class="history-empty">还没有历史会话</div>
                </div>
              </div>
            </el-popover>
            <el-dropdown trigger="click" popper-class="assistant-more-popper" @command="handleMoreCommand">
              <el-button text class="header-action icon-only" title="更多操作">
                <el-icon><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="new">
                    <el-icon><MagicStick /></el-icon>
                    新对话
                  </el-dropdown-item>
                  <el-dropdown-item command="rename">
                    <el-icon><EditPen /></el-icon>
                    设置助手名字
                  </el-dropdown-item>
                  <el-dropdown-item command="player">
                    <el-icon><Soccer /></el-icon>
                    切换球星：{{ footballPlayerName }}
                  </el-dropdown-item>
                  <el-dropdown-item command="clear">
                    <el-icon><Delete /></el-icon>
                    清空当前对话
                  </el-dropdown-item>
                  <el-dropdown-item divided command="close">
                    <el-icon><Close /></el-icon>
                    关闭助手
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </header>

        <main ref="messagesRef" class="message-list" @scroll="onMessagesScroll">
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
            <div class="message-stack">
              <div
                class="bubble"
                :class="{ typing: typing && idx === messages.length - 1 && msg.role === 'assistant' }"
                v-html="formatMessage(msg.content)"
              ></div>
              <div v-if="getMapVisual(msg)" class="map-visual-card">
                <div class="map-visual-header">
                  <div>
                    <span>{{ getMapVisual(msg)?.title || '路线生活' }}</span>
                    <small>{{ mapVisualSubtitle(getMapVisual(msg)) }}</small>
                  </div>
                  <el-icon><Location /></el-icon>
                </div>

                <template v-if="getMapVisual(msg)?.type === 'route'">
                  <div class="route-points">
                    <span>{{ getPlaceName(getMapVisual(msg)?.origin, '出发地') }}</span>
                    <span v-if="getMapVisual(msg)?.waypoint">{{ getPlaceName(getMapVisual(msg)?.waypoint, '途经地') }}</span>
                    <span>{{ getPlaceName(getMapVisual(msg)?.destination, '目的地') }}</span>
                  </div>
                  <div class="route-options">
                    <article v-for="route in getMapVisual(msg)?.routes || []" :key="route.route_type" class="route-option">
                      <header>
                        <strong>{{ route.summary?.label || routeLabel(route.route_type) }}</strong>
                        <em>{{ route.summary?.distance_km || formatKm(route.distance_m) }} km · {{ route.summary?.duration_minutes || formatMinutes(route.duration_s) }} 分钟</em>
                      </header>
                      <p v-if="route.summary?.walking_m">步行约 {{ route.summary.walking_m }} 米</p>
                      <p v-if="route.summary?.cost">预估票价约 {{ route.summary.cost }} 元</p>
                      <ol>
                        <li v-for="(seg, segIndex) in route.segments || []" :key="segIndex">
                          <b>{{ seg.from }} → {{ seg.to }}</b>
                          <span>{{ seg.summary?.distance_km || formatKm(seg.distance_m) }} km · {{ seg.summary?.duration_minutes || formatMinutes(seg.duration_s) }} 分钟</span>
                          <small v-for="step in (seg.steps || []).slice(0, 4)" :key="step">{{ step }}</small>
                        </li>
                      </ol>
                      <button v-if="route.map_links?.amap" type="button" @click="openExternal(route.map_links.amap)">
                        打开高德地图
                      </button>
                    </article>
                  </div>
                  <div v-if="hasNearby(getMapVisual(msg)?.nearby)" class="nearby-section">
                    <h4>目的地附近</h4>
                    <div v-for="(items, keyword) in getMapVisual(msg)?.nearby" :key="keyword" class="nearby-group">
                      <span>{{ keyword }}</span>
                      <button
                        v-for="item in (items || []).slice(0, 3)"
                        :key="item.name"
                        type="button"
                        @click="item.map_url && openExternal(item.map_url)"
                      >
                        {{ item.name }}
                      </button>
                    </div>
                  </div>
                </template>

                <template v-else-if="getMapVisual(msg)?.type === 'poi'">
                  <div class="poi-list">
                    <button
                      v-for="item in getMapVisual(msg)?.items || []"
                      :key="item.name"
                      type="button"
                      @click="item.map_url && openExternal(item.map_url)"
                    >
                      <strong>{{ item.name }}</strong>
                      <span>{{ item.address || '地址暂缺' }}</span>
                      <em v-if="item.distance">约 {{ item.distance }} 米</em>
                    </button>
                  </div>
                </template>
              </div>
              <div v-if="msg.references?.length" class="reference-list">
                <div v-for="ref in msg.references" :key="ref.id || ref.title" class="reference-item">
                  <div class="reference-title">
                    <span>{{ ref.title || '引用片段' }}</span>
                    <em v-if="typeof ref.score === 'number'">{{ Math.round(ref.score * 100) }}%</em>
                  </div>
                  <p>{{ formatReference(ref) }}</p>
                </div>
              </div>
            </div>
          </div>

          <div v-if="loading" class="message-row assistant">
            <div class="avatar"><span class="mini-ball"></span></div>
            <div class="bubble thinking">
              <span></span><span></span><span></span>
            </div>
          </div>
        </main>

        <button v-if="showJumpToBottom" class="jump-bottom" type="button" @click="forceScrollToBottom">
          回到底部
        </button>

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

        <div v-if="currentMode === 'code_review'" class="coding-model-bar">
          <span>模型</span>
          <el-select
            v-model="selectedCodingModel"
            size="small"
            class="coding-model-select"
            popper-class="assistant-model-popper"
          >
            <el-option
              v-for="item in codingModelOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>

        <footer
          class="composer"
          :class="{ dragging: isFileDragging }"
          @dragenter.prevent="onFileDragEnter"
          @dragover.prevent="onFileDragOver"
          @dragleave.prevent="onFileDragLeave"
          @drop.prevent="onFileDrop"
        >
          <input
            ref="fileInputRef"
            class="file-input"
            type="file"
            multiple
            accept=".txt,.md,.markdown,.pdf,.docx,.png,.jpg,.jpeg,.bmp,.webp,.tif,.tiff"
            @change="onFileInputChange"
          />
          <div class="composer-main">
            <div v-if="attachedFiles.length" class="attached-files">
              <div v-for="file in attachedFiles" :key="file.file_id" class="attached-file">
                <img v-if="file.preview_url" :src="file.preview_url" alt="" />
                <el-icon v-else><Document /></el-icon>
                <div>
                  <span>{{ file.name }}</span>
                  <em>{{ formatFileSize(file.size) }}</em>
                </div>
                <button type="button" @click="removeAttachedFile(file.file_id)">
                  <el-icon><Close /></el-icon>
                </button>
              </div>
            </div>
            <el-input
              ref="composerInputRef"
              v-model="inputText"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              :placeholder="activePlaceholder"
              resize="none"
              :disabled="loading"
              @keydown="handleKeydown"
            />
          </div>
          <el-button circle :disabled="loading" @click="openFilePicker">
            <el-icon><Paperclip /></el-icon>
          </el-button>
          <el-button type="primary" circle :loading="loading" @click="sendMessage()">
            <el-icon><Promotion /></el-icon>
          </el-button>
        </footer>
      </section>
    </transition>

    <el-dialog
      v-model="nameDialogVisible"
      title="设置助手名字"
      width="360px"
      append-to-body
      destroy-on-close
      @opened="focusNameInput"
    >
      <el-form label-position="top">
        <el-form-item label="助手昵称">
          <el-input
            ref="assistantNameInputRef"
            v-model="assistantNameDraft"
            maxlength="12"
            show-word-limit
            placeholder="例如：小智、wintall、小校园"
            @keydown.enter.prevent="saveAssistantName"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="nameDialogVisible = false">取消</el-button>
        <el-button @click="resetAssistantName">恢复默认</el-button>
        <el-button type="primary" @click="saveAssistantName">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="paymentDialogVisible"
      title="校园助手授权入口"
      width="340px"
      append-to-body
      destroy-on-close
      class="payment-dialog"
      @closed="releasePaymentImage"
    >
      <div class="payment-box">
        <img v-if="paymentImageUrl" :src="paymentImageUrl" alt="校园助手收款码" />
        <div v-else class="payment-placeholder">收款码加载中...</div>
        <p>右键足球弹出的扩展入口，后续可接入授权、消费和服务开通流程。</p>
      </div>
    </el-dialog>

    <div v-if="!visible" class="assistant-hover-tip" role="status">
      {{ assistantGreeting }}
    </div>

    <div v-if="!visible" class="football-player-stage" :class="`player-${footballPlayer}`">
      <button
        type="button"
        class="footballer"
        :aria-label="`当前${footballPlayerName}风格，点击切换球星`"
        :title="`当前${footballPlayerName}风格，点击切换球星`"
        @click.stop="toggleFootballPlayer"
      >
        <span class="player-shadow"></span>
        <span class="player-head"></span>
        <span class="player-hair"></span>
        <span class="player-face">
          <span class="eye left"></span>
          <span class="eye right"></span>
          <span class="brow"></span>
          <span class="nose"></span>
          <span class="mouth"></span>
          <span class="beard"></span>
        </span>
        <span class="player-body">
          <span>{{ footballPlayerNumber }}</span>
        </span>
        <span class="player-arm left"></span>
        <span class="player-arm right"></span>
        <span class="player-leg support"></span>
        <span class="player-leg kick"></span>
        <span class="player-boot support"></span>
        <span class="player-boot kick"></span>
      </button>
    </div>

    <button
      class="football-button"
      :class="{ open: visible, dragging: isDragging }"
      type="button"
      :aria-label="assistantTitle"
      @mousedown="onMouseDown"
      @click="togglePanel"
      @contextmenu.prevent.stop="openPaymentDialog"
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
import { computed, markRaw, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Close,
  DataAnalysis,
  Delete,
  Document,
  EditPen,
  MagicStick,
  Location,
  MoreFilled,
  Notebook,
  Paperclip,
  Promotion,
  Reading,
  Search,
  Soccer,
  Tools,
  User,
} from '@element-plus/icons-vue'
import {
  chatWithCampusAgent,
  clearCampusAgentContext,
  deleteCampusAgentSession,
  getCampusAgentModes,
  getCampusAgentSession,
  getCampusAgentSessions,
  uploadCampusAgentFile,
} from '@/api/ai'
import { useUserStore } from '@/stores/user'

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
  mode?: string
  tool_calls?: Array<Record<string, any>>
  references?: Array<{
    id?: number
    title?: string
    content?: string
    score?: number
    metadata?: Record<string, any>
  }>
}

interface ChatSessionItem {
  session_id: string
  title: string
  message_count: number
  last_message?: string
  last_user_message?: string
  created_at?: string
  updated_at?: string
}

type FootballPlayer = 'ronaldo' | 'messi'

function getMapVisual(msg: ChatMessage) {
  const toolCall = (msg.tool_calls || []).find((call) => call?.data?.visual)
  return toolCall?.data?.visual || null
}

function getPlaceName(place: any, fallback: string) {
  return place?.formatted_address || place?.name || fallback
}

function formatMinutes(seconds: number) {
  const value = Number(seconds || 0)
  return value ? Math.max(1, Math.round(value / 60)) : 0
}

function formatKm(meters: number) {
  const value = Number(meters || 0)
  return value ? (value / 1000).toFixed(1) : '0'
}

function routeLabel(type: string) {
  if (type === 'transit') return '公共交通'
  if (type === 'driving') return '自驾'
  return '路线'
}

function mapVisualSubtitle(visual: any) {
  if (!visual) return ''
  if (visual.type === 'poi') return `${visual.items?.length || 0} 个地点`
  const count = visual.routes?.length || 0
  return count ? `${count} 种出行方案` : '地点建议'
}

function hasNearby(nearby: Record<string, any[]> | undefined) {
  return Object.values(nearby || {}).some((items) => Array.isArray(items) && items.length)
}

function openExternal(url: string) {
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

interface AttachedFile {
  file_id: string
  name: string
  ext: string
  size: number
  mime_type: string
  kind: string
  preview_url?: string
}

function formatReference(ref: NonNullable<ChatMessage['references']>[number]) {
  const chunkNo = ref.metadata?.chunk_no
  const docId = ref.metadata?.document_id
  const parts = []
  if (chunkNo) parts.push(`片段 ${chunkNo}`)
  if (docId) parts.push(`文档 ${docId}`)
  return parts.length ? parts.join(' · ') : '相关出处'
}

const modeIcons: Record<string, any> = {
  auto: markRaw(MagicStick),
  rag: markRaw(Reading),
  search: markRaw(Search),
  academic_tools: markRaw(Tools),
  academic_ops: markRaw(Tools),
  study: markRaw(Notebook),
  document: markRaw(Document),
  code_review: markRaw(Tools),
  github: markRaw(Tools),
  emotion: markRaw(User),
  map: markRaw(Location),
  data_analysis: markRaw(DataAnalysis),
  worldcup: markRaw(Soccer),
  ai_knowledge: markRaw(Search),
}

const fallbackModes: AssistantMode[] = [
  { code: 'auto', name: '自动', description: '自动判断问题类型并选择合适能力', quick_questions: ['我的课表', '我的成绩怎么样', '最近有什么公告'] },
  { code: 'rag', name: 'RAG知识问答', description: '知识库检索问答', quick_questions: ['三打白骨精是哪一回', '帮我查一段名著知识'] },
  { code: 'search', name: '搜索引擎', description: '联网搜索实时资讯、资料和来源链接', quick_questions: ['搜索今天 AI 有什么新闻', '联网查 DeepSeek 最新消息', '帮我查 LangGraph 最新文档'] },
  { code: 'academic_ops', name: '教务助手', description: '查询和操作权限内教务数据', quick_questions: ['查询所有学生', '我的成绩怎么样', '今天有什么课', '给学生吴浩发邮件'] },
  { code: 'study', name: '学习辅导', description: '课程讲解、题目解析、复习计划和诗词鉴赏', quick_questions: ['数据库事务隔离级别怎么理解', '帮我制定一周英语复习计划', '赏析一下《静夜思》'] },
  { code: 'document', name: '文档处理', description: '总结、图片 OCR 和英汉互译', quick_questions: ['总结这段文字', '识别图片里的文字', '把这段话翻译成英文'] },
  { code: 'code_review', name: '编程助手', description: '代码问答、代码生成、文件定位、代码解释和项目体检', quick_questions: ['分析项目 E:\\student', '学生新增接口在哪', '帮我写一个 FastAPI 上传接口', '解释 AIAssistant.vue'] },
  { code: 'github', name: 'GitHub助手', description: '读取仓库、目录、issue、PR，确认后创建 issue', quick_questions: ['分析仓库 https://github.com/owner/repo', '查看这个仓库的 open issues', '创建一个 GitHub issue'] },
  { code: 'emotion', name: '情绪陪伴', description: '专业心理支持和压力调节', quick_questions: ['我最近考试压力很大，给我专业建议', '我总是拖延和自责怎么办'] },
  { code: 'map', name: '路线生活', description: '公共交通、自驾路线和周边搜索', quick_questions: ['从学校到火车站优先地铁', '学校附近有什么吃喝玩乐'] },
  { code: 'data_analysis', name: '数据分析', description: '数据体检和趋势分析', quick_questions: ['系统还有哪些高危异常', '分析一下学生成绩趋势'] },
  { code: 'worldcup', name: '世界杯问答', description: '世界杯知识问答', quick_questions: ['2022世界杯冠军是谁', '世界杯小组赛规则是什么'] },
  { code: 'ai_knowledge', name: 'AI知识问答', description: 'AI、后端、数据库等技术问答', quick_questions: ['LangGraph和LangChain区别', 'FastAPI常见面试题'] },
]

const forcedModeLabels: Record<string, Partial<AssistantMode>> = {
  code_review: {
    name: '编程助手',
    description: '代码问答、代码生成、文件定位、代码解释和项目体检',
    quick_questions: ['分析项目 E:\\student', '学生新增接口在哪', '帮我写一个 FastAPI 上传接口', '解释 AIAssistant.vue'],
  },
}

const codingModelOptions = [
  { value: 'system:auto', label: '系统推荐' },
  { value: 'deepseek:deepseek-chat', label: 'DeepSeek Chat' },
  { value: 'deepseek:deepseek-reasoner', label: 'DeepSeek Reasoner' },
  { value: 'qwen:qwen-plus', label: 'Qwen Plus' },
  { value: 'qwen:qwen-coder-plus', label: 'Qwen Coder Plus' },
  { value: 'openai:gpt-4.1', label: 'OpenAI GPT-4.1' },
  { value: 'anthropic:claude-sonnet', label: 'Claude Sonnet' },
  { value: 'local:ollama', label: '本地模型 Ollama' },
]

const ASSISTANT_NAME_DEFAULT = 'wintall'
const ASSISTANT_NAME_KEY_PREFIX = 'campus_assistant_name'
const FOOTBALL_PLAYER_KEY_PREFIX = 'campus_assistant_player'
const userStore = useUserStore()
const visible = ref(false)
const inputText = ref('')
const messages = ref<ChatMessage[]>([])
const loading = ref(false)
const typing = ref(false)
const messagesRef = ref<HTMLElement | null>(null)
const autoScroll = ref(true)
const showJumpToBottom = ref(false)
const composerInputRef = ref<any>(null)
const modes = ref<AssistantMode[]>(fallbackModes.map((mode) => ({ ...mode, icon: modeIcons[mode.code] || markRaw(MagicStick) })))
const currentMode = ref('auto')
const sessionId = ref<string | undefined>()
const fileInputRef = ref<HTMLInputElement | null>(null)
const attachedFiles = ref<AttachedFile[]>([])
const isFileDragging = ref(false)
const dragDepth = ref(0)
const assistantName = ref(ASSISTANT_NAME_DEFAULT)
const assistantNameDraft = ref('')
const nameDialogVisible = ref(false)
const assistantNameInputRef = ref<any>(null)
const selectedCodingModel = ref(codingModelOptions[0].value)
const paymentDialogVisible = ref(false)
const paymentImageUrl = ref('')
const historyPopoverVisible = ref(false)
const chatSessions = ref<ChatSessionItem[]>([])
const footballPlayer = ref<FootballPlayer>('messi')

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
let typingTimer: number | undefined
let footballRenderer: any = null
let footballScene: any = null
let footballCamera: any = null
let footballGroup: any = null
let footballFrame = 0

const assistantTitle = computed(() => assistantName.value ? `校园助手${assistantName.value}` : '校园助手')
const assistantGreeting = computed(() => `您好，我是${assistantTitle.value}，希望帮助到您`)
const footballPlayerName = computed(() => footballPlayer.value === 'ronaldo' ? 'C罗' : '梅西')
const footballPlayerNumber = computed(() => footballPlayer.value === 'ronaldo' ? '7' : '10')
const activeMode = computed(() => modes.value.find((mode) => mode.code === currentMode.value) || modes.value[0])
const activeQuickQuestions = computed(() => activeMode.value?.quick_questions?.slice(0, 4) || [])
const activePlaceholder = computed(() => {
  if (currentMode.value === 'auto') return '问成绩、课表、请假、知识点、情绪压力都可以...'
  if (currentMode.value === 'search') return '输入要联网搜索的问题，例如：今天 AI 有什么新闻、DeepSeek 最新消息...'
  if (currentMode.value === 'academic_ops' || currentMode.value === 'academic_tools') return '例如：查我的成绩、查询所有学生、新增学生、给学生吴浩发邮件...'
  if (currentMode.value === 'study') return '问课程知识、题目解析、复习计划，也可以直接发诗词让我鉴赏...'
  if (currentMode.value === 'document') return '拖入图片/PDF/Word/txt，或输入：提取图片文字、总结这个文件、存入知识库...'
  if (currentMode.value === 'code_review') return '问编程问题、找代码位置、生成代码，或输入项目路径做体检...'
  if (currentMode.value === 'github') return '输入 GitHub 仓库地址，可查目录、issue、PR，也可确认后创建 issue...'
  if (currentMode.value === 'map') return '例如：从A到B再到C、优先地铁、自驾路线、附近吃喝玩乐...'
  return `当前：${activeMode.value?.name}。输入你的问题，Enter 发送`
})

function assistantNameStorageKey() {
  const info = userStore.userInfo
  const identity = info?.id || info?.username || info?.account || 'guest'
  return `${ASSISTANT_NAME_KEY_PREFIX}:${identity}`
}

function footballPlayerStorageKey() {
  const info = userStore.userInfo
  const identity = info?.id || info?.username || info?.account || 'guest'
  return `${FOOTBALL_PLAYER_KEY_PREFIX}:${identity}`
}

function normalizeAssistantName(value: string) {
  return (value || '')
    .trim()
    .replace(/^校园助手/, '')
    .replace(/\s+/g, '')
    .slice(0, 12)
}

function loadAssistantName() {
  const saved = localStorage.getItem(assistantNameStorageKey())
  assistantName.value = normalizeAssistantName(saved || ASSISTANT_NAME_DEFAULT) || ASSISTANT_NAME_DEFAULT
}

function loadFootballPlayer() {
  const saved = localStorage.getItem(footballPlayerStorageKey())
  footballPlayer.value = saved === 'ronaldo' || saved === 'messi' ? saved : 'messi'
}

function setFootballPlayer(player: FootballPlayer) {
  footballPlayer.value = player
  localStorage.setItem(footballPlayerStorageKey(), player)
  focusComposer()
}

function toggleFootballPlayer() {
  setFootballPlayer(footballPlayer.value === 'messi' ? 'ronaldo' : 'messi')
  ElMessage.success(`已切换为${footballPlayerName.value}风格`)
}

function openNameDialog() {
  assistantNameDraft.value = assistantName.value
  nameDialogVisible.value = true
}

function focusNameInput() {
  nextTick(() => {
    assistantNameInputRef.value?.focus?.()
  })
}

function saveAssistantName() {
  const nextName = normalizeAssistantName(assistantNameDraft.value)
  if (!nextName) {
    ElMessage.warning('请输入助手昵称')
    return
  }
  assistantName.value = nextName
  localStorage.setItem(assistantNameStorageKey(), nextName)
  nameDialogVisible.value = false
  ElMessage.success(`已设置为${assistantTitle.value}`)
  focusComposer()
}

function resetAssistantName() {
  assistantName.value = ASSISTANT_NAME_DEFAULT
  assistantNameDraft.value = ASSISTANT_NAME_DEFAULT
  localStorage.removeItem(assistantNameStorageKey())
  nameDialogVisible.value = false
  ElMessage.success('已恢复默认名字')
  focusComposer()
}

function sessionStorageKey() {
  const info = userStore.userInfo
  const identity = info?.id || info?.username || info?.account || 'guest'
  return `campus_agent_session:${identity}`
}

function normalizeHistoryMessages(rawMessages: any[]): ChatMessage[] {
  return (rawMessages || [])
    .filter((item) => item?.role === 'user' || item?.role === 'assistant')
    .map((item) => ({
      role: item.role,
      content: item.content || '',
      mode: item.mode,
      references: item.tool_data?.references || [],
      tool_calls: item.tool_data?.tool_calls || [],
    }))
}

function formatSessionTime(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadSessions() {
  try {
    const res = await getCampusAgentSessions(20)
    chatSessions.value = res.data || []
  } catch (e) {
    chatSessions.value = []
  }
}

async function restoreSession(targetSessionId: string) {
  if (!targetSessionId) return
  try {
    stopTypingEffect()
    const res = await getCampusAgentSession(targetSessionId)
    const data = res.data
    if (!data?.session_id) {
      ElMessage.warning('会话不存在或已失效')
      return
    }
    sessionId.value = data.session_id
    localStorage.setItem(sessionStorageKey(), data.session_id)
    messages.value = normalizeHistoryMessages(data.messages || [])
    historyPopoverVisible.value = false
    const lastMode = [...messages.value].reverse().find((item) => item.mode)?.mode
    if (lastMode && modes.value.some((mode) => mode.code === lastMode)) {
      currentMode.value = lastMode
    }
    scrollToBottom(true)
    focusComposer()
  } catch (e: any) {
    ElMessage.error(e?.message || '加载历史会话失败')
  }
}

async function restoreLatestSession() {
  try {
    const savedSessionId = localStorage.getItem(sessionStorageKey())
    if (savedSessionId) {
      await restoreSession(savedSessionId)
      if (messages.value.length) return
    }
    await loadSessions()
    const latest = chatSessions.value.find((item) => item.message_count > 0)
    if (latest?.session_id) await restoreSession(latest.session_id)
  } catch (e) {}
}

function startNewConversation() {
  stopTypingEffect()
  messages.value = []
  sessionId.value = undefined
  attachedFiles.value.forEach((file) => {
    if (file.preview_url) URL.revokeObjectURL(file.preview_url)
  })
  attachedFiles.value = []
  localStorage.removeItem(sessionStorageKey())
  ElMessage.success('已开启新对话')
  focusComposer()
}

function startNewConversationFromHistory() {
  historyPopoverVisible.value = false
  startNewConversation()
}

async function removeSession(targetSessionId: string) {
  if (!targetSessionId) return
  try {
    await deleteCampusAgentSession(targetSessionId)
    chatSessions.value = chatSessions.value.filter((item) => item.session_id !== targetSessionId)
    if (targetSessionId === sessionId.value) {
      messages.value = []
      sessionId.value = undefined
      localStorage.removeItem(sessionStorageKey())
    }
    ElMessage.success('历史会话已删除')
  } catch (e: any) {
    ElMessage.error(e?.message || '删除历史会话失败')
  }
}

function handleMoreCommand(command: string) {
  if (command === 'new') {
    startNewConversation()
    return
  }
  if (command === 'rename') {
    openNameDialog()
    return
  }
  if (command === 'player') {
    toggleFootballPlayer()
    return
  }
  if (command === 'clear') {
    clearContext()
    return
  }
  if (command === 'close') {
    visible.value = false
  }
}

function selectedCodingModelPayload() {
  if (currentMode.value !== 'code_review') return {}
  const [provider, model] = selectedCodingModel.value.split(':')
  if (!provider || provider === 'system') return {}
  return {
    llm_provider: provider,
    llm_model: model,
  }
}

function releasePaymentImage() {
  if (paymentImageUrl.value) {
    URL.revokeObjectURL(paymentImageUrl.value)
    paymentImageUrl.value = ''
  }
}

async function openPaymentDialog() {
  paymentDialogVisible.value = true
  releasePaymentImage()
  try {
    const token = localStorage.getItem('access_token') || ''
    const response = await fetch('/api/v1/campus-agent/payment-code', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) throw new Error('收款码加载失败')
    const blob = await response.blob()
    paymentImageUrl.value = URL.createObjectURL(blob)
  } catch (e: any) {
    ElMessage.error(e?.message || '收款码加载失败')
  }
}

function onMouseDown(e: MouseEvent) {
  if (e.button !== 0) return
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
  if (visible.value) {
    focusComposer()
  }
}

function switchMode(mode: string) {
  currentMode.value = mode
  focusComposer()
}

function isNearBottom(el: HTMLElement, threshold = 72) {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= threshold
}

function updateScrollState() {
  const el = messagesRef.value
  if (!el) return
  const nearBottom = isNearBottom(el)
  autoScroll.value = nearBottom
  showJumpToBottom.value = !nearBottom
}

function onMessagesScroll() {
  updateScrollState()
}

function scrollToBottom(force = false) {
  nextTick(() => {
    const el = messagesRef.value
    if (!el) return
    if (!force && !autoScroll.value) {
      showJumpToBottom.value = true
      return
    }
    el.scrollTop = el.scrollHeight
    autoScroll.value = true
    showJumpToBottom.value = false
  })
}

function forceScrollToBottom() {
  autoScroll.value = true
  scrollToBottom(true)
  focusComposer()
}

function focusComposer() {
  nextTick(() => {
    if (!visible.value || loading.value) return
    composerInputRef.value?.focus?.()
    const textarea = composerInputRef.value?.textarea as HTMLTextAreaElement | undefined
    textarea?.focus()
  })
}

function formatMessage(text: string) {
  if (!text) return ''
  return text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')
}

function stopTypingEffect() {
  if (typingTimer) {
    window.clearTimeout(typingTimer)
    typingTimer = undefined
  }
  typing.value = false
}

function typeAssistantReply(messageIndex: number, fullText: string) {
  stopTypingEffect()
  typing.value = true
  if (!messages.value[messageIndex]) return
  const shouldFollow = messagesRef.value ? isNearBottom(messagesRef.value, 120) : true
  autoScroll.value = shouldFollow
  messages.value[messageIndex] = { ...messages.value[messageIndex], content: '' }
  const chars = Array.from(fullText || '我收到了，但暂时没有生成有效回复。')
  let index = 0
  const tick = () => {
    const current = messages.value[messageIndex]
    if (!current) {
      stopTypingEffect()
      return
    }
    const step = chars[index] === '\n' ? 1 : 2
    messages.value[messageIndex] = {
      ...current,
      content: current.content + chars.slice(index, index + step).join(''),
    }
    index += step
    scrollToBottom()
    if (index < chars.length) {
      typingTimer = window.setTimeout(tick, chars[index - 1] === '\n' ? 90 : 24)
      return
    }
    stopTypingEffect()
    focusComposer()
  }
  tick()
}

async function sendMessage(presetText?: string) {
  let text = (presetText || inputText.value).trim()
  if (!text && attachedFiles.value.length) {
    text = attachedFiles.value.some((file) => file.kind === 'image') ? '提取图片文字' : '总结这个文件'
  }
  if ((!text && !attachedFiles.value.length) || loading.value) return

  messages.value.push({ role: 'user', content: text })
  autoScroll.value = true
  const fileIds = attachedFiles.value.map((file) => file.file_id)
  attachedFiles.value.forEach((file) => {
    if (file.preview_url) URL.revokeObjectURL(file.preview_url)
  })
  attachedFiles.value = []
  inputText.value = ''
  scrollToBottom(true)

  loading.value = true
  try {
    const res = await chatWithCampusAgent({
      message: text,
      mode: currentMode.value,
      session_id: sessionId.value,
      file_ids: fileIds,
      ...selectedCodingModelPayload(),
    })
    sessionId.value = res.data?.session_id || sessionId.value
    if (sessionId.value) {
      localStorage.setItem(sessionStorageKey(), sessionId.value)
    }
    const reply = res.data?.reply || '我收到了，但暂时没有生成有效回复。'
    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      references: res.data?.references || [],
      tool_calls: res.data?.tool_calls || [],
    }
    messages.value.push(assistantMessage)
    typeAssistantReply(messages.value.length - 1, reply)
    loadSessions()
  } catch (e: any) {
    messages.value.push({
      role: 'assistant',
      content: e?.message || '校园助手暂时不可用，请稍后再试。',
    })
  } finally {
    loading.value = false
    scrollToBottom()
    if (!typing.value) focusComposer()
  }
}

function openFilePicker() {
  fileInputRef.value?.click()
}

function formatFileSize(size: number) {
  if (!Number.isFinite(size)) return ''
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function removeAttachedFile(fileId: string) {
  const file = attachedFiles.value.find((item) => item.file_id === fileId)
  if (file?.preview_url) URL.revokeObjectURL(file.preview_url)
  attachedFiles.value = attachedFiles.value.filter((item) => item.file_id !== fileId)
  focusComposer()
}

async function attachFiles(files: FileList | File[]) {
  const selected = Array.from(files)
  if (!selected.length) return
  if (attachedFiles.value.length + selected.length > 10) {
    ElMessage.warning('一次最多处理 10 个文件')
    return
  }
  currentMode.value = 'document'
  for (const raw of selected) {
    if (raw.size > 50 * 1024 * 1024) {
      ElMessage.warning(`${raw.name} 超过 50MB 限制`)
      continue
    }
    try {
      const res = await uploadCampusAgentFile(raw)
      const item = res.data as AttachedFile
      if (raw.type.startsWith('image/')) {
        item.preview_url = URL.createObjectURL(raw)
      }
      attachedFiles.value.push(item)
    } catch (e: any) {
      ElMessage.error(e?.message || `${raw.name} 上传失败`)
    }
  }
  focusComposer()
}

function onFileInputChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) attachFiles(input.files)
  input.value = ''
}

function onFileDragEnter(e: DragEvent) {
  if (!e.dataTransfer?.types?.includes('Files')) return
  dragDepth.value += 1
  isFileDragging.value = true
}

function onFileDragOver(e: DragEvent) {
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
  isFileDragging.value = true
}

function onFileDragLeave() {
  dragDepth.value = Math.max(0, dragDepth.value - 1)
  if (dragDepth.value === 0) isFileDragging.value = false
}

function onFileDrop(e: DragEvent) {
  dragDepth.value = 0
  isFileDragging.value = false
  const files = e.dataTransfer?.files
  if (files?.length) attachFiles(files)
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
    stopTypingEffect()
    messages.value = []
    attachedFiles.value.forEach((file) => {
      if (file.preview_url) URL.revokeObjectURL(file.preview_url)
    })
    attachedFiles.value = []
    ElMessage.success('对话已清空')
    loadSessions()
    focusComposer()
  } catch (e) {
    stopTypingEffect()
    messages.value = []
    focusComposer()
  }
}

async function loadModes() {
  try {
    const res = await getCampusAgentModes()
    const remoteModes = (res.data || []) as AssistantMode[]
    if (remoteModes.length) {
      modes.value = remoteModes.map((mode) => ({
        ...mode,
        ...(forcedModeLabels[mode.code] || {}),
        icon: modeIcons[mode.code] || markRaw(MagicStick),
      }))
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

onMounted(async () => {
  loadAssistantName()
  loadFootballPlayer()
  await loadModes()
  await restoreLatestSession()
  initFootball()
  focusComposer()
})
onUnmounted(() => {
  stopTypingEffect()
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
  attachedFiles.value.forEach((file) => {
    if (file.preview_url) URL.revokeObjectURL(file.preview_url)
  })
  disposeFootball()
})
</script>

<style scoped>
.campus-assistant {
  position: fixed;
  z-index: 9999;
}

.assistant-hover-tip {
  position: absolute;
  right: 72px;
  bottom: 10px;
  width: max-content;
  max-width: min(300px, calc(100vw - 112px));
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.94);
  color: #ffffff;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.22);
  font-size: 14px;
  line-height: 1.45;
  white-space: normal;
  pointer-events: none;
  opacity: 0;
  transform: translateX(8px) translateY(2px);
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.assistant-hover-tip::after {
  content: "";
  position: absolute;
  right: -6px;
  bottom: 18px;
  width: 12px;
  height: 12px;
  background: rgba(15, 23, 42, 0.94);
  transform: rotate(45deg);
}

.campus-assistant:hover .assistant-hover-tip {
  opacity: 1;
  transform: translateX(0) translateY(0);
}

.football-player-stage {
  position: absolute;
  right: 58px;
  bottom: -4px;
  width: 96px;
  height: 104px;
  pointer-events: none;
  opacity: 0.98;
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.campus-assistant:hover .football-player-stage {
  opacity: 1;
  transform: translateY(-2px);
}

.footballer {
  position: absolute;
  left: 5px;
  bottom: 9px;
  width: 72px;
  height: 88px;
  border: 0;
  padding: 0;
  cursor: pointer;
  background: transparent;
  transform-origin: 50% 100%;
  animation: playerApproach 2.8s ease-in-out infinite;
  pointer-events: auto;
}

.footballer::after {
  content: "";
  position: absolute;
  left: 31px;
  top: 25px;
  width: 7px;
  height: 17px;
  border-radius: 999px;
  background: #ffe3bd;
  z-index: 2;
}

.player-shadow {
  position: absolute;
  left: 10px;
  bottom: -3px;
  width: 58px;
  height: 12px;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.18);
  filter: blur(2px);
  animation: playerShadow 2.8s ease-in-out infinite;
}

.player-head {
  position: absolute;
  left: 24px;
  top: 3px;
  width: 24px;
  height: 27px;
  border-radius: 48% 48% 44% 44%;
  background: radial-gradient(circle at 35% 28%, #ffe3bd 0 24%, #d49762 72%, #a96a40 100%);
  box-shadow: inset -3px -3px 4px rgba(88, 52, 28, 0.18);
  z-index: 5;
}

.player-hair {
  position: absolute;
  left: 22px;
  top: -1px;
  width: 28px;
  height: 16px;
  border-radius: 58% 62% 34% 34%;
  background: #1f2937;
  transform: rotate(-10deg);
  box-shadow: 4px 3px 0 -1px #111827;
  z-index: 6;
}

.player-face {
  position: absolute;
  left: 24px;
  top: 3px;
  width: 24px;
  height: 27px;
  z-index: 7;
}

.player-face .eye,
.player-face .nose,
.player-face .mouth,
.player-face .brow,
.player-face .beard {
  position: absolute;
  display: block;
}

.player-face .eye {
  top: 12px;
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: #1f2937;
}

.player-face .eye.left {
  left: 7px;
}

.player-face .eye.right {
  right: 7px;
}

.player-face .brow {
  left: 6px;
  top: 9px;
  width: 12px;
  height: 2px;
  border-radius: 999px;
  background: rgba(31, 41, 55, 0.58);
  transform: rotate(-4deg);
}

.player-face .nose {
  left: 11px;
  top: 13px;
  width: 3px;
  height: 6px;
  border-radius: 999px;
  background: rgba(171, 104, 59, 0.34);
}

.player-face .mouth {
  left: 8px;
  top: 20px;
  width: 9px;
  height: 3px;
  border-radius: 0 0 999px 999px;
  border-bottom: 2px solid rgba(91, 54, 32, 0.68);
}

.player-face .beard {
  display: none;
}

.player-body {
  position: absolute;
  left: 20px;
  top: 31px;
  width: 32px;
  height: 34px;
  border-radius: 11px 11px 6px 6px;
  background: linear-gradient(135deg, #7dd3fc 0 28%, #ffffff 28% 40%, #7dd3fc 40% 60%, #ffffff 60% 72%, #7dd3fc 72% 100%);
  box-shadow: inset -4px -5px 7px rgba(15, 23, 42, 0.16), 0 5px 10px rgba(15, 23, 42, 0.16);
  z-index: 3;
}

.player-body::before {
  content: "";
  position: absolute;
  left: -6px;
  right: -6px;
  top: 3px;
  height: 10px;
  border-radius: 999px 999px 3px 3px;
  background: inherit;
  z-index: -1;
}

.player-body::after {
  content: "";
  position: absolute;
  right: -3px;
  top: 9px;
  width: 6px;
  height: 6px;
  border-radius: 2px;
  background: rgba(245, 158, 11, 0.92);
  box-shadow: 0 0 0 1px rgba(146, 64, 14, 0.16);
}

.player-body span {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -48%);
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
}

.player-arm {
  position: absolute;
  top: 38px;
  width: 9px;
  height: 32px;
  border-radius: 999px;
  background: #d49762;
  transform-origin: 50% 4px;
  z-index: 2;
}

.player-arm.left {
  left: 13px;
  transform: rotate(34deg);
  animation: playerArmLeft 2.8s ease-in-out infinite;
}

.player-arm.right {
  left: 50px;
  transform: rotate(-36deg);
  animation: playerArmRight 2.8s ease-in-out infinite;
}

.player-leg {
  position: absolute;
  top: 60px;
  width: 9px;
  height: 31px;
  border-radius: 999px 999px 7px 7px;
  background:
    linear-gradient(to bottom, #1d4ed8 0 22%, #d49762 22% 58%, #f8fafc 58% 100%);
  box-shadow: inset -2px 0 3px rgba(15, 23, 42, 0.14);
  transform-origin: 50% 4px;
  z-index: 2;
}

.player-leg::before {
  content: "";
  position: absolute;
  left: -2px;
  top: -3px;
  width: 13px;
  height: 9px;
  border-radius: 4px 4px 6px 6px;
  background: #1d4ed8;
}

.player-leg::after {
  content: "";
  position: absolute;
  left: 1px;
  bottom: 8px;
  width: 7px;
  height: 3px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.72);
}

.player-leg.support {
  left: 27px;
  transform: rotate(7deg);
}

.player-leg.kick {
  left: 40px;
  transform: rotate(-18deg);
  animation: playerKickLeg 2.8s ease-in-out infinite;
}

.player-boot {
  position: absolute;
  width: 15px;
  height: 7px;
  border-radius: 8px 6px 4px 4px;
  background: linear-gradient(90deg, #111827 0 74%, #374151 74% 100%);
  box-shadow: 0 2px 2px rgba(15, 23, 42, 0.18);
  z-index: 4;
}

.player-boot::after {
  content: "";
  position: absolute;
  left: 3px;
  right: 3px;
  bottom: -1px;
  height: 2px;
  border-radius: 999px;
  background: #f8fafc;
  opacity: 0.85;
}

.player-boot.support {
  left: 27px;
  bottom: 1px;
  transform: rotate(2deg);
}

.player-boot.kick {
  left: 43px;
  bottom: 8px;
  transform-origin: 2px 45%;
  animation: playerKickBoot 2.8s ease-in-out infinite;
}

.player-ronaldo .player-body {
  background:
    linear-gradient(90deg, transparent 0 42%, rgba(255, 255, 255, 0.92) 42% 50%, transparent 50% 100%),
    linear-gradient(135deg, #dc2626 0 52%, #b91c1c 52% 100%);
}

.player-ronaldo .player-body span {
  color: #ffffff;
}

.player-ronaldo .player-hair {
  left: 21px;
  top: -3px;
  height: 17px;
  border-radius: 45% 70% 34% 36%;
  background: linear-gradient(140deg, #111827 0 60%, #374151 61% 100%);
  transform: rotate(-18deg);
  box-shadow: 8px 2px 0 -5px #111827;
}

.player-ronaldo .player-leg {
  background:
    linear-gradient(to bottom, #f8fafc 0 22%, #d49762 22% 58%, #f8fafc 58% 100%);
  border: 1px solid rgba(148, 163, 184, 0.34);
}

.player-ronaldo .player-leg::before {
  background: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.28);
}

.player-ronaldo .player-leg::after {
  background: rgba(220, 38, 38, 0.78);
}

.player-messi .player-hair {
  left: 21px;
  top: 0;
  width: 30px;
  height: 17px;
  border-radius: 52% 58% 34% 42%;
  background: #4a2717;
  transform: rotate(6deg);
  box-shadow: -2px 5px 0 -1px #4a2717;
}

.player-messi .player-face .beard {
  display: block;
  left: 5px;
  top: 17px;
  width: 15px;
  height: 8px;
  border-radius: 2px 2px 999px 999px;
  background: rgba(74, 39, 23, 0.78);
  clip-path: polygon(0 0, 100% 0, 82% 100%, 18% 100%);
}

.player-messi .player-face .mouth {
  border-bottom-color: rgba(255, 255, 255, 0.78);
  z-index: 2;
}

.player-messi .player-leg {
  background:
    linear-gradient(to bottom, #1d4ed8 0 22%, #d49762 22% 58%, #f8fafc 58% 100%);
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

.football-player-stage + .football-button {
  animation: footballFloat 3.6s ease-in-out infinite, kickedBall 2.8s ease-in-out infinite;
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

.payment-box {
  display: grid;
  justify-items: center;
  gap: 12px;
}

.payment-box img,
.payment-placeholder {
  width: 230px;
  height: 230px;
  border-radius: 8px;
  border: 1px solid #d9e2ef;
  background: #f8fafc;
}

.payment-box img {
  display: block;
  object-fit: contain;
}

.payment-placeholder {
  display: grid;
  place-items: center;
  color: #64748b;
  font-size: 13px;
}

.payment-box p {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
  text-align: center;
}

:global(.assistant-history-popper) {
  z-index: 12055 !important;
  padding: 10px !important;
}

.history-popover {
  display: grid;
  gap: 10px;
}

.history-popover-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.history-popover-head strong {
  color: #111827;
  font-size: 14px;
}

.history-popover-head button {
  height: 28px;
  border: 0;
  border-radius: 999px;
  background: #0f172a;
  color: #ffffff;
  padding: 0 10px;
  font-size: 12px;
  cursor: pointer;
}

.history-list {
  max-height: min(380px, 58vh);
  overflow-y: auto;
  display: grid;
  gap: 8px;
}

.history-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 30px;
  gap: 6px;
  align-items: stretch;
  width: 100%;
  min-height: 72px;
  border: 1px solid #d9e2ef;
  border-radius: 8px;
  background: #ffffff;
  transition: border-color 0.16s ease, background 0.16s ease, box-shadow 0.16s ease;
}

.history-item:hover {
  border-color: #93b4e8;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
}

.history-item.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.history-main {
  min-width: 0;
  border: 0;
  background: transparent;
  padding: 10px 0 10px 11px;
  text-align: left;
  cursor: pointer;
}

.history-delete {
  width: 28px;
  height: 28px;
  align-self: center;
  justify-self: center;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
}

.history-delete:hover {
  background: #fee2e2;
  color: #dc2626;
}

.history-card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.history-card-title strong,
.history-list span,
.history-list em {
  display: block;
}

.history-card-title strong {
  min-width: 0;
  color: #111827;
  font-size: 13px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.history-card-title small {
  flex: 0 0 auto;
  border-radius: 999px;
  background: #2563eb;
  color: #ffffff;
  padding: 2px 7px;
  font-size: 11px;
  font-weight: 600;
}

.history-list span {
  margin-top: 4px;
  color: #475569;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-list em,
.history-empty {
  margin-top: 5px;
  color: #94a3b8;
  font-size: 11px;
  font-style: normal;
}

.history-empty {
  padding: 18px;
  text-align: center;
}

@keyframes footballFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

@keyframes fallbackSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes kickedBall {
  0%, 68%, 100% { transform: translateY(0) translateX(0) rotate(0deg); }
  74% { transform: translateY(-6px) translateX(4px) rotate(7deg); }
  82% { transform: translateY(0) translateX(0) rotate(0deg); }
}

@keyframes playerApproach {
  0%, 100% { transform: translateX(0) rotate(-1deg); }
  42% { transform: translateX(5px) rotate(1deg); }
  70% { transform: translateX(10px) rotate(-3deg); }
  82% { transform: translateX(3px) rotate(1deg); }
}

@keyframes playerShadow {
  0%, 100% { transform: scaleX(0.9); opacity: 0.14; }
  58% { transform: scaleX(1.08); opacity: 0.2; }
  74% { transform: scaleX(0.78); opacity: 0.12; }
}

@keyframes playerKickLeg {
  0%, 45%, 100% { transform: rotate(-18deg); }
  62% { transform: rotate(18deg); }
  74% { transform: rotate(-34deg); }
  88% { transform: rotate(-12deg); }
}

@keyframes playerKickBoot {
  0%, 45%, 100% { transform: translateX(0) translateY(0) rotate(-4deg); }
  62% { transform: translateX(-2px) translateY(1px) rotate(11deg); }
  74% { transform: translateX(4px) translateY(-4px) rotate(-10deg); }
  88% { transform: translateX(1px) translateY(0) rotate(-2deg); }
}

@keyframes playerArmLeft {
  0%, 100% { transform: rotate(34deg); }
  58% { transform: rotate(12deg); }
  74% { transform: rotate(52deg); }
}

@keyframes playerArmRight {
  0%, 100% { transform: rotate(-36deg); }
  58% { transform: rotate(-14deg); }
  74% { transform: rotate(-58deg); }
}

.assistant-panel {
  position: relative;
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

.panel-header > div:first-child {
  min-width: 0;
}

.panel-title {
  font-size: 17px;
  font-weight: 700;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.panel-subtitle {
  max-width: min(300px, calc(100vw - 190px));
  margin-top: 5px;
  color: #cbd5e1;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.panel-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 6px;
}

.panel-actions .header-action {
  color: #ffffff;
  min-width: 34px;
  height: 32px;
  padding: 0 8px;
  border-radius: 8px;
}

.panel-actions .history-action {
  gap: 4px;
}

.panel-actions .history-action span {
  font-size: 12px;
}

.panel-actions .icon-only {
  width: 34px;
  padding: 0;
}

:global(.assistant-more-popper) {
  z-index: 12060 !important;
}

:global(.assistant-more-popper .el-dropdown-menu__item) {
  gap: 8px;
}

.message-list {
  flex: 1;
  min-height: 0;
  padding: 16px;
  overflow-y: auto;
  background: #f6f8fb;
  overscroll-behavior: contain;
  scroll-behavior: smooth;
}

.jump-bottom {
  position: absolute;
  left: 50%;
  bottom: 122px;
  transform: translateX(-50%);
  z-index: 5;
  height: 30px;
  border: 1px solid #c8d5e6;
  border-radius: 999px;
  background: #ffffff;
  color: #1d4ed8;
  padding: 0 12px;
  font-size: 12px;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.14);
  cursor: pointer;
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

.bubble.typing::after {
  content: '|';
  display: inline-block;
  margin-left: 2px;
  color: #2563eb;
  animation: caretBlink 0.9s steps(2, start) infinite;
}

@keyframes caretBlink {
  50% {
    opacity: 0;
  }
}

.message-stack {
  max-width: 324px;
  display: grid;
  gap: 8px;
}

.reference-list {
  display: grid;
  gap: 8px;
}

.map-visual-card {
  background: #ffffff;
  border: 1px solid #dbe4ef;
  border-radius: 10px;
  padding: 10px;
  box-shadow: 0 3px 12px rgba(15, 23, 42, 0.07);
}

.map-visual-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #edf1f7;
}

.map-visual-header span {
  display: block;
  color: #111827;
  font-size: 13px;
  font-weight: 700;
}

.map-visual-header small {
  display: block;
  margin-top: 2px;
  color: #667085;
  font-size: 11px;
}

.route-points {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 10px 0;
}

.route-points span {
  max-width: 100%;
  border: 1px solid #d7e3f2;
  border-radius: 999px;
  background: #f7fbff;
  color: #1d4ed8;
  padding: 4px 8px;
  font-size: 11px;
}

.route-options {
  display: grid;
  gap: 9px;
}

.route-option {
  border: 1px solid #e1e8f2;
  border-radius: 8px;
  padding: 9px;
  background: #fbfdff;
}

.route-option header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.route-option strong {
  color: #111827;
  font-size: 13px;
}

.route-option em,
.route-option p {
  margin: 0;
  color: #64748b;
  font-size: 11px;
  font-style: normal;
}

.route-option ol {
  display: grid;
  gap: 7px;
  margin: 8px 0 0;
  padding-left: 18px;
}

.route-option li {
  color: #334155;
  font-size: 12px;
}

.route-option li b,
.route-option li span,
.route-option li small {
  display: block;
}

.route-option li b {
  font-weight: 600;
}

.route-option li span,
.route-option li small {
  margin-top: 2px;
  color: #64748b;
  font-size: 11px;
}

.route-option button,
.nearby-group button,
.poi-list button {
  cursor: pointer;
}

.route-option > button {
  margin-top: 9px;
  width: 100%;
  height: 30px;
  border: 0;
  border-radius: 6px;
  background: #0f172a;
  color: #ffffff;
  font-size: 12px;
}

.nearby-section {
  margin-top: 10px;
  display: grid;
  gap: 7px;
}

.nearby-section h4 {
  margin: 0;
  color: #111827;
  font-size: 12px;
}

.nearby-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.nearby-group span {
  color: #64748b;
  font-size: 11px;
}

.nearby-group button {
  border: 1px solid #d7e3f2;
  border-radius: 999px;
  background: #ffffff;
  color: #1f2937;
  padding: 4px 7px;
  font-size: 11px;
}

.poi-list {
  display: grid;
  gap: 7px;
  margin-top: 9px;
}

.poi-list button {
  text-align: left;
  border: 1px solid #e1e8f2;
  border-radius: 8px;
  background: #fbfdff;
  padding: 8px;
}

.poi-list strong,
.poi-list span,
.poi-list em {
  display: block;
}

.poi-list strong {
  color: #111827;
  font-size: 12px;
}

.poi-list span,
.poi-list em {
  margin-top: 2px;
  color: #64748b;
  font-size: 11px;
  font-style: normal;
}

.reference-item {
  background: #ffffff;
  border: 1px solid #dbe4ef;
  border-radius: 8px;
  padding: 9px 10px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
}

.reference-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 5px;
  color: #1f2937;
  font-size: 12px;
  font-weight: 700;
}

.reference-title em {
  font-style: normal;
  color: #2563eb;
  font-weight: 600;
}

.reference-item p {
  margin: 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
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

.coding-model-bar {
  padding: 8px 12px 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid #eef2f7;
  background: #fbfdff;
}

.coding-model-bar span {
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}

.coding-model-select {
  flex: 1;
}

:global(.assistant-model-popper) {
  z-index: 12050 !important;
}

:global(.assistant-model-popper .el-select-dropdown__item) {
  max-width: 280px;
}

.composer {
  padding: 12px;
  display: flex;
  gap: 9px;
  align-items: flex-end;
  border-top: 1px solid #e5e7eb;
  background: #ffffff;
  position: relative;
}

.composer.dragging {
  background: #eef6ff;
  box-shadow: inset 0 0 0 2px #2563eb;
}

.file-input {
  display: none;
}

.composer-main {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 8px;
}

.attached-files {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  max-height: 86px;
  overflow-y: auto;
}

.attached-file {
  width: min(188px, 100%);
  min-height: 42px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 24px;
  align-items: center;
  gap: 7px;
  border: 1px solid #d9e2ef;
  border-radius: 8px;
  background: #f8fafc;
  padding: 5px 6px;
}

.attached-file img {
  width: 34px;
  height: 34px;
  object-fit: cover;
  border-radius: 6px;
  background: #ffffff;
}

.attached-file > .el-icon {
  width: 34px;
  height: 34px;
  border-radius: 6px;
  background: #ffffff;
  color: #2563eb;
}

.attached-file span {
  display: block;
  color: #1f2937;
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.attached-file em {
  display: block;
  margin-top: 2px;
  color: #667085;
  font-size: 11px;
  font-style: normal;
}

.attached-file button {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #667085;
  cursor: pointer;
}

.attached-file button:hover {
  background: #e5e7eb;
  color: #111827;
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
    max-width: calc(100vw - 170px);
  }

  .panel-actions .history-action span {
    display: none;
  }
}
</style>
