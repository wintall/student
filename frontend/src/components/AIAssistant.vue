<template>
  <div class="ai-assistant-container">
    <!-- 浮动气泡按钮 -->
    <div class="ai-bubble" @click="togglePanel" :class="{ active: visible }">
      <el-icon :size="28">
        <ChatDotRound v-if="!visible" />
        <Close v-else />
      </el-icon>
    </div>

    <!-- 聊天面板 -->
    <transition name="slide">
      <div v-if="visible" class="ai-panel">
        <div class="ai-panel-header">
          <div class="header-left">
            <el-icon :size="22" color="#fff"><MagicStick /></el-icon>
            <span>智能助手</span>
          </div>
          <div class="header-actions">
            <el-button text @click="clearContext">
              <el-icon><Delete /></el-icon> 清空
            </el-button>
            <el-icon :size="20" @click="visible = false" style="cursor:pointer;"><Close /></el-icon>
          </div>
        </div>

        <!-- 消息区 -->
        <div class="ai-panel-messages" ref="messagesRef">
          <div v-if="!messages.length" class="welcome">
            <div class="welcome-icon">✨</div>
            <p>你好！我是你的智能助手</p>
            <p class="welcome-tips">可以帮你：</p>
            <div class="quick-chips">
              <div class="chip" @click="sendMessage('查看我的成绩')">查看我的成绩</div>
              <div class="chip" @click="sendMessage('最近有什么校园公告？')">最新公告</div>
              <div class="chip" @click="sendMessage('天气怎么样？')">查询天气</div>
              <div class="chip" @click="sendMessage('帮我列一个学习计划')">闲聊</div>
            </div>
          </div>

          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="message-row"
            :class="msg.role"
          >
            <div class="message-avatar">
              <el-icon v-if="msg.role === 'assistant'" :size="20"><MagicStick /></el-icon>
              <el-icon v-else :size="20"><User /></el-icon>
            </div>
            <div class="message-bubble" v-html="formatMessage(msg.content)"></div>
          </div>

          <div v-if="loading" class="message-row assistant">
            <div class="message-avatar">
              <el-icon :size="20"><MagicStick /></el-icon>
            </div>
            <div class="message-bubble thinking">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="ai-panel-input">
          <el-input
            v-model="inputText"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 3 }"
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            resize="none"
            @keydown="handleKeydown"
            :disabled="loading"
          />
          <el-button
            type="primary"
            :loading="loading"
            circle
            @click="sendMessage"
            style="margin-left: 8px;"
          >
            <el-icon><Promotion /></el-icon>
          </el-button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { chatWithAi, clearAiContext } from '@/api/ai'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

const visible = ref(false)
const inputText = ref('')
const messages = ref<ChatMessage[]>([])
const loading = ref(false)
const messagesRef = ref<HTMLElement | null>(null)

function togglePanel() {
  visible.value = !visible.value
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function formatMessage(text: string) {
  if (!text) return ''
  // 换行支持
  return text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')
}

async function sendMessage(presetText?: string) {
  const text = (presetText || inputText.value).trim()
  if (!text) return
  if (loading.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  scrollToBottom()

  loading.value = true
  try {
    const res = await chatWithAi(text)
    const reply = (res.data?.reply) || (typeof res.data === 'string' ? res.data : '') || '抱歉，没有收到回复'
    messages.value.push({ role: 'assistant', content: reply })
  } catch (e: any) {
    messages.value.push({
      role: 'assistant',
      content: e?.message || '服务暂时不可用，请稍后再试',
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
    await clearAiContext()
    messages.value = []
    ElMessage.success('对话上下文已清空')
  } catch (e) {
    messages.value = []
  }
}

onMounted(() => {
  scrollToBottom()
})
</script>

<style scoped>
.ai-assistant-container {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 9999;
}

.ai-bubble {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.ai-bubble:hover {
  transform: scale(1.08) translateY(-2px);
  box-shadow: 0 12px 32px rgba(102, 126, 234, 0.5);
}

.ai-bubble.active {
  transform: rotate(90deg) scale(0.95);
  background: linear-gradient(135deg, #f56c6c 0%, #e6a23c 100%);
}

.ai-panel {
  width: 380px;
  height: 540px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  margin-bottom: 16px;
  overflow: hidden;
}

.slide-enter-active, .slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-enter-from, .slide-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}

.ai-panel-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  padding: 14px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex; align-items: center; gap: 10px;
  font-size: 15px; font-weight: 600;
}

.header-actions {
  display: flex; align-items: center; gap: 12px; font-size: 13px;
}
.header-actions .el-button { color: #fff; padding: 0; }

.ai-panel-messages {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  background: #f7f9fc;
}

.welcome {
  text-align: center;
  padding: 32px 16px;
  color: #606266;
}

.welcome-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.welcome p {
  margin: 4px 0;
  font-size: 14px;
}

.welcome-tips {
  color: #909399 !important;
  font-size: 13px !important;
  margin-top: 16px !important;
}

.quick-chips {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.chip {
  background: #fff;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  color: #667eea;
  border: 1px solid rgba(102, 126, 234, 0.2);
  cursor: pointer;
  transition: all 0.2s;
}

.chip:hover {
  background: #667eea;
  color: #fff;
  transform: translateY(-1px);
}

.message-row {
  display: flex;
  margin-bottom: 14px;
  align-items: flex-start;
  gap: 10px;
}

.message-row.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
}

.message-row.assistant .message-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.message-row.user .message-avatar {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.message-bubble {
  max-width: 260px;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.message-row.assistant .message-bubble {
  background: #fff;
  color: #303133;
  border-top-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.message-row.user .message-bubble {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border-top-right-radius: 4px;
}

.message-bubble.thinking {
  display: flex;
  gap: 4px;
  padding: 14px;
}

.thinking .dot {
  width: 6px;
  height: 6px;
  background: #c0c4cc;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.thinking .dot:nth-child(1) { animation-delay: -0.32s; }
.thinking .dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.5); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

.ai-panel-input {
  padding: 12px;
  border-top: 1px solid #ebeef5;
  background: #fff;
  display: flex;
  align-items: flex-end;
}

.ai-panel-input :deep(.el-textarea__inner) {
  border-radius: 10px;
  padding: 8px 12px;
}
</style>
