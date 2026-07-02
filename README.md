# Wintall AI Campus Assistant

一个基于 FastAPI + Vue 3 的校园信息管理与 AI 足球助手项目。项目包含教务管理、请假考勤、邮件、RAG 综合知识库、文档处理、搜索、地图路线、GitHub 助手、编程助手、人脸识别登录等模块。

## 技术栈

- 后端：FastAPI、SQLAlchemy、Alembic、MySQL、Redis
- 前端：Vue 3、Vite、TypeScript、Element Plus、Pinia
- AI 能力：LangChain、LangGraph、DeepSeek/OpenAI 兼容接口、Milvus、Tavily、Tesseract OCR
- 视觉能力：face-api 人脸特征提取与后端余弦相似度匹配

## 目录说明

```text
app/                  后端接口、模型、服务和 AI Agent 能力
frontend/             Vue 前端项目
alembic/              数据库迁移
scripts/              初始化数据、权限同步、演示数据脚本
docs/                 项目文档与技术知识库
tests/                后端测试用例
tools/                OCR 等本地工具资源
```

## 环境准备

建议环境：

- Python 3.11+
- Node.js 20+
- MySQL 8+
- Redis 6+
- 可选：Milvus、Tesseract OCR、Ollama

## 后端启动

1. 创建并激活虚拟环境：

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 配置环境变量：

```bash
copy .env.example .env
```

然后修改 `.env` 中的 MySQL、Redis、JWT、SMTP、DeepSeek、Tavily、地图 Key 等配置。真实密钥不要提交到 GitHub。

4. 初始化数据库：

```bash
alembic upgrade head
python -m scripts.init_db
python -m scripts.sync_rbac_permissions
python -m scripts.sync_operations_module
python -m scripts.sync_user_emails
```

如需重置演示数据，可根据需要执行：

```bash
python -m scripts.reset_seed_data
python -m scripts.seed_integrated_demo_data
python -m scripts.seed_attendance_data
python -m scripts.seed_schedule_data
```

5. 启动后端：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

后端接口文档：

```text
http://localhost:8000/api/docs
```

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

默认访问：

```text
http://localhost:5173
```

## 常用测试账号

初始化脚本会创建演示账号，默认可先使用：

```text
管理员：admin / admin123
```

其他学生、教师账号以初始化脚本和数据库实际生成结果为准。

## AI 助手可选配置

足球助手可以按配置启用不同能力：

- DeepSeek/OpenAI 兼容接口：用于自然语言理解、学习辅导、情绪陪伴、总结生成。
- Tavily API Key：用于搜索引擎模块获取最新信息。
- Milvus：用于 RAG 综合知识库向量检索。
- Tesseract OCR：用于图片文字识别。
- SMTP：用于邮件、情绪风险通知和系统站内信联动。
- 地图 Key：用于路线生活模块。

缺少某些可选配置时，系统会尽量降级到本地规则或给出提示。

## RAG 知识库

综合知识库支持上传 txt、md、pdf、docx 等资料，经过文档解析、切片、Embedding、MySQL 片段存储和可选 Milvus 向量入库后，可在足球助手中进行知识问答。

知识库相关技术说明位于：

```text
docs/Tech-Knowledge/RAG/
```

## 技术文档

可复用技术沉淀位于：

```text
docs/Tech-Knowledge/
```

其中包含 Agent 编排、RAG、Memory、MCP 搜索、权限边界、OCR、人脸识别、日志追踪、降级策略等 Markdown 文档，适合答辩和后续项目复用。

## 注意事项

- `.env`、上传文件、日志、数据库文件、node_modules 不会提交到仓库。
- 首次运行前必须正确配置 MySQL 和 Redis。
- OCR 需要本机安装 Tesseract，中文识别需要 `chi_sim.traineddata`。
- 如果使用 Milvus，请确认 Milvus 服务已启动并在 `.env` 中配置连接地址。
