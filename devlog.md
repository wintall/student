# 学生信息管理系统 - 开发日志

## [2026-06-20] Task 1: 项目初始化
- 完成内容：项目基础框架搭建
- 文件变更：
  - 新增 `.env`（环境变量配置）
  - 新增 `requirements.txt`（13个依赖包）
  - 新增 `app/config.py`（Pydantic Settings 读取 .env）
  - 新增 `app/database.py`（SQLAlchemy 引擎 + Session）
  - 新增 `app/redis.py`（Redis 连接池 + 便捷操作）
  - 新增 `main.py`（FastAPI 入口 + CORS + RequestID 中间件）
  - 创建完整目录结构（app/core, models, schemas, api/v1, services, utils, logs, scripts, tests）
- 技术要点：
  - CORS_ORIGINS 需要声明为 `List[str]` 类型，field_validator 处理 JSON 字符串
  - DATABASE_URL 和 REDIS_URL 使用 @property 动态构建

## [2026-06-20] Task 2: ORM 模型 + Alembic 迁移
- 完成内容：17张数据库表 ORM 模型 + Alembic 首次迁移
- 文件变更：
  - 新增 `app/models/base.py`（Base, TimestampMixin, SoftDeleteMixin）
  - 新增 `app/models/user.py`（User, Role, Menu, UserRole, RoleMenu, OperationLog）
  - 新增 `app/models/department.py`（Department）
  - 新增 `app/models/clazz.py`（Clazz）
  - 新增 `app/models/teacher.py`（Teacher, TeacherClazz）
  - 新增 `app/models/student.py`（Student, StudentCourse）
  - 新增 `app/models/course.py`（Course）
  - 新增 `app/models/exam.py`（Exam）
  - 新增 `app/models/score.py`（Score）
  - 新增 `app/models/announcement.py`（Announcement, AnnouncementRead）
  - 更新 `app/models/__init__.py`（导出所有模型）
  - 新增 `app/core/enums.py`（11个 IntEnum 类 + ENUM_DICT）
  - 初始化 Alembic + 首次迁移 `alembic/versions/*.py`
- 技术要点：
  - Clazz.counselor_id 指向 teacher.id（不是 user.id）
  - Teacher/Student 表不含 phone/email（统一在 User 表）
  - OperationLog.created_at 使用 `default=func.now()` 而非 `server_default`（MySQL 兼容）
  - Menu 表自引用关系实现树形结构

## [2026-06-20] Task 3: 核心模块
- 完成内容：validators, security, permissions, rate_limit
- 文件变更：
  - 新增 `app/core/validators.py`（身份证、手机号、邮箱、密码校验）
  - 新增 `app/core/security.py`（JWT 生成/验证 + bcrypt 密码哈希）
  - 新增 `app/core/permissions.py`（RBAC 权限检查 + Redis 缓存）
  - 新增 `app/core/rate_limit.py`（Redis 登录限流）
- 技术要点：
  - 身份证宽松校验：18位，前17位数字，最后一位数字或X，日期合理性检查
  - 手机号支持 +86 前缀，存储时统一为纯11位数字
  - admin 角色直接放行（返回 `{"*"}`），其他角色查 RoleMenu 链路
  - 权限缓存 10 分钟过期

## [2026-06-20] Task 4: Schema + 通用工具
- 完成内容：所有 Pydantic Schema + 分页/响应工具
- 文件变更：
  - 新增 `app/schemas/common.py`（ApiResponse, PageParams, PageResult）
  - 新增 `app/schemas/auth.py`（LoginRequest, TokenResponse, ChangePasswordRequest）
  - 新增 `app/schemas/user.py`（UserCreate, UserUpdate, UserOut）
  - 新增 `app/schemas/role.py`（RoleCreate, RoleUpdate, MenuCreate, MenuUpdate, MenuOut）
  - 新增 `app/schemas/department.py`、`clazz.py`、`teacher.py`、`student.py`、`course.py`、`exam.py`、`score.py`、`announcement.py`
  - 新增 `app/utils/pagination.py`（通用分页）
  - 新增 `app/utils/response.py`（统一响应封装）
- 技术要点：
  - ApiResponse 使用 Generic[T] 实现泛型响应
  - PageParams.offset 使用 @property 计算偏移量
  - 所有 Out schema 使用 `model_config = {"from_attributes": True}`

## [2026-06-20] Task 5: 全局异常处理
- 完成内容：自定义异常类 + 全局异常处理器
- 文件变更：
  - 新增 `app/exceptions.py`（BusinessException, AuthenticationError, PermissionDenied, NotFoundError）
  - 更新 `main.py`（5个全局异常处理器：BusinessException, RequestValidationError, IntegrityError, SQLAlchemyError, Exception）
- 技术要点：
  - 所有异常统一返回 `{code, message, data}` 格式
  - IntegrityError 提取 Duplicate entry 信息返回"数据已存在"
  - 全局异常捕获避免 500 页面暴露堆栈

## [2026-06-20] Task 6-7: Service + API 层 + 登录鉴权
- 完成内容：全部 11 个 service + 12 个 API router + 依赖注入
- 文件变更：
  - 新增 `app/deps.py`（get_db, get_current_user, get_optional_user）
  - 新增 `app/services/auth_service.py`（login, refresh, logout, change_password）
  - 新增 `app/services/user_service.py`、`role_service.py`、`department_service.py`、`clazz_service.py`、`teacher_service.py`、`student_service.py`、`course_service.py`、`exam_service.py`、`score_service.py`、`announcement_service.py`
  - 新增 `app/api/v1/common.py`（枚举字典、健康检查）
  - 新增 `app/api/v1/auth.py`（login, refresh, logout, change-password, menus）
  - 新增 `app/api/v1/user.py`、`role.py`、`department.py`、`clazz.py`、`teacher.py`、`student.py`、`course.py`、`exam.py`、`score.py`、`announcement.py`
  - 新增 `app/api/v1/router.py`（汇总注册所有子路由）
  - 更新 `main.py`（注册 api_router）
- 技术要点：
  - 登录支持用户名/手机号/身份证三种方式（_find_user_by_account 自动判断）
  - refresh_token 存储到 Redis，支持主动注销
  - score_service 自动计算成绩等级和班级排名
  - 66 条 API 路由

## [2026-06-20] Task 8: 种子数据脚本
- 完成内容：初始化脚本（角色、管理员、菜单树、示例数据）
- 文件变更：
  - 新增 `scripts/init_db.py`
- 技术要点：
  - 3 个预设角色：admin / staff / student
  - 完整菜单树：5个一级目录 + 多个二级菜单 + 按钮级权限
  - admin 全菜单权限，staff 部分管理权限，student 只读权限
  - 示例数据：2个院系、3个班级、2个教职工、3个学生
  - 初始密码：admin/admin123，其他用户/123456Ab，首次强制改密

## [2026-06-20] Task 9: 应用日志 + 请求追踪
- 完成内容：日志配置 + RequestID 追踪
- 文件变更：
  - 新增 `app/core/logging_config.py`（TimedRotatingFileHandler + RequestIDFilter）
  - 更新 `main.py`（lifespan 中初始化日志，中间件注入 request_id 到日志上下文）
- 技术要点：
  - 按日轮转，保留 30 天
  - 控制台 + 文件双输出
  - 使用 LogRecordFactory 将 request_id 注入日志上下文
  - SQLAlchemy 和 alembic 日志级别设为 WARNING

## [2026-06-20] Task 10: 开发日志
- 完成内容：创建 devlog.md（本文件）
- 文件变更：新增 `devlog.md`
