<template>
  <div class="page-container nl-db-page">
    <div class="header-banner">
      <div class="banner-content">
        <div class="banner-left">
          <div class="banner-icon">
            <el-icon :size="38"><Database /></el-icon>
          </div>
          <div class="banner-text">
            <h1>智能数据库助手</h1>
            <p>自然语言操作 · 用对话方式管理数据，让数据库操作更简单</p>
          </div>
        </div>
      </div>
      <div class="banner-decor">
        <span v-for="n in 5" :key="n" class="decor-dot"></span>
      </div>
    </div>

    <div class="main-content">
      <div class="qa-panel">
        <div ref="chatRef" class="chat-area">
          <div v-if="!messages.length" class="welcome">
            <div class="welcome-icon">
              <el-icon :size="72"><MessageSquare /></el-icon>
            </div>
            <h2>开始智能数据管理</h2>
            <p>用自然语言对学生、教师、班级、课程进行增删改查</p>
            <div class="welcome-example">
              <span @click="quickAsk('帮我查询所有学生')">查询学生</span>
              <span @click="quickAsk('新增一个学生，姓名张三，学号2024001')">新增学生</span>
              <span @click="quickAsk('修改学生ID为1的姓名为李四')">修改学生</span>
              <span @click="quickAsk('删除学生ID为1')">删除学生</span>
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
                <el-icon v-else :size="22"><Cpu /></el-icon>
              </div>
              <div class="msg-body">
                <div class="msg-head">
                  <span class="msg-who">{{ m.role === 'user' ? '你' : '智能助手' }}</span>
                  <span class="msg-time">{{ formatTime() }}</span>
                </div>
                <div class="msg-bubble">{{ m.content }}</div>

                <div v-if="m.toolCalls && m.toolCalls.length" class="tool-calls">
                  <div class="tool-calls-title">
                    <el-icon><Wrench /></el-icon>
                    <span>执行操作</span>
                  </div>
                  <div class="tool-calls-list">
                    <div
                      v-for="(tc, tci) in m.toolCalls"
                      :key="tci"
                      class="tool-call-item"
                    >
                      <span class="tool-name">{{ tc.tool }}</span>
                      <span class="tool-args">{{ JSON.stringify(tc.args) }}</span>
                    </div>
                  </div>
                </div>

                <div v-if="m.toolResults && m.toolResults.length" class="tool-results">
                  <div class="tool-results-title">
                    <el-icon><CircleCheck v-if="m.toolResults.every(r => r.success)" /><CircleClose v-else /></el-icon>
                    <span>操作结果</span>
                  </div>
                  <div class="tool-results-list">
                    <div
                      v-for="(result, ri) in m.toolResults"
                      :key="ri"
                      class="tool-result-item"
                      :class="result.success ? 'success' : 'error'"
                    >
                      <span class="result-icon">{{ result.success ? '✓' : '✗' }}</span>
                      <div class="result-content">
                        <span class="result-message">{{ result.message }}</span>
                        <div v-if="result.data && Object.keys(result.data).length" class="result-data">
                          <span class="data-label">数据：</span>
                          <span class="data-value">{{ JSON.stringify(result.data) }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="m.data && m.data.length" class="data-result">
                  <div class="data-result-title">
                    <el-icon><TableComponent /></el-icon>
                    <span>查询结果 · 共 {{ m.data.length }} 条</span>
                  </div>
                  <div class="data-table">
                    <table>
                      <thead>
                        <tr>
                          <th v-for="(key, ki) in Object.keys(m.data[0])" :key="ki">
                            {{ formatColumnName(key) }}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(row, ri) in m.data" :key="ri">
                          <td v-for="(key, ki) in Object.keys(row)" :key="ki">
                            {{ formatValue(row[key]) }}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </TransitionGroup>

          <div v-if="loading" class="msg-row assistant thinking-row">
            <div class="msg-avatar assistant">
              <el-icon :size="22"><Cpu /></el-icon>
            </div>
            <div class="msg-body">
              <div class="msg-head">
                <span class="msg-who">智能助手</span>
                <span class="msg-time">正在处理...</span>
              </div>
              <div class="msg-bubble thinking">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="thinking-text">正在分析请求，执行操作...</span>
              </div>
            </div>
          </div>
        </div>

        <div class="input-area">
          <div class="input-hint-bar">
            <span class="hint-text">支持：学生、教师、班级、课程的增删改查</span>
            <span class="hint-divider">|</span>
            <span class="hint-text">按 Enter 发送，Shift+Enter 换行</span>
          </div>
          <el-input
            v-model="inputText"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 5 }"
            placeholder="输入您的数据库操作请求..."
            resize="none"
            class="qa-input"
            @keydown="handleKeydown"
            :disabled="loading"
          />
          <div class="input-actions">
            <div class="input-left">
              <el-button plain @click="clearAll" :disabled="loading || !messages.length">
                <el-icon><Delete /></el-icon>
                <span>清空对话</span>
              </el-button>
              <el-button plain @click="loadHistory" :disabled="loading">
                <el-icon><History /></el-icon>
                <span>历史记录</span>
              </el-button>
            </div>
            <div class="input-right">
              <el-button type="primary" :loading="loading" class="send-btn" @click="sendQuestion">
                <el-icon><Send /></el-icon>
                <span>发送</span>
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <div class="side-panel">
        <div class="panel-section">
          <div class="section-title">
            <el-icon><Lightbulb /></el-icon>
            <span>使用示例</span>
          </div>
          <div class="example-list">
            <div
              v-for="(ex, idx) in examples"
              :key="idx"
              class="example-item"
              @click="quickAsk(ex.query)"
            >
              <el-icon class="example-icon" :size="16">
                <Search v-if="ex.type === '查询'" />
                <Plus v-else-if="ex.type === '新增'" />
                <Edit v-else-if="ex.type === '修改'" />
                <Delete v-else-if="ex.type === '删除'" />
              </el-icon>
              <span class="example-text">{{ ex.query }}</span>
              <span class="example-type" :class="ex.type">{{ ex.type }}</span>
            </div>
          </div>
        </div>

        <div class="panel-section">
          <div class="section-title">
            <el-icon><Lock /></el-icon>
            <span>权限说明</span>
          </div>
          <div class="permission-list">
            <div v-for="(perm, idx) in permissions" :key="idx" class="permission-item">
              <el-icon class="perm-icon" :size="16" :class="perm.allowed ? 'allowed' : 'denied'">
                <CircleCheck v-if="perm.allowed" />
                <CircleClose v-else />
              </el-icon>
              <span class="perm-desc">{{ perm.desc }}</span>
            </div>
          </div>
        </div>

        <div class="panel-section tips">
          <div class="section-title">
            <el-icon><InfoFilled /></el-icon>
            <span>温馨提示</span>
          </div>
          <ul class="tips-list">
            <li><el-icon :size="14"><AlertCircle /></el-icon><span>操作前请确保参数完整</span></li>
            <li><el-icon :size="14"><AlertCircle /></el-icon><span>删除操作会进行软删除</span></li>
            <li><el-icon :size="14"><AlertCircle /></el-icon><span>对话历史保留最近10轮</span></li>
            <li><el-icon :size="14"><AlertCircle /></el-icon><span>请使用清晰的自然语言描述</span></li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { nlDbChat, nlDbHistory, nlDbClear } from '@/api/nl-db'

interface ToolResult {
  success: boolean
  message: string
  data?: any
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: Array<{ tool: string; args: Record<string, any> }>
  toolResults?: ToolResult[]
  data?: Array<Record<string, any>>
}

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const loading = ref(false)
const chatRef = ref<HTMLElement | null>(null)

const examples = [
  { query: '查询所有学生', type: '查询' },
  { query: '查询姓名包含张的学生', type: '查询' },
  { query: '新增学生，姓名李四，学号2024002，性别男，班级ID为1', type: '新增' },
  { query: '修改学生ID为3的姓名为王五', type: '修改' },
  { query: '删除学生ID为5', type: '删除' },
  { query: '查询所有教师', type: '查询' },
  { query: '查询所有班级', type: '查询' },
  { query: '查询所有课程', type: '查询' },
]

const permissions = ref([
  { desc: '查询学生', allowed: true },
  { desc: '新增学生', allowed: true },
  { desc: '修改学生', allowed: true },
  { desc: '删除学生', allowed: true },
  { desc: '查询教师', allowed: true },
  { desc: '新增教师', allowed: false },
  { desc: '查询班级', allowed: true },
  { desc: '查询课程', allowed: true },
])

function formatTime(): string {
  const d = new Date()
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

function formatColumnName(name: string): string {
  const map: Record<string, string> = {
    id: 'ID',
    name: '姓名',
    student_no: '学号',
    employee_no: '工号',
    gender: '性别',
    clazz_id: '班级ID',
    department_id: '院系ID',
    status: '状态',
    code: '代码',
    grade: '年级',
    credit: '学分',
    teacher_id: '教师ID',
    counselor_id: '辅导员ID',
    position: '岗位',
    title: '职称',
    email: '邮箱',
    phone: '电话',
  }
  return map[name] || name
}

function formatValue(value: any): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') return String(value)
  if (value === 1 || value === '1') return '男'
  if (value === 2 || value === '2') return '女'
  return String(value)
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

function quickAsk(q: string) {
  inputText.value = q
  sendQuestion()
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
    const res: any = await nlDbChat(q)
    const data = res.data || {}
    const toolCalls = data.tool_calls || []
    const toolResults = data.tool_results || []
    
    let resultData = undefined
    for (const result of toolResults) {
      if (result.success && result.data && Array.isArray(result.data)) {
        resultData = result.data
        break
      }
    }
    
    messages.value.push({
      role: 'assistant',
      content: data.reply || '操作完成',
      toolCalls: toolCalls.length ? toolCalls : undefined,
      toolResults: toolResults.length ? toolResults : undefined,
      data: resultData,
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
  nlDbClear().catch(() => {})
  messages.value = []
}

async function loadHistory() {
  try {
    const res: any = await nlDbHistory()
    const history = res.data || []
    messages.value = history.map((item: any) => ({
      role: item.role as 'user' | 'assistant',
      content: item.content,
    }))
    scrollToBottom()
  } catch (e: any) {
    ElMessage.error('加载历史记录失败: ' + (e.message || e))
  }
}

onMounted(() => {})
</script>

<style scoped>
.nl-db-page {
  min-height: 100%;
  padding: 16px 0 24px;
  background: linear-gradient(180deg, #f0fdf4 0%, #ecfdf5 50%, #f0f9ff 100%);
}

.header-banner {
  position: relative;
  margin: 0 20px 20px;
  padding: 28px 36px;
  border-radius: 20px;
  background: linear-gradient(135deg, #065f46 0%, #166534 50%, #15803d 100%);
  color: #fff;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(6, 95, 70, 0.35);
}
.header-banner::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 80% 20%, rgba(163, 230, 53, 0.15), transparent 45%);
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
  background: linear-gradient(135deg, rgba(163, 230, 53, 0.25), rgba(163, 230, 53, 0.08));
  border: 1px solid rgba(163, 230, 53, 0.3);
  color: #a3e635;
  backdrop-filter: blur(8px);
}
.banner-text h1 {
  margin: 0 0 6px;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 2px;
}
.banner-text p {
  margin: 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  letter-spacing: 1px;
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
  background: rgba(163, 230, 53, 0.55);
}
.banner-decor .decor-dot:nth-child(3) {
  width: 18px;
  border-radius: 2px;
  background: rgba(163, 230, 53, 0.8);
}

.main-content {
  display: flex;
  gap: 20px;
  margin: 0 20px;
}

.qa-panel {
  flex: 1;
  background: #fff;
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.04);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  min-height: 650px;
}

.side-panel {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-section {
  background: #fff;
  border-radius: 16px;
  padding: 20px;
  border: 1px solid rgba(0, 0, 0, 0.04);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}
.panel-section.tips {
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  border-color: #10b981;
}

.section-title {
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

.example-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.example-item {
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
.example-item:hover {
  background: #fff;
  border-color: #065f46;
  transform: translateX(3px);
}
.example-icon {
  color: #6b7280;
  flex-shrink: 0;
}
.example-item:hover .example-icon {
  color: #065f46;
}
.example-text {
  flex: 1;
  font-size: 13px;
  color: #374151;
}
.example-type {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}
.example-type.查询 {
  background: #dbeafe;
  color: #1d4ed8;
}
.example-type.新增 {
  background: #dcfce7;
  color: #166534;
}
.example-type.修改 {
  background: #fef3c7;
  color: #b45309;
}
.example-type.删除 {
  background: #fee2e2;
  color: #991b1b;
}

.permission-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.permission-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #4b5563;
}
.perm-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}
.perm-icon.allowed {
  background: #dcfce7;
  color: #166534;
}
.perm-icon.denied {
  background: #fee2e2;
  color: #991b1b;
}

.tips-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.tips-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #065f46;
  margin-bottom: 8px;
}
.tips-list li:last-child {
  margin-bottom: 0;
}
.tips-list li .el-icon {
  color: #10b981;
  flex-shrink: 0;
}

.chat-area {
  flex: 1;
  padding: 32px 36px 20px;
  overflow-y: auto;
  max-height: 580px;
  background: linear-gradient(180deg, #fff 0%, #fafaf8 100%);
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

.welcome {
  text-align: center;
  padding: 60px 20px;
}
.welcome-icon {
  width: 120px;
  height: 120px;
  margin: 0 auto 28px;
  border-radius: 50%;
  background: radial-gradient(circle, #d1fae5 0%, #ecfdf5 100%);
  color: #10b981;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 40px rgba(16, 185, 129, 0.2);
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
  background: #065f46;
  border-color: #065f46;
  color: #fff;
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(6, 95, 70, 0.25);
}

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
  background: linear-gradient(135deg, #34d399 0%, #10b981 100%);
  color: #fff;
}
.msg-avatar.assistant {
  background: linear-gradient(135deg, #065f46 0%, #166534 100%);
  color: #a3e635;
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
}
.msg-row.user .msg-bubble {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: #fff;
  border-top-right-radius: 4px;
  box-shadow: 0 4px 16px rgba(16, 185, 129, 0.25);
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

.tool-calls {
  margin-top: 14px;
  padding: 14px;
  border-radius: 12px;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  border: 1px solid #bfdbfe;
}

.tool-results {
  margin-top: 14px;
  padding: 14px;
  border-radius: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
}
.tool-results-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 10px;
}
.tool-results-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.tool-result-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
}
.tool-result-item.success {
  background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
  border: 1px solid #86efac;
}
.tool-result-item.error {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  border: 1px solid #fca5a5;
}
.result-icon {
  font-size: 16px;
  font-weight: 700;
  flex-shrink: 0;
}
.tool-result-item.success .result-icon {
  color: #166534;
}
.tool-result-item.error .result-icon {
  color: #991b1b;
}
.result-content {
  flex: 1;
}
.result-message {
  font-size: 13.5px;
  color: #374151;
  font-weight: 500;
}
.result-data {
  margin-top: 6px;
  font-size: 12.5px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.data-label {
  color: #6b7280;
}
.data-value {
  color: #065f46;
  font-family: 'Courier New', monospace;
  background: rgba(6, 95, 70, 0.08);
  padding: 4px 8px;
  border-radius: 6px;
}
.tool-calls-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #1d4ed8;
  margin-bottom: 10px;
}
.tool-calls-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tool-call-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.tool-name {
  font-weight: 600;
  color: #1e40af;
  background: rgba(30, 64, 175, 0.1);
  padding: 4px 10px;
  border-radius: 6px;
}
.tool-args {
  color: #4b5563;
  font-family: 'Courier New', monospace;
}

.data-result {
  margin-top: 14px;
  padding: 14px;
  border-radius: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
}
.data-result-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 12px;
}
.data-table {
  overflow-x: auto;
}
.data-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.data-table th,
.data-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
}
.data-table th {
  background: #fff;
  font-weight: 600;
  color: #374151;
}
.data-table tr:hover td {
  background: #fff;
}

.input-area {
  padding: 18px 24px 20px;
  border-top: 1px solid #e5e7eb;
  background: #fff;
}
.input-hint-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.hint-text {
  font-size: 12px;
  color: #9ca3af;
}
.hint-divider {
  color: #e5e7eb;
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
  border-color: #065f46;
  background: #fff;
  box-shadow: 0 0 0 4px rgba(6, 95, 70, 0.08);
}
.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
}
.input-left {
  display: flex;
  gap: 10px;
}
.send-btn {
  background: linear-gradient(135deg, #065f46 0%, #166534 100%) !important;
  border: none !important;
  padding: 10px 24px !important;
  border-radius: 12px !important;
  font-weight: 500 !important;
  box-shadow: 0 4px 12px rgba(6, 95, 70, 0.25);
  transition: all 0.2s;
}
.send-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(6, 95, 70, 0.35);
}

@media screen and (max-width: 1100px) {
  .side-panel {
    display: none;
  }
}
</style>