<template>
  <div class="page-container rag-page">
    <!-- 顶部标题栏 -->
    <div class="header-banner">
      <div class="banner-content">
        <div class="banner-left">
          <div class="banner-icon">
            <el-icon :size="38"><Reading /></el-icon>
          </div>
          <div class="banner-text">
            <h1>四大名著 · 智能问答</h1>
            <p>基于向量检索 · 与千古文章对话，寻回那些熟悉的情节与人物</p>
          </div>
        </div>
        <div class="banner-right">
          <el-tag :type="healthOk ? 'success' : 'info'" effect="dark" round size="large" class="status-tag">
            <span class="status-dot" :class="{ ok: healthOk }"></span>
            {{ healthOk ? '检索服务运行中' : '初始化中...' }}
          </el-tag>
        </div>
      </div>
      <!-- 装饰纹样 -->
      <div class="banner-decor">
        <span v-for="n in 7" :key="n" class="decor-dot"></span>
      </div>
    </div>

    <el-row :gutter="20" class="main-row">
      <!-- 左侧：书籍筛选 + 快捷提问 -->
      <el-col :span="6">
        <!-- 书籍知识库 -->
        <div class="side-panel">
          <div class="panel-title">
            <el-icon><Collection /></el-icon>
            <span>选择典籍</span>
            <span class="panel-sub">{{ books.length }} 部</span>
          </div>
          <div class="book-list" v-loading="booksLoading">
            <div
              v-for="book in books"
              :key="book.code"
              class="book-card"
              :class="[
                getBookClass(book.code),
                { active: selectedBooks.includes(book.code) }
              ]"
              @click="toggleBook(book.code)"
            >
              <div class="book-card-top">
                <div class="book-cover">
                  <span class="cover-text">{{ getBookShort(book.name) }}</span>
                </div>
                <div class="book-info">
                  <div class="book-name">{{ book.name }}</div>
                  <div class="book-author">{{ book.author }} · {{ book.dynasty }}</div>
                </div>
              </div>
              <div class="book-card-bottom">
                <el-tag size="small" effect="plain" round>
                  {{ book.total_chapters }} 回 · {{ book.total_sections }} 段
                </el-tag>
                <el-icon v-if="selectedBooks.includes(book.code)" class="check-icon"><CircleCheck /></el-icon>
              </div>
            </div>
          </div>
        </div>

        <!-- 快捷提问 -->
        <div class="side-panel">
          <div class="panel-title">
            <el-icon><MagicStick /></el-icon>
            <span>试试这些</span>
          </div>
          <div class="quick-list">
            <div
              v-for="(q, idx) in quickQuestions"
              :key="idx"
              class="quick-item"
              @click="quickAsk(q)"
            >
              <span class="quick-idx">{{ String(idx + 1).padStart(2, '0') }}</span>
              <span class="quick-text">{{ q }}</span>
              <el-icon class="quick-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>

        <!-- 小提示 -->
        <div class="side-panel tips-panel">
          <div class="tips-icon">
            <el-icon :size="18"><InfoFilled /></el-icon>
          </div>
          <div class="tips-content">
            <div class="tips-title">使用小提示</div>
            <div class="tips-text">
              · 点击书名可多选，限定检索范围<br/>
              · 可提问人物、情节、回目、人物关系等<br/>
              · 回答下方附参考出处，不默认展开大段原文
            </div>
          </div>
        </div>
      </el-col>

      <!-- 右侧：问答主区 -->
      <el-col :span="18">
        <div class="qa-panel">
          <!-- 对话区 -->
          <div ref="chatRef" class="chat-area">
            <div v-if="!messages.length" class="welcome">
              <div class="welcome-icon">
                <el-icon :size="72"><ChatLineSquare /></el-icon>
              </div>
              <h2>开始你与古典文学的对话</h2>
              <p>输入你关心的问题，例如「诸葛亮空城计是哪一回？」「林黛玉葬花讲了什么？」</p>
              <div class="welcome-example">
                <span @click="quickAsk('关羽过五关斩六将经过哪些关隘？')">关羽过五关斩六将</span>
                <span @click="quickAsk('武松打虎在什么地方？')">武松打虎</span>
                <span @click="quickAsk('贾宝玉和薛宝钗最终结局如何？')">宝玉宝钗结局</span>
              </div>
            </div>

            <TransitionGroup name="msg-fade">
              <div
                v-for="(m, idx) in messages"
                :key="idx"
                class="msg-row"
                :class="m.role"
              >
                <div class="msg-avatar" :class="m.role">
                  <el-icon v-if="m.role === 'user'" :size="22"><User /></el-icon>
                  <el-icon v-else :size="22"><Reading /></el-icon>
                </div>
                <div class="msg-body">
                  <div class="msg-head">
                    <span class="msg-who">{{ m.role === 'user' ? '你' : '名著助手' }}</span>
                    <span class="msg-time">{{ formatTime() }}</span>
                  </div>
                  <div class="msg-bubble">{{ m.content }}</div>

                  <!-- 检索来源（只在 assistant 消息展示） -->
                  <div v-if="m.sources && m.sources.length" class="sources-block">
                    <div class="sources-title">
                      <el-icon><DocumentCopy /></el-icon>
                      <span>参考出处 · 共 {{ m.sources.length }} 条</span>
                      <span class="sources-line"></span>
                    </div>
                    <div class="sources-list">
                      <div
                        v-for="(s, si) in m.sources"
                        :key="si"
                        class="source-card"
                        :class="getBookClass(s.book_code)"
                      >
                        <div class="source-head">
                          <el-tag size="small" effect="dark" round class="source-book-tag">
                            {{ s.book_name }}
                          </el-tag>
                          <span class="source-chapter">第 {{ s.chapter_no }} 回</span>
                          <span class="source-title">《{{ s.chapter_title }}》</span>
                          <span class="source-score">
                            <el-icon><TrendCharts /></el-icon>
                            {{ (s.score * 100).toFixed(0) }}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </TransitionGroup>

            <div v-if="loading" class="msg-row assistant thinking-row">
              <div class="msg-avatar assistant">
                <el-icon :size="22"><Reading /></el-icon>
              </div>
              <div class="msg-body">
                <div class="msg-head">
                  <span class="msg-who">名著助手</span>
                  <span class="msg-time">正在检索...</span>
                </div>
                <div class="msg-bubble thinking">
                  <span class="typing-dot"></span>
                  <span class="typing-dot"></span>
                  <span class="typing-dot"></span>
                  <span class="thinking-text">正在翻阅典籍，寻找答案...</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 输入区 -->
          <div class="input-area">
            <div class="input-filter" v-if="selectedBooks.length">
              <el-tag
                v-for="code in selectedBooks"
                :key="code"
                class="filter-tag"
                :class="getBookClass(code)"
                round
                closable
                @close="toggleBook(code)"
              >
                {{ getBookNameByCode(code) }}
              </el-tag>
              <span class="filter-tip">已限定检索范围（点击 × 可取消）</span>
            </div>
            <el-input
              v-model="inputText"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 5 }"
              placeholder="向四大名著提问... 例如「刘备三顾茅庐请的是谁？」"
              resize="none"
              class="qa-input"
              @keydown="handleKeydown"
              :disabled="loading"
            />
            <div class="input-actions">
              <div class="input-left">
                <span class="input-hint">Enter 发送 · Shift+Enter 换行</span>
              </div>
              <div class="input-right">
                <el-button plain @click="clearAll" :disabled="loading || !messages.length">
                  <el-icon><Delete /></el-icon>
                  <span>清空</span>
                </el-button>
                <el-button type="primary" :loading="loading" class="send-btn" @click="sendQuestion">
                  <el-icon><Promotion /></el-icon>
                  <span>发送</span>
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { askRag, listRagBooks, ragHealth } from '@/api/rag'
import type { RagBook, RagSource } from '@/api/rag'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: RagSource[]
}

const books = ref<RagBook[]>([])
const booksLoading = ref(false)
const selectedBooks = ref<string[]>([])
const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const loading = ref(false)
const chatRef = ref<HTMLElement | null>(null)

const healthOk = ref(false)
const healthLoading = ref(false)

const quickQuestions = [
  '孙悟空三打白骨精是哪一回？',
  '关羽过五关斩六将经过哪些关隘？',
  '林黛玉焚稿断痴情讲了什么？',
  '武松打虎在什么地方？',
  '诸葛亮空城计是哪一回？',
  '梁山泊英雄排座次有多少好汉？',
  '桃园三结义是哪三人？',
  '贾宝玉和薛宝钗最终结局如何？',
]

// ===== 书籍配色映射 =====
function getBookClass(code: string): string {
  const map: Record<string, string> = {
    'xiyouji': 'book-xiyou',
    'sanguo': 'book-sanguo',
    'shuihu': 'book-shuihu',
    'honglou': 'book-honglou',
  }
  return map[code] || 'book-default'
}

function getBookShort(name: string): string {
  if (name.includes('西游记')) return '西游'
  if (name.includes('三国演义')) return '三国'
  if (name.includes('水浒传')) return '水浒'
  if (name.includes('红楼梦')) return '红楼'
  return name.substring(0, 2)
}

function getBookNameByCode(code: string): string {
  const b = books.value.find((x) => x.code === code)
  return b ? b.name : code
}

function formatTime(): string {
  const d = new Date()
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

// ===== 生命周期 =====
onMounted(async () => {
  await loadBooks()
  await checkHealth()
})

// ===== 方法 =====
function toggleBook(code: string) {
  const idx = selectedBooks.value.indexOf(code)
  if (idx >= 0) {
    selectedBooks.value.splice(idx, 1)
  } else {
    selectedBooks.value.push(code)
  }
}

async function loadBooks() {
  booksLoading.value = true
  try {
    const res: any = await listRagBooks()
    books.value = res.data || []
  } catch (e: any) {
    ElMessage.error('加载知识库失败: ' + (e.message || e))
  } finally {
    booksLoading.value = false
  }
}

async function checkHealth() {
  healthLoading.value = true
  try {
    const res: any = await ragHealth()
    healthOk.value = res.data?.milvus === 'ok' || res.data?.status === 'ok'
  } catch {
    healthOk.value = false
  } finally {
    healthLoading.value = false
  }
}

function quickAsk(q: string) {
  inputText.value = q
  sendQuestion()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendQuestion()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatRef.value) {
      chatRef.value.scrollTop = chatRef.value.scrollHeight
    }
  })
}

async function sendQuestion() {
  const q = inputText.value.trim()
  if (!q) return
  if (loading.value) return

  messages.value.push({ role: 'user', content: q })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const res: any = await askRag(
      q,
      selectedBooks.value.length ? selectedBooks.value : null,
      5,
    )
    const data = res.data || {}
    messages.value.push({
      role: 'assistant',
      content: data.answer || '抱歉，未能生成回答。',
      sources: data.sources || [],
    })
  } catch (e: any) {
    messages.value.push({
      role: 'assistant',
      content: '出错了: ' + (e.message || e),
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function clearAll() {
  messages.value = []
}
</script>

<style scoped>
/* ========= 基础 ========= */
.rag-page {
  min-height: 100%;
  padding: 16px 0 24px;
  background:
    radial-gradient(1200px 600px at 10% -10%, rgba(255, 237, 213, 0.55), transparent 60%),
    radial-gradient(1000px 500px at 110% 10%, rgba(219, 234, 254, 0.5), transparent 60%),
    linear-gradient(180deg, #fbf9f5 0%, #f3efe7 100%);
}

/* ========= 顶部 Banner ========= */
.header-banner {
  position: relative;
  margin: 0 20px 20px;
  padding: 28px 36px;
  border-radius: 20px;
  background:
    linear-gradient(135deg, #1e3a5f 0%, #2d5a8e 50%, #14532d 100%);
  color: #fff;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(30, 58, 95, 0.35), 0 2px 6px rgba(0, 0, 0, 0.06);
}
.header-banner::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 80% 20%, rgba(255, 220, 150, 0.15), transparent 45%),
    radial-gradient(circle at 10% 80%, rgba(150, 200, 255, 0.18), transparent 50%);
  pointer-events: none;
}
.banner-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  z-index: 1;
}
.banner-left {
  display: flex;
  align-items: center;
  gap: 20px;
}
.banner-icon {
  width: 72px;
  height: 72px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(255, 220, 150, 0.25), rgba(255, 220, 150, 0.08));
  border: 1px solid rgba(255, 220, 150, 0.3);
  color: #ffe9bf;
  backdrop-filter: blur(8px);
}
.banner-text h1 {
  margin: 0 0 6px;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 2px;
  background: linear-gradient(90deg, #fff, #ffe9bf);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.banner-text p {
  margin: 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  letter-spacing: 1px;
}
.status-tag {
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.14) !important;
  border: 1px solid rgba(255, 255, 255, 0.25) !important;
  color: #fff !important;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.status-tag .status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #9ca3af;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.15);
  animation: pulse 2s infinite;
}
.status-tag .status-dot.ok {
  background: #4ade80;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.banner-decor {
  position: absolute;
  bottom: 10px;
  left: 36px;
  display: flex;
  gap: 8px;
  z-index: 1;
}
.banner-decor .decor-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 220, 150, 0.55);
}
.banner-decor .decor-dot:nth-child(4) {
  width: 18px;
  border-radius: 2px;
  background: rgba(255, 220, 150, 0.8);
}

/* ========= 主体布局 ========= */
.main-row {
  margin: 0 20px !important;
}

/* ========= 左侧卡片 ========= */
.side-panel {
  background: #fff;
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 16px;
  border: 1px solid rgba(0, 0, 0, 0.04);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  color: #1f2937;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #e5e7eb;
}
.panel-title .panel-sub {
  margin-left: auto;
  font-size: 12px;
  color: #9ca3af;
  font-weight: 400;
}

/* ========= 书籍卡片 ========= */
.book-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.book-card {
  padding: 14px;
  border-radius: 12px;
  border: 1.5px solid #e5e7eb;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  background: #fafafa;
}
.book-card:hover {
  transform: translateX(3px);
  background: #fff;
}
.book-card.active {
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
  background: #fff;
}
.book-card-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.book-cover {
  width: 48px;
  height: 56px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.2),
    2px 3px 8px rgba(0, 0, 0, 0.2),
    -2px 0 0 0 rgba(0, 0, 0, 0.08);
}
.book-cover .cover-text {
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 1px;
  writing-mode: vertical-rl;
  text-orientation: upright;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}
.book-info .book-name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 4px;
}
.book-info .book-author {
  font-size: 12px;
  color: #6b7280;
}
.book-card-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.book-card .check-icon {
  color: #10b981;
  font-size: 16px;
}

/* 各部书籍配色 */
.book-xiyou {
  border-color: #fde68a;
}
.book-xiyou .book-cover,
.book-xiyou.active,
.book-xiyou .source-book-tag,
.book-xiyou .filter-tag {
  background: linear-gradient(160deg, #f59e0b 0%, #d97706 100%) !important;
}
.book-xiyou:hover { border-color: #f59e0b; }
.book-xiyou.active { box-shadow: 0 6px 20px rgba(245, 158, 11, 0.3); }

.book-sanguo {
  border-color: #fecaca;
}
.book-sanguo .book-cover,
.book-sanguo.active,
.book-sanguo .source-book-tag,
.book-sanguo .filter-tag {
  background: linear-gradient(160deg, #dc2626 0%, #991b1b 100%) !important;
}
.book-sanguo:hover { border-color: #dc2626; }
.book-sanguo.active { box-shadow: 0 6px 20px rgba(220, 38, 38, 0.3); }

.book-shuihu {
  border-color: #a7f3d0;
}
.book-shuihu .book-cover,
.book-shuihu.active,
.book-shuihu .source-book-tag,
.book-shuihu .filter-tag {
  background: linear-gradient(160deg, #059669 0%, #065f46 100%) !important;
}
.book-shuihu:hover { border-color: #059669; }
.book-shuihu.active { box-shadow: 0 6px 20px rgba(5, 150, 105, 0.3); }

.book-honglou {
  border-color: #fbcfe8;
}
.book-honglou .book-cover,
.book-honglou.active,
.book-honglou .source-book-tag,
.book-honglou .filter-tag {
  background: linear-gradient(160deg, #db2777 0%, #9d174d 100%) !important;
}
.book-honglou:hover { border-color: #db2777; }
.book-honglou.active { box-shadow: 0 6px 20px rgba(219, 39, 119, 0.3); }

.book-default .book-cover,
.book-default.active,
.book-default .source-book-tag,
.book-default .filter-tag {
  background: linear-gradient(160deg, #6366f1 0%, #4338ca 100%) !important;
}

/* ========= 快捷提问 ========= */
.quick-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.quick-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f9fafb;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.quick-item:hover {
  background: #fff;
  border-color: #1e3a5f;
  transform: translateX(3px);
  box-shadow: 0 2px 8px rgba(30, 58, 95, 0.12);
}
.quick-idx {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 600;
  min-width: 22px;
  font-family: 'Courier New', monospace;
}
.quick-item:hover .quick-idx {
  color: #1e3a5f;
}
.quick-text {
  flex: 1;
  font-size: 13px;
  color: #374151;
  line-height: 1.5;
}
.quick-arrow {
  color: #9ca3af;
  font-size: 14px;
  transition: all 0.2s;
  opacity: 0;
}
.quick-item:hover .quick-arrow {
  opacity: 1;
  color: #1e3a5f;
  transform: translateX(3px);
}

/* ========= 小提示 ========= */
.tips-panel {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border: none;
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.tips-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(146, 64, 14, 0.15);
  color: #92400e;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.tips-title {
  font-size: 13px;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 6px;
}
.tips-text {
  font-size: 12px;
  color: #78350f;
  line-height: 1.8;
}

/* ========= 问答主区 ========= */
.qa-panel {
  background: #fff;
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.04);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  min-height: 650px;
}

.chat-area {
  flex: 1;
  padding: 32px 36px 20px;
  overflow-y: auto;
  max-height: 620px;
  background:
    linear-gradient(180deg, #fff 0%, #fafaf8 100%);
}
.chat-area::-webkit-scrollbar {
  width: 6px;
}
.chat-area::-webkit-scrollbar-track {
  background: transparent;
}
.chat-area::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}
.chat-area::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}

/* ========= 欢迎页 ========= */
.welcome {
  text-align: center;
  padding: 60px 20px;
}
.welcome-icon {
  width: 120px;
  height: 120px;
  margin: 0 auto 28px;
  border-radius: 50%;
  background:
    radial-gradient(circle, #ede9fe 0%, #f5f3ff 100%);
  color: #6366f1;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 40px rgba(99, 102, 241, 0.2);
  animation: float 3s ease-in-out infinite;
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}
.welcome h2 {
  margin: 0 0 12px;
  font-size: 22px;
  color: #1f2937;
  letter-spacing: 1px;
}
.welcome p {
  margin: 0 0 24px;
  color: #6b7280;
  font-size: 14px;
}
.welcome-example {
  display: flex;
  gap: 10px;
  justify-content: center;
  flex-wrap: wrap;
}
.welcome-example span {
  padding: 8px 18px;
  background: #fff;
  border: 1.5px solid #e5e7eb;
  border-radius: 20px;
  font-size: 13px;
  color: #4b5563;
  cursor: pointer;
  transition: all 0.2s;
}
.welcome-example span:hover {
  background: #1e3a5f;
  border-color: #1e3a5f;
  color: #fff;
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(30, 58, 95, 0.25);
}

/* ========= 消息 ========= */
.msg-fade-enter-active,
.msg-fade-leave-active {
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.msg-fade-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.msg-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.msg-row {
  display: flex;
  gap: 14px;
  margin-bottom: 28px;
}
.msg-row.user {
  flex-direction: row-reverse;
}
.msg-avatar {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}
.msg-avatar.user {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: #fff;
}
.msg-avatar.assistant {
  background: linear-gradient(135deg, #1e3a5f 0%, #065f46 100%);
  color: #ffd966;
}

.msg-body {
  max-width: 78%;
}
.msg-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.msg-row.user .msg-head {
  justify-content: flex-end;
}
.msg-who {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}
.msg-time {
  font-size: 11px;
  color: #9ca3af;
}

.msg-bubble {
  padding: 14px 18px;
  border-radius: 16px;
  font-size: 14.5px;
  line-height: 1.85;
  word-break: break-word;
  white-space: pre-wrap;
  position: relative;
}
.msg-row.user .msg-bubble {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: #fff;
  border-top-right-radius: 4px;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.25);
}
.msg-row.assistant .msg-bubble {
  background: #fff;
  color: #1f2937;
  border-top-left-radius: 4px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
}

.msg-bubble.thinking {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 18px 22px;
}
.typing-dot {
  width: 7px;
  height: 7px;
  background: #9ca3af;
  border-radius: 50%;
  animation: typing 1.2s infinite ease-in-out;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}
.thinking-text {
  font-size: 13px;
  color: #9ca3af;
  margin-left: 6px;
}

/* ========= 参考段落 ========= */
.sources-block {
  margin-top: 16px;
  padding: 20px;
  border-radius: 14px;
  background:
    linear-gradient(135deg, #fffbeb 0%, #fef9e7 100%);
  border: 1px solid #fde68a;
  box-shadow: inset 0 2px 0 rgba(255, 255, 255, 0.8);
  position: relative;
}
.sources-block::before {
  content: '';
  position: absolute;
  top: 0;
  left: 20px;
  right: 20px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #d97706, transparent);
  opacity: 0.3;
}
.sources-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 14px;
}
.sources-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, rgba(146, 64, 14, 0.25), transparent);
  margin-left: 8px;
}
.sources-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.source-card {
  background: #fff;
  border-radius: 10px;
  padding: 12px 14px;
  border-left: 3px solid #d1d5db;
  transition: all 0.2s;
}
.source-card.book-xiyou { border-left-color: #f59e0b; }
.source-card.book-sanguo { border-left-color: #dc2626; }
.source-card.book-shuihu { border-left-color: #059669; }
.source-card.book-honglou { border-left-color: #db2777; }

.source-card:hover {
  transform: translateX(2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}
.source-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.source-book-tag {
  border: none !important;
  padding: 2px 10px !important;
  font-size: 11px !important;
  color: #fff !important;
}
.source-chapter {
  font-size: 12px;
  color: #1f2937;
  font-weight: 500;
}
.source-title {
  font-size: 12px;
  color: #4b5563;
  font-style: italic;
}
.source-score {
  margin-left: auto;
  font-size: 11px;
  color: #92400e;
  background: rgba(217, 119, 6, 0.1);
  padding: 3px 8px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.source-quote {
  padding: 0 4px;
  line-height: 1.8;
  position: relative;
}
.quote-mark {
  font-size: 22px;
  font-weight: 700;
  color: #d97706;
  font-family: 'Courier New', monospace;
  line-height: 1;
  opacity: 0.7;
}
.quote-mark.left {
  margin-right: 2px;
  vertical-align: top;
}
.quote-mark.right {
  margin-left: 2px;
  vertical-align: bottom;
}
.source-text {
  font-size: 13px;
  color: #4b5563;
  font-family: 'Georgia', 'STKaiti', 'KaiTi', serif;
}

/* ========= 输入区 ========= */
.input-area {
  padding: 18px 24px 20px;
  border-top: 1px solid #e5e7eb;
  background: #fff;
}
.input-filter {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.filter-tag {
  border: none !important;
  color: #fff !important;
  font-size: 12px !important;
  padding: 4px 10px !important;
}
.filter-tip {
  font-size: 12px;
  color: #9ca3af;
  margin-left: 4px;
}
.qa-input :deep(.el-textarea__inner) {
  border-radius: 14px;
  border: 1.5px solid #e5e7eb;
  padding: 14px 16px;
  font-size: 14.5px;
  transition: all 0.2s;
  background: #fafafa;
}
.qa-input :deep(.el-textarea__inner):focus {
  border-color: #1e3a5f;
  background: #fff;
  box-shadow: 0 0 0 4px rgba(30, 58, 95, 0.08);
}
.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
}
.input-left .input-hint {
  font-size: 11px;
  color: #9ca3af;
}
.input-right {
  display: flex;
  gap: 10px;
}
.send-btn {
  background: linear-gradient(135deg, #1e3a5f 0%, #065f46 100%) !important;
  border: none !important;
  padding: 10px 24px !important;
  border-radius: 12px !important;
  font-weight: 500 !important;
  box-shadow: 0 4px 12px rgba(30, 58, 95, 0.25);
  transition: all 0.2s;
}
.send-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(30, 58, 95, 0.35);
}

/* ========= 响应式：窄屏适配 ========= */
@media screen and (max-width: 1100px) {
  .main-row > .el-col:first-child {
    width: 28% !important;
  }
  .main-row > .el-col:last-child {
    width: 72% !important;
  }
}
</style>
