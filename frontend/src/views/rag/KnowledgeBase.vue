<template>
  <div class="page-container knowledge-page">
    <div class="page-shell">
      <section class="toolbar">
        <div>
          <h1>综合知识库</h1>
          <p>导入文本、Markdown、PDF 或项目内文件，供校园助手持续问答。</p>
        </div>
        <div class="toolbar-actions">
          <el-input v-model="keyword" clearable placeholder="搜索知识库" @keyup.enter="fetchBases">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" @click="openBaseDialog()">
            <el-icon><Plus /></el-icon>
            新建
          </el-button>
        </div>
      </section>

      <el-row :gutter="16" class="content-row">
        <el-col :xs="24" :lg="7">
          <section class="panel kb-panel">
            <div class="panel-head">
              <span>知识库</span>
              <el-tag size="small" type="info">{{ bases.length }}</el-tag>
            </div>
            <el-scrollbar class="kb-list" v-loading="baseLoading">
              <button
                v-for="kb in bases"
                :key="kb.id"
                class="kb-item"
                :class="{ active: selectedKb?.id === kb.id }"
                @click="selectKb(kb)"
              >
                <span class="kb-title-line">
                  <span class="kb-name">{{ kb.name }}</span>
                  <el-tag v-if="typeof kb.eval_score === 'number'" size="small" :type="scoreTagType(kb.eval_score)">
                    {{ kb.eval_score }}分
                  </el-tag>
                </span>
                <span class="kb-meta">{{ scopeLabel(kb.scope_type) }} · {{ kb.document_count }} 文档 · {{ kb.chunk_count }} 片段</span>
                <span v-if="kb.eval_sample_count" class="kb-eval-meta">评估 {{ kb.eval_sample_count }} 题 · F1 {{ kb.eval_f1 || 0 }}%</span>
              </button>
              <el-empty v-if="!baseLoading && !bases.length" description="暂无知识库" />
            </el-scrollbar>
          </section>
        </el-col>

        <el-col :xs="24" :lg="17">
          <section v-if="selectedKb" class="panel work-panel">
            <div class="work-head">
              <div>
                <h2>{{ selectedKb.name }}</h2>
                <p>{{ selectedKb.description || '这个知识库还没有描述。' }}</p>
              </div>
              <div class="work-actions">
                <el-button @click="openBaseDialog(selectedKb)">
                  <el-icon><Edit /></el-icon>
                  编辑
                </el-button>
                <el-popconfirm title="删除知识库会同步删除文档和向量，确定吗？" @confirm="removeBase(selectedKb.id)">
                  <template #reference>
                    <el-button type="danger" plain>
                      <el-icon><Delete /></el-icon>
                      删除
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>
            </div>

            <el-tabs v-model="activeTab">
              <el-tab-pane label="构建配置" name="config">
                <div class="config-grid">
                  <section class="config-card">
                    <h3>知识库加工流水线</h3>
                    <div class="pipeline">
                      <span v-for="step in kbDetail?.build?.pipeline || defaultPipeline" :key="step">{{ step }}</span>
                    </div>
                  </section>
                  <section class="config-card">
                    <h3>生成参数</h3>
                    <div class="metric-grid">
                      <div><span>切片方式</span><strong>{{ chunkStrategyLabel(selectedKb.chunk_strategy) }}</strong></div>
                      <div><span>切片大小</span><strong>{{ selectedKb.chunk_size }} 字</strong></div>
                      <div><span>上下文重叠</span><strong>{{ selectedKb.chunk_overlap }} 字</strong></div>
                      <div><span>Embedding</span><strong>{{ selectedKb.embedding_model }}</strong></div>
                      <div><span>向量库</span><strong>{{ selectedKb.vector_store }}</strong></div>
                      <div><span>相似度</span><strong>{{ selectedKb.similarity_metric }}</strong></div>
                    </div>
                  </section>
                  <section class="config-card">
                    <h3>检索策略</h3>
                    <div class="metric-grid">
                      <div><span>检索模式</span><strong>{{ retrievalModeLabel(selectedKb.retrieval_mode) }}</strong></div>
                      <div><span>默认 TopK</span><strong>{{ selectedKb.default_top_k }}</strong></div>
                      <div><span>最低分数</span><strong>{{ selectedKb.default_min_score }}%</strong></div>
                      <div><span>向量权重</span><strong>{{ selectedKb.vector_weight }}%</strong></div>
                      <div><span>关键词权重</span><strong>{{ selectedKb.bm25_weight }}%</strong></div>
                      <div><span>标题/核心词</span><strong>{{ selectedKb.title_weight }}% / {{ selectedKb.core_weight }}%</strong></div>
                    </div>
                  </section>
                  <section class="config-card">
                    <h3>构建状态</h3>
                    <div class="metric-grid">
                      <div><span>文档数</span><strong>{{ selectedKb.document_count }}</strong></div>
                      <div><span>片段数</span><strong>{{ selectedKb.chunk_count }}</strong></div>
                      <div><span>平均片段</span><strong>{{ kbDetail?.build?.avg_chunk_chars || 0 }} 字</strong></div>
                      <div><span>Milvus Collection</span><strong>{{ kbDetail?.build?.milvus_collection || '-' }}</strong></div>
                    </div>
                    <p class="config-note">{{ kbDetail?.retrieval?.metrics_note || 'Recall@K / Precision@K 需要标准测试集，本页先展示检索诊断。' }}</p>
                  </section>
                  <section class="config-card eval-card">
                    <div class="config-card-head">
                      <h3>质量评估</h3>
                      <el-button size="small" type="primary" :loading="evaluating" @click="runEvaluation">
                        {{ evaluating ? '评估中' : '立即评估' }}
                      </el-button>
                    </div>
                    <div class="score-summary">
                      <div class="score-ring" :class="scoreClass(evaluation.score)">
                        <strong>{{ evaluation.score ?? '-' }}</strong>
                        <span>综合分</span>
                      </div>
                      <div class="metric-grid eval-metrics">
                        <div><span>Recall@K</span><strong>{{ metricPercent(evaluation.recall) }}</strong></div>
                        <div><span>Precision@K</span><strong>{{ metricPercent(evaluation.precision) }}</strong></div>
                        <div><span>F1</span><strong>{{ metricPercent(evaluation.f1) }}</strong></div>
                        <div><span>Hit@1 / MRR</span><strong>{{ metricPercent(evaluation.hit_at_1) }} / {{ metricPercent(evaluation.mrr) }}</strong></div>
                      </div>
                    </div>
                    <p class="config-note">
                      {{ evaluation.note || '点击立即评估，系统会自动抽取问题样本并按当前检索配置计算指标。' }}
                    </p>
                    <p v-if="evaluation.evaluated_at" class="config-note">
                      最近评估：{{ evaluation.evaluated_at }} · 样本 {{ evaluation.sample_count || 0 }} 题
                    </p>
                  </section>
                </div>
              </el-tab-pane>

              <el-tab-pane label="导入资料" name="import">
                <div class="import-grid">
                  <div class="import-box">
                    <div class="box-title">长文本</div>
                    <el-input v-model="textForm.title" placeholder="文档标题" />
                    <el-input v-model="textForm.text" type="textarea" :rows="8" resize="none" placeholder="粘贴一段长文字，保存后即可检索问答" />
                    <el-button type="primary" :loading="importing" @click="submitText">
                      <el-icon><DocumentAdd /></el-icon>
                      {{ importing ? '处理中，请勿关闭' : '导入文本' }}
                    </el-button>
                  </div>

                  <div class="import-box">
                    <div class="box-title">文件上传</div>
                    <el-input v-model="uploadTitle" placeholder="标题可选，默认使用文件名" />
                    <el-upload
                      drag
                      :auto-upload="false"
                      :limit="1"
                      :on-change="handleFileChange"
                      :on-remove="handleFileRemove"
                      accept=".txt,.md,.markdown,.pdf"
                    >
                      <el-icon class="upload-icon"><UploadFilled /></el-icon>
                      <div class="el-upload__text">拖入或点击选择 txt / md / pdf</div>
                    </el-upload>
                    <el-button type="success" :loading="importing" :disabled="!uploadFile" @click="submitUpload">
                      <el-icon><Upload /></el-icon>
                      {{ importing ? '处理中，请勿关闭' : '上传入库' }}
                    </el-button>
                  </div>

                  <div class="import-box wide">
                    <div class="box-title">本地路径</div>
                    <div class="path-line">
                      <el-input v-model="pathForm.path" placeholder="仅允许项目目录或 uploads 目录下的 txt / md / pdf" />
                      <el-input v-model="pathForm.title" placeholder="标题可选" />
                      <el-button :loading="importing" @click="submitPath">
                        <el-icon><FolderOpened /></el-icon>
                        {{ importing ? '处理中，请勿关闭' : '导入' }}
                      </el-button>
                    </div>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="文档" name="documents">
                <el-table :data="documents" v-loading="docLoading" stripe>
                  <el-table-column prop="title" label="标题" min-width="180" />
                  <el-table-column prop="source_type" label="来源" width="90">
                    <template #default="{ row }">
                      <el-tag size="small">{{ sourceLabel(row.source_type) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="chunk_count" label="片段" width="80" />
                  <el-table-column prop="char_count" label="字数" width="90" />
                  <el-table-column prop="status" label="状态" width="100">
                    <template #default="{ row }">
                      <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'info'" size="small">
                        {{ row.status }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="created_at" label="导入时间" width="170" />
                  <el-table-column label="操作" width="90" fixed="right">
                    <template #default="{ row }">
                      <el-popconfirm title="确定删除该文档吗？" @confirm="removeDocument(row.id)">
                        <template #reference>
                          <el-button link type="danger">删除</el-button>
                        </template>
                      </el-popconfirm>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane label="问答" name="qa">
                <div class="qa-box">
                  <el-input v-model="question" type="textarea" :rows="3" resize="none" placeholder="向当前知识库提问" @keydown="handleAskKeydown" />
                  <div class="qa-actions">
                    <el-slider v-model="topK" :min="1" :max="10" show-stops />
                    <el-button type="primary" :loading="asking" @click="submitAsk">
                      <el-icon><Promotion /></el-icon>
                      提问
                    </el-button>
                  </div>
                  <div v-if="answer" class="answer">
                    <h3>回答</h3>
                    <p>{{ answer }}</p>
                  </div>
                  <div v-if="sources.length" class="sources">
                    <h3>参考出处</h3>
                    <div v-if="retrievalInfo" class="retrieval-panel">
                      <div>
                        <span>检索模式</span>
                        <strong>{{ retrievalModeLabel(retrievalInfo.mode) }}</strong>
                      </div>
                      <div>
                        <span>候选片段</span>
                        <strong>{{ retrievalInfo.candidate_total || 0 }}</strong>
                      </div>
                      <div>
                        <span>向量/关键词/精准</span>
                        <strong>{{ retrievalInfo.vector_candidates || 0 }} / {{ retrievalInfo.keyword_candidates || 0 }} / {{ retrievalInfo.precise_candidates || 0 }}</strong>
                      </div>
                      <div>
                        <span>权重</span>
                        <strong>V {{ percent(retrievalInfo.weights?.vector) }} · K {{ percent(retrievalInfo.weights?.bm25) }} · T {{ percent(retrievalInfo.weights?.title) }}</strong>
                      </div>
                    </div>
                    <div v-for="item in sources" :key="item.chunk_id" class="source-item">
                      <div class="source-head">
                        <span>{{ item.title }} · 片段 {{ item.chunk_no }}</span>
                        <el-tag size="small" type="info">{{ Math.round(item.score * 100) }}%</el-tag>
                      </div>
                      <div class="score-line">
                        <span>向量 {{ percent(item.vector_score) }}</span>
                        <span>关键词 {{ percent(item.bm25_score) }}</span>
                        <span>标题 {{ percent(item.title_score) }}</span>
                        <span>核心词 {{ percent(item.core_score) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </el-tab-pane>
            </el-tabs>
          </section>

          <section v-else class="panel empty-panel">
            <el-empty description="请选择或新建一个知识库" />
          </section>
        </el-col>
      </el-row>
    </div>

    <el-dialog v-model="baseDialogVisible" :title="editingBase ? '编辑知识库' : '新建知识库'" width="760px" class="kb-dialog">
      <el-form ref="baseFormRef" :model="baseForm" :rules="baseRules" label-position="top">
        <section class="dialog-section">
          <div class="dialog-section-title">基础信息</div>
          <div class="dialog-form-grid">
            <el-form-item label="名称" prop="name">
              <el-input v-model="baseForm.name" />
            </el-form-item>
            <el-form-item label="范围">
              <el-radio-group v-model="baseForm.scope_type">
                <el-radio value="personal">个人</el-radio>
                <el-radio value="public">公共</el-radio>
              </el-radio-group>
            </el-form-item>
          </div>
          <el-form-item label="描述">
            <el-input v-model="baseForm.description" type="textarea" :rows="3" />
          </el-form-item>
        </section>

        <section class="dialog-section">
          <div class="dialog-section-title">知识库生成参数</div>
          <div class="dialog-form-grid">
            <el-form-item label="切片方式">
              <el-select v-model="baseForm.chunk_strategy">
                <el-option label="按段落优先" value="paragraph" />
                <el-option label="固定长度" value="fixed" />
              </el-select>
            </el-form-item>
            <el-form-item label="切片大小">
              <el-input-number v-model="baseForm.chunk_size" :min="200" :max="2000" :step="100" />
            </el-form-item>
            <el-form-item label="上下文重叠字数">
              <el-input-number v-model="baseForm.chunk_overlap" :min="0" :max="500" :step="50" />
            </el-form-item>
            <el-form-item label="默认召回 TopK">
              <el-input-number v-model="baseForm.default_top_k" :min="1" :max="20" />
            </el-form-item>
          </div>
        </section>

        <section class="dialog-section">
          <div class="dialog-section-title">检索参数</div>
          <div class="dialog-form-grid">
            <el-form-item label="检索模式">
              <el-select v-model="baseForm.retrieval_mode">
                <el-option label="混合检索（推荐）" value="hybrid" />
                <el-option label="仅向量检索" value="vector" />
                <el-option label="仅关键词检索" value="keyword" />
              </el-select>
            </el-form-item>
            <el-form-item label="最低相似度分数">
              <div class="slider-field">
                <el-slider v-model="baseForm.default_min_score" :min="0" :max="100" />
                <el-input-number v-model="baseForm.default_min_score" :min="0" :max="100" />
              </div>
            </el-form-item>
          </div>
          <div class="weight-editor">
            <label>
              <span>向量权重</span>
              <el-input-number v-model="baseForm.vector_weight" :min="0" :max="100" />
            </label>
            <label>
              <span>关键词权重</span>
              <el-input-number v-model="baseForm.bm25_weight" :min="0" :max="100" />
            </label>
            <label>
              <span>标题权重</span>
              <el-input-number v-model="baseForm.title_weight" :min="0" :max="100" />
            </label>
            <label>
              <span>核心词权重</span>
              <el-input-number v-model="baseForm.core_weight" :min="0" :max="100" />
            </label>
          </div>
        </section>

        <section v-if="!editingBase" class="dialog-section">
          <div class="dialog-section-head">
            <div>
              <div class="dialog-section-title">导入资料</div>
              <p>可在新建知识库时直接导入第一份资料，也可以稍后在“导入资料”页签继续追加。</p>
            </div>
            <el-tag type="info" size="small">可选</el-tag>
          </div>
          <el-radio-group v-model="createImportMode" class="import-mode-group">
            <el-radio-button value="none">稍后导入</el-radio-button>
            <el-radio-button value="upload">上传文件</el-radio-button>
            <el-radio-button value="text">粘贴文本</el-radio-button>
            <el-radio-button value="path">本地路径</el-radio-button>
          </el-radio-group>

          <div v-if="createImportMode === 'upload'" class="create-import-panel">
            <el-input v-model="createUploadTitle" placeholder="标题可选，默认使用文件名" />
            <el-upload
              drag
              :auto-upload="false"
              :limit="1"
              :on-change="handleCreateFileChange"
              :on-remove="handleCreateFileRemove"
              accept=".txt,.md,.markdown,.pdf"
            >
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div class="el-upload__text">拖入或点击选择 txt / md / pdf</div>
            </el-upload>
          </div>

          <div v-if="createImportMode === 'text'" class="create-import-panel">
            <el-input v-model="createTextForm.title" placeholder="文档标题" />
            <el-input
              v-model="createTextForm.text"
              type="textarea"
              :rows="5"
              resize="none"
              placeholder="粘贴需要入库的长文本，创建后会自动切片并写入向量库"
            />
          </div>

          <div v-if="createImportMode === 'path'" class="create-import-panel">
            <el-input v-model="createPathForm.path" placeholder="仅允许项目目录或 uploads 目录下的 txt / md / pdf" />
            <el-input v-model="createPathForm.title" placeholder="标题可选" />
          </div>
        </section>
      </el-form>
      <template #footer>
        <el-button @click="baseDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="baseSaving" @click="submitBase">
          {{ editingBase ? '保存' : createImportMode === 'none' ? '创建知识库' : '创建并导入' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type UploadFile } from 'element-plus'
import {
  askKnowledge,
  createKnowledgeBase,
  deleteKnowledgeBase,
  deleteKnowledgeDocument,
  evaluateKnowledgeBase,
  getKnowledgeBaseDetail,
  importKnowledgePath,
  importKnowledgeText,
  listKnowledgeBases,
  listKnowledgeDocuments,
  updateKnowledgeBase,
  uploadKnowledgeDocument,
  type KnowledgeBase,
  type KnowledgeDocument,
  type KnowledgeSource,
} from '@/api/rag-knowledge'
import { Delete, DocumentAdd, Edit, FolderOpened, Plus, Promotion, Search, Upload, UploadFilled } from '@element-plus/icons-vue'

const keyword = ref('')
const bases = ref<KnowledgeBase[]>([])
const selectedKb = ref<KnowledgeBase | null>(null)
const documents = ref<KnowledgeDocument[]>([])
const sources = ref<KnowledgeSource[]>([])
const answer = ref('')
const question = ref('')
const topK = ref(5)
const kbDetail = ref<Record<string, any> | null>(null)
const retrievalInfo = ref<Record<string, any> | null>(null)
const activeTab = ref('import')
const baseLoading = ref(false)
const docLoading = ref(false)
const importing = ref(false)
const asking = ref(false)
const evaluating = ref(false)
const baseSaving = ref(false)
const baseDialogVisible = ref(false)
const editingBase = ref<KnowledgeBase | null>(null)
const uploadFile = ref<File | null>(null)
const uploadTitle = ref('')
const baseFormRef = ref<FormInstance>()

const defaultPipeline = ['文档解析', '文本清洗', '切片', 'Embedding 向量化', 'MySQL 片段存储', 'Milvus 向量入库', '混合检索问答']
const baseDefaults = {
  name: '',
  description: '',
  scope_type: 'personal',
  chunk_strategy: 'paragraph' as 'paragraph' | 'fixed',
  chunk_size: 700,
  chunk_overlap: 100,
  embedding_model: 'moka-ai/m3e-base',
  vector_store: 'milvus',
  similarity_metric: 'COSINE' as 'COSINE' | 'IP' | 'L2',
  retrieval_mode: 'hybrid' as 'vector' | 'keyword' | 'hybrid',
  default_top_k: 5,
  default_min_score: 45,
  vector_weight: 62,
  bm25_weight: 28,
  title_weight: 10,
  core_weight: 35,
}
const baseForm = reactive({ ...baseDefaults })
const textForm = reactive({ title: '', text: '' })
const pathForm = reactive({ path: '', title: '' })
const createImportMode = ref<'none' | 'upload' | 'text' | 'path'>('none')
const createTextForm = reactive({ title: '', text: '' })
const createPathForm = reactive({ path: '', title: '' })
const createUploadFile = ref<File | null>(null)
const createUploadTitle = ref('')
const baseRules = { name: [{ required: true, message: '请输入知识库名称', trigger: 'blur' }] }

function currentEvaluation() {
  const detailEval = kbDetail.value?.evaluation || {}
  const kb = selectedKb.value
  return {
    score: detailEval.score ?? kb?.eval_score,
    recall: typeof detailEval.recall === 'number' ? detailEval.recall / 100 : percentToRatio(kb?.eval_recall),
    precision: typeof detailEval.precision === 'number' ? detailEval.precision / 100 : percentToRatio(kb?.eval_precision),
    f1: typeof detailEval.f1 === 'number' ? detailEval.f1 / 100 : percentToRatio(kb?.eval_f1),
    hit_at_1: typeof detailEval.hit_at_1 === 'number' ? detailEval.hit_at_1 / 100 : percentToRatio(kb?.eval_hit),
    mrr: typeof detailEval.mrr === 'number' ? detailEval.mrr / 100 : percentToRatio(kb?.eval_mrr),
    sample_count: detailEval.sample_count ?? kb?.eval_sample_count,
    evaluated_at: detailEval.evaluated_at ?? kb?.evaluated_at,
    note: detailEval.note,
  }
}

const evaluation = computed(currentEvaluation)

function scopeLabel(scope: string) {
  return ({ personal: '个人', public: '公共', class: '班级', course: '课程' } as Record<string, string>)[scope] || scope
}

function sourceLabel(source: string) {
  return ({ text: '文本', upload: '上传', path: '路径' } as Record<string, string>)[source] || source
}

function percent(value?: number) {
  if (typeof value !== 'number') return '0%'
  return `${Math.round(value * 100)}%`
}

function percentToRatio(value?: number) {
  return typeof value === 'number' ? value / 100 : undefined
}

function metricPercent(value?: number) {
  if (typeof value !== 'number') return '-'
  return `${Math.round(value * 100)}%`
}

function scoreTagType(score?: number) {
  if (typeof score !== 'number') return 'info'
  if (score >= 85) return 'success'
  if (score >= 70) return 'warning'
  return 'danger'
}

function scoreClass(score?: number) {
  if (typeof score !== 'number') return 'empty'
  if (score >= 85) return 'good'
  if (score >= 70) return 'mid'
  return 'low'
}

function chunkStrategyLabel(value?: string) {
  return ({ paragraph: '按段落优先', fixed: '固定长度' } as Record<string, string>)[value || ''] || value || '-'
}

function retrievalModeLabel(value?: string) {
  return ({ hybrid: '混合检索', vector: '向量检索', keyword: '关键词检索' } as Record<string, string>)[value || ''] || value || '-'
}

async function fetchBases() {
  baseLoading.value = true
  try {
    const res = await listKnowledgeBases({ keyword: keyword.value || undefined })
    bases.value = res.data || []
    if (selectedKb.value) selectedKb.value = bases.value.find((item) => item.id === selectedKb.value?.id) || null
    if (!selectedKb.value && bases.value.length) await selectKb(bases.value[0])
  } catch (error: any) {
    bases.value = []
    selectedKb.value = null
    documents.value = []
    ElMessage.error(error?.message || '知识库列表加载失败，请确认后端已重启并加载最新接口')
  } finally {
    baseLoading.value = false
  }
}

async function selectKb(kb: KnowledgeBase) {
  selectedKb.value = kb
  answer.value = ''
  sources.value = []
  retrievalInfo.value = null
  await Promise.all([fetchDocuments(), fetchKbDetail()])
}

async function fetchDocuments() {
  if (!selectedKb.value) return
  docLoading.value = true
  try {
    const res = await listKnowledgeDocuments(selectedKb.value.id)
    documents.value = res.data || []
  } catch (error: any) {
    documents.value = []
    ElMessage.error(error?.message || '文档列表加载失败')
  } finally {
    docLoading.value = false
  }
}

async function fetchKbDetail() {
  if (!selectedKb.value) return
  try {
    const res = await getKnowledgeBaseDetail(selectedKb.value.id)
    kbDetail.value = res.data || null
  } catch (error) {
    kbDetail.value = null
  }
}

function openBaseDialog(kb?: KnowledgeBase) {
  editingBase.value = kb || null
  resetCreateImportForm()
  Object.assign(baseForm, {
    ...baseDefaults,
    ...(kb || {}),
    description: kb?.description || '',
    scope_type: kb?.scope_type || 'personal',
  })
  baseDialogVisible.value = true
}

async function submitBase() {
  await baseFormRef.value?.validate()
  if (!editingBase.value && !validateCreateImport()) return
  baseSaving.value = true
  try {
    if (editingBase.value) {
      await updateKnowledgeBase(editingBase.value.id, baseForm)
      ElMessage.success('知识库已更新')
    } else {
      const res = await createKnowledgeBase(baseForm)
      const createdKb = res.data
      selectedKb.value = createdKb
      if (createImportMode.value !== 'none') {
        try {
          await importIntoCreatedBase(createdKb.id)
          ElMessage.success('知识库已创建，资料已入库')
        } catch (error: any) {
          ElMessage.warning(error?.message || '知识库已创建，但资料导入失败，可在导入资料页重试')
          createImportMode.value = 'none'
        }
      } else {
        ElMessage.success('知识库已创建，可继续导入资料')
      }
    }
    baseDialogVisible.value = false
    await fetchBases()
    if (!editingBase.value && selectedKb.value) {
      const latest = bases.value.find((item) => item.id === selectedKb.value?.id)
      if (latest) {
        await selectKb(latest)
      } else {
        await fetchDocuments()
        await fetchKbDetail()
      }
      activeTab.value = createImportMode.value === 'none' ? 'import' : 'documents'
      resetCreateImportForm()
      return
    }
    if (selectedKb.value) await fetchKbDetail()
  } finally {
    baseSaving.value = false
  }
}

function resetCreateImportForm() {
  createImportMode.value = 'none'
  createTextForm.title = ''
  createTextForm.text = ''
  createPathForm.path = ''
  createPathForm.title = ''
  createUploadFile.value = null
  createUploadTitle.value = ''
}

function validateCreateImport() {
  if (createImportMode.value === 'text') {
    if (!createTextForm.title.trim() || !createTextForm.text.trim()) {
      ElMessage.warning('请填写导入文本的标题和内容')
      return false
    }
  }
  if (createImportMode.value === 'upload' && !createUploadFile.value) {
    ElMessage.warning('请选择要上传的文件')
    return false
  }
  if (createImportMode.value === 'path' && !createPathForm.path.trim()) {
    ElMessage.warning('请输入本地文件路径')
    return false
  }
  return true
}

async function importIntoCreatedBase(kbId: number) {
  if (createImportMode.value === 'text') {
    await importKnowledgeText({ kb_id: kbId, title: createTextForm.title.trim(), text: createTextForm.text })
    return
  }
  if (createImportMode.value === 'upload' && createUploadFile.value) {
    await uploadKnowledgeDocument(kbId, createUploadFile.value, createUploadTitle.value.trim() || undefined)
    return
  }
  if (createImportMode.value === 'path') {
    await importKnowledgePath({
      kb_id: kbId,
      path: createPathForm.path.trim(),
      title: createPathForm.title.trim() || undefined,
    })
  }
}

async function removeBase(id: number) {
  await deleteKnowledgeBase(id)
  ElMessage.success('知识库已删除')
  selectedKb.value = null
  documents.value = []
  await fetchBases()
}

async function submitText() {
  if (!selectedKb.value) return
  if (!textForm.title.trim() || !textForm.text.trim()) {
    ElMessage.warning('请填写标题和文本')
    return
  }
  importing.value = true
  try {
    await importKnowledgeText({ kb_id: selectedKb.value.id, title: textForm.title, text: textForm.text })
    ElMessage.success('文本已入库')
    textForm.title = ''
    textForm.text = ''
    await fetchBases()
    await fetchDocuments()
    await fetchKbDetail()
    activeTab.value = 'documents'
  } finally {
    importing.value = false
  }
}

function handleFileChange(file: UploadFile) {
  uploadFile.value = file.raw || null
}

function handleFileRemove() {
  uploadFile.value = null
}

function handleCreateFileChange(file: UploadFile) {
  createUploadFile.value = file.raw || null
}

function handleCreateFileRemove() {
  createUploadFile.value = null
}

async function submitUpload() {
  if (!selectedKb.value || !uploadFile.value) return
  importing.value = true
  try {
    await uploadKnowledgeDocument(selectedKb.value.id, uploadFile.value, uploadTitle.value || undefined)
    ElMessage.success('文件已入库')
    uploadFile.value = null
    uploadTitle.value = ''
    await fetchBases()
    await fetchDocuments()
    await fetchKbDetail()
    activeTab.value = 'documents'
  } finally {
    importing.value = false
  }
}

async function submitPath() {
  if (!selectedKb.value) return
  if (!pathForm.path.trim()) {
    ElMessage.warning('请输入文件路径')
    return
  }
  importing.value = true
  try {
    await importKnowledgePath({ kb_id: selectedKb.value.id, path: pathForm.path, title: pathForm.title || undefined })
    ElMessage.success('路径文件已入库')
    pathForm.path = ''
    pathForm.title = ''
    await fetchBases()
    await fetchDocuments()
    await fetchKbDetail()
    activeTab.value = 'documents'
  } finally {
    importing.value = false
  }
}

async function removeDocument(id: number) {
  await deleteKnowledgeDocument(id)
  ElMessage.success('文档已删除')
  await fetchBases()
  await fetchDocuments()
  await fetchKbDetail()
}

async function runEvaluation() {
  if (!selectedKb.value) return
  evaluating.value = true
  try {
    const res = await evaluateKnowledgeBase(selectedKb.value.id)
    ElMessage.success(`评估完成，综合评分 ${res.data?.score ?? '-'} 分`)
    await fetchBases()
    const latest = bases.value.find((item) => item.id === selectedKb.value?.id)
    if (latest) selectedKb.value = latest
    await fetchKbDetail()
  } catch (error: any) {
    ElMessage.error(error?.message || '知识库评估失败')
  } finally {
    evaluating.value = false
  }
}

async function submitAsk() {
  if (!selectedKb.value || !question.value.trim()) return
  asking.value = true
  try {
    const res = await askKnowledge({ question: question.value, kb_ids: [selectedKb.value.id], top_k: topK.value, min_score: 0 })
    answer.value = res.data?.answer || ''
    sources.value = res.data?.sources || []
    retrievalInfo.value = res.data?.retrieval || null
  } finally {
    asking.value = false
  }
}

function handleAskKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submitAsk()
  }
}

onMounted(() => {
  fetchBases().catch(() => {})
})
</script>

<style scoped>
.knowledge-page {
  min-height: 100%;
}

.page-shell {
  max-width: 1480px;
  margin: 0 auto;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.toolbar h1 {
  margin: 0 0 6px;
  font-size: 24px;
  color: #1f2937;
}

.toolbar p {
  margin: 0;
  color: #64748b;
}

.toolbar-actions {
  display: grid;
  grid-template-columns: minmax(180px, 260px) auto;
  gap: 10px;
}

.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.kb-panel,
.work-panel,
.empty-panel {
  min-height: calc(100vh - 168px);
}

.panel-head {
  height: 50px;
  padding: 0 14px;
  border-bottom: 1px solid #eef2f7;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.kb-list {
  height: calc(100vh - 220px);
  padding: 10px;
}

.kb-item {
  width: 100%;
  min-height: 72px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  text-align: left;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.kb-item:hover,
.kb-item.active {
  background: #f0f7ff;
  border-color: #9cc9ff;
}

.kb-title-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.kb-name {
  display: block;
  min-width: 0;
  font-weight: 600;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-meta,
.kb-eval-meta {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.kb-eval-meta {
  margin-top: 5px;
  color: #2563eb;
}

.work-panel {
  padding: 16px;
}

.work-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.work-head h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.work-head p {
  margin: 0;
  color: #64748b;
}

.work-actions {
  display: flex;
  gap: 8px;
}

.import-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.import-box {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px;
  display: grid;
  gap: 12px;
  align-content: start;
}

.import-box.wide {
  grid-column: 1 / -1;
}

.box-title {
  font-weight: 600;
  color: #1f2937;
}

.path-line {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) 220px auto;
  gap: 10px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.config-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px;
  background: #fbfdff;
}

.config-card h3 {
  margin: 0 0 12px;
  font-size: 15px;
  color: #1f2937;
}

.config-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.config-card-head h3 {
  margin: 0;
}

.pipeline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pipeline span {
  border: 1px solid #cfe0f5;
  border-radius: 999px;
  background: #ffffff;
  color: #1d4ed8;
  padding: 5px 9px;
  font-size: 12px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.metric-grid div {
  min-height: 54px;
  border: 1px solid #e6edf6;
  border-radius: 8px;
  background: #ffffff;
  padding: 8px 10px;
}

.metric-grid span {
  display: block;
  color: #64748b;
  font-size: 12px;
  margin-bottom: 5px;
}

.metric-grid strong {
  display: block;
  color: #111827;
  font-size: 13px;
  word-break: break-word;
}

.config-note {
  margin: 12px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.7;
}

.eval-card {
  grid-column: 1 / -1;
}

.score-summary {
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  gap: 14px;
  align-items: stretch;
}

.score-ring {
  min-height: 132px;
  border-radius: 8px;
  border: 1px solid #dbe4ef;
  background: #ffffff;
  display: grid;
  place-content: center;
  text-align: center;
}

.score-ring strong {
  color: #111827;
  font-size: 34px;
  line-height: 1;
}

.score-ring span {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
}

.score-ring.good {
  border-color: #86efac;
  background: #f0fdf4;
}

.score-ring.mid {
  border-color: #fde68a;
  background: #fffbeb;
}

.score-ring.low {
  border-color: #fecaca;
  background: #fef2f2;
}

.score-ring.empty {
  background: #f8fafc;
}

.eval-metrics {
  align-content: stretch;
}

.upload-icon {
  font-size: 34px;
  color: #409eff;
}

.qa-box {
  display: grid;
  gap: 14px;
}

.qa-actions {
  display: grid;
  grid-template-columns: minmax(180px, 280px) auto;
  align-items: center;
  gap: 14px;
}

.answer,
.source-item {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px;
  background: #fbfdff;
}

.answer h3,
.sources h3 {
  margin: 0 0 10px;
  font-size: 16px;
}

.answer p,
.source-item p {
  white-space: pre-wrap;
  line-height: 1.7;
  margin: 0;
  color: #334155;
}

.sources {
  display: grid;
  gap: 10px;
}

.retrieval-panel {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 4px;
}

.retrieval-panel div {
  border: 1px solid #dce7f5;
  border-radius: 8px;
  background: #f8fbff;
  padding: 8px 10px;
}

.retrieval-panel span {
  display: block;
  color: #64748b;
  font-size: 12px;
  margin-bottom: 4px;
}

.retrieval-panel strong {
  display: block;
  color: #111827;
  font-size: 12px;
  word-break: break-word;
}

.source-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  font-weight: 600;
}

.score-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 12px;
}

.dialog-section {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 14px;
  background: #fbfdff;
}

.dialog-section-title {
  margin-bottom: 12px;
  color: #1f2937;
  font-size: 15px;
  font-weight: 700;
}

.dialog-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.dialog-section-head .dialog-section-title {
  margin-bottom: 4px;
}

.dialog-section-head p {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.dialog-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}

.kb-dialog :deep(.el-form-item) {
  margin-bottom: 14px;
}

.kb-dialog :deep(.el-form-item__label) {
  margin-bottom: 6px;
  color: #475569;
  line-height: 1.25;
  font-size: 13px;
  font-weight: 600;
}

.kb-dialog :deep(.el-select),
.kb-dialog :deep(.el-input-number) {
  width: 100%;
}

.slider-field {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 118px;
  align-items: center;
  gap: 12px;
}

.weight-editor {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.weight-editor label {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.weight-editor span {
  color: #475569;
  font-size: 13px;
  font-weight: 600;
}

.import-mode-group {
  margin-bottom: 12px;
}

.create-import-panel {
  display: grid;
  gap: 12px;
}

.empty-panel {
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 992px) {
  .toolbar,
  .work-head {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-actions,
  .import-grid,
  .config-grid,
  .retrieval-panel,
  .path-line,
  .qa-actions {
    grid-template-columns: 1fr;
  }

  .metric-grid,
  .dialog-form-grid,
  .slider-field,
  .score-summary,
  .weight-editor {
    grid-template-columns: 1fr;
  }

  .dialog-section-head {
    align-items: stretch;
    flex-direction: column;
  }

  .import-mode-group {
    display: grid;
  }

  .kb-panel,
  .work-panel,
  .empty-panel {
    min-height: auto;
  }

  .kb-list {
    height: 280px;
  }
}
</style>
