# 人脸识别登录模块开发文档

## 一、需求概述

为学生管理系统增加人脸识别登录功能，用户可以通过摄像头实时捕捉人脸特征进行身份验证，无需输入账号密码。

### 1.1 核心功能

| 功能 | 描述 |
|------|------|
| 人脸录入 | 用户在个人中心录入人脸特征模板 |
| 人脸登录 | 登录页通过摄像头进行人脸识别登录 |
| 人脸管理 | 用户/管理员可管理人脸模板（查看、删除） |
| 人脸登录日志 | 记录人脸识别登录记录，用于安全审计 |

### 1.2 技术选型

| 环节 | 方案 | 说明 |
|------|------|------|
| 人脸检测 | face-api.js | 浏览器端实时人脸检测 |
| 特征提取 | face-api.js | 输出 128 维特征向量 |
| 特征比对 | 余弦相似度 | 计算特征向量夹角，阈值 ≥ 0.6 |
| 活体检测 | 眨眼检测 | 要求用户眨眼验证活体 |
| 限流 | Redis | 同 IP 5分钟最多尝试5次 |

---

## 二、数据库设计

### 2.1 新增表结构

#### 2.1.1 face_template（人脸模板表）

```sql
CREATE TABLE face_template (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    user_id INT NOT NULL COMMENT '关联用户ID',
    feature_vector TEXT NOT NULL COMMENT '人脸特征向量（JSON序列化）',
    confidence FLOAT DEFAULT 0.0 COMMENT '录入时的置信度',
    status TINYINT DEFAULT 1 COMMENT '1=启用 0=禁用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '录入时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uq_face_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人脸模板表';
```

#### 2.1.2 face_login_log（人脸登录日志表）

```sql
CREATE TABLE face_login_log (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    user_id INT NULL COMMENT '匹配到的用户ID',
    confidence FLOAT NOT NULL COMMENT '匹配置信度',
    success BOOLEAN NOT NULL COMMENT '是否成功',
    message VARCHAR(255) NULL COMMENT '结果描述',
    ip_address VARCHAR(50) NULL COMMENT '请求IP',
    device_info VARCHAR(255) NULL COMMENT '设备信息',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '登录时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人脸登录日志表';
```

### 2.2 现有表修改

#### 2.2.1 user 表新增字段

```sql
ALTER TABLE user ADD COLUMN has_face_template BOOLEAN DEFAULT FALSE COMMENT '是否已录入人脸';
```

---

## 三、后端实现（FastAPI + MVC 分层）

### 3.1 模型层（Model）

#### 3.1.1 创建模型文件：`app/models/face.py`

```python
"""
人脸识别相关模型
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin


class FaceTemplate(TimestampMixin, Base):
    """人脸模板表 - 存储用户的人脸特征向量"""
    __tablename__ = "face_template"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, comment="关联用户ID")
    feature_vector = Column(Text, nullable=False, comment="人脸特征向量（JSON序列化）")
    confidence = Column(Float, default=0.0, comment="录入时的置信度")
    status = Column(Integer, default=1, comment="1=启用 0=禁用")

    __table_args__ = (UniqueConstraint("user_id", name="uq_face_user"),)

    user = relationship("User", back_populates="face_template")


class FaceLoginLog(Base):
    """人脸登录日志表 - 安全审计"""
    __tablename__ = "face_login_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True, comment="匹配到的用户ID")
    confidence = Column(Float, nullable=False, comment="匹配置信度")
    success = Column(Boolean, nullable=False, comment="是否成功")
    message = Column(String(255), nullable=True, comment="结果描述")
    ip_address = Column(String(50), nullable=True, comment="请求IP")
    device_info = Column(String(255), nullable=True, comment="设备信息")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="登录时间")

    user = relationship("User", backref="face_login_logs")
```

#### 3.1.2 修改用户模型：`app/models/user.py`

在 `User` 类中添加：

```python
has_face_template = Column(Boolean, default=False, comment="是否已录入人脸")
face_template = relationship("FaceTemplate", back_populates="user", uselist=False, cascade="all, delete-orphan")
```

### 3.2 数据传输层（Schema）

#### 3.2.1 创建 Schema 文件：`app/schemas/face.py`

```python
"""
人脸识别相关 Schema
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class FaceLoginRequest(BaseModel):
    """人脸登录请求"""
    feature_vector: List[float] = Field(..., description="128维人脸特征向量")
    device_info: Optional[str] = Field(None, description="设备信息")


class FaceLoginResponse(BaseModel):
    """人脸登录响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class FaceEnrollRequest(BaseModel):
    """人脸录入请求"""
    feature_vector: List[float] = Field(..., description="128维人脸特征向量")
    confidence: float = Field(..., description="录入时的置信度")


class FaceTemplateResponse(BaseModel):
    """人脸模板响应"""
    id: int
    user_id: int
    confidence: float
    status: int
    created_at: str


class FaceLoginLogResponse(BaseModel):
    """人脸登录日志响应"""
    id: int
    user_id: Optional[int]
    confidence: float
    success: bool
    message: Optional[str]
    ip_address: Optional[str]
    created_at: str
```

### 3.3 服务层（Service）

#### 3.3.1 创建服务文件：`app/services/face_service.py`

```python
"""
人脸识别服务
"""
import json
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
import numpy as np

from app.models.user import User
from app.models.face import FaceTemplate, FaceLoginLog
from app.core.security import create_access_token, create_refresh_token
from app.core.rate_limit import check_login_rate_limit
from app.exceptions import AuthenticationError, BusinessException
from app.redis import redis_set, redis_get, redis_delete
from app.config import settings

logger = logging.getLogger("app")

# 人脸识别配置
FACE_MATCH_THRESHOLD = 0.6  # 余弦相似度阈值
FACE_LOGIN_RATE_LIMIT_KEY = "face_login_rate:{ip}"
FACE_LOGIN_RATE_LIMIT_COUNT = 5  # 5分钟最多尝试5次
FACE_LOGIN_RATE_LIMIT_TTL = 300  # 5分钟


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """计算余弦相似度"""
    a = np.array(vec1)
    b = np.array(vec2)
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))


def face_login(feature_vector: List[float], device_info: str, ip: str, db: Session) -> dict:
    """
    人脸登录
    - 限流检查
    - 特征比对
    - 生成 token
    - 记录日志
    """
    # 1. 参数校验
    if len(feature_vector) != 128:
        raise BusinessException(code=400, message="特征向量维度不正确")

    # 2. 限流检查
    rate_key = FACE_LOGIN_RATE_LIMIT_KEY.format(ip=ip)
    try:
        count = redis_get(rate_key)
        count = int(count) if count and count.isdigit() else 0
        if count >= FACE_LOGIN_RATE_LIMIT_COUNT:
            raise BusinessException(code=400, message="尝试次数过多，请5分钟后再试")
        redis_set(rate_key, str(count + 1), ex=FACE_LOGIN_RATE_LIMIT_TTL)
    except Exception:
        pass

    # 3. 查询所有可用的人脸模板
    templates = db.query(FaceTemplate).filter(
        FaceTemplate.status == 1
    ).all()

    if not templates:
        raise AuthenticationError("系统暂无已录入人脸，请使用密码登录")

    # 4. 特征比对
    max_similarity = 0.0
    matched_user = None

    for template in templates:
        try:
            stored_vector = json.loads(template.feature_vector)
            if len(stored_vector) != 128:
                continue
            similarity = cosine_similarity(feature_vector, stored_vector)
            if similarity > max_similarity:
                max_similarity = similarity
                matched_user = template.user
        except Exception as e:
            logger.error(f"人脸比对失败: {e}")
            continue

    # 5. 判断是否匹配成功
    success = max_similarity >= FACE_MATCH_THRESHOLD
    message = ""
    
    if not success:
        message = f"人脸匹配失败，相似度: {max_similarity:.4f}"
        _log_face_login(None, max_similarity, False, message, ip, device_info, db)
        raise AuthenticationError(message)

    # 6. 检查用户状态
    if matched_user.status != 1:
        message = "用户账号已被禁用"
        _log_face_login(matched_user.id, max_similarity, False, message, ip, device_info, db)
        raise AuthenticationError(message)

    # 7. 更新最后登录时间
    matched_user.last_login_at = datetime.now()
    db.commit()

    # 8. 生成 token
    access_token = create_access_token(matched_user.id)
    refresh_token = create_refresh_token(matched_user.id)

    # 9. 存储 refresh_token 到 Redis
    try:
        refresh_key = f"refresh_token:{matched_user.id}"
        redis_set(refresh_key, refresh_token, ex=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400)
    except Exception:
        pass

    # 10. 获取用户角色
    from app.models.user import UserRole, Role
    user_roles = (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == matched_user.id)
        .all()
    )
    role_list = [
        {"id": r.id, "code": r.code, "name": r.name}
        for r in user_roles
    ]
    is_admin = any(r.code == "admin" for r in user_roles)

    # 11. 记录登录成功日志
    message = f"人脸登录成功，相似度: {max_similarity:.4f}"
    _log_face_login(matched_user.id, max_similarity, True, message, ip, device_info, db)

    logger.info(f"用户 {matched_user.username} 人脸识别登录成功")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": matched_user.id,
            "username": matched_user.username,
            "real_name": matched_user.real_name,
            "phone": matched_user.phone,
            "email": matched_user.email,
            "roles": role_list,
            "is_admin": is_admin,
        },
    }


def enroll_face(user: User, feature_vector: List[float], confidence: float, db: Session) -> FaceTemplate:
    """
    录入人脸模板
    - 校验特征向量
    - 创建或更新人脸模板
    - 更新用户 has_face_template 标志
    """
    # 1. 参数校验
    if len(feature_vector) != 128:
        raise BusinessException(code=400, message="特征向量维度不正确")
    
    if confidence < 0.5:
        raise BusinessException(code=400, message="人脸图像质量过低，请重新拍摄")

    # 2. 检查是否已存在模板
    existing = db.query(FaceTemplate).filter(
        FaceTemplate.user_id == user.id
    ).first()

    # 3. 创建或更新模板
    if existing:
        existing.feature_vector = json.dumps(feature_vector)
        existing.confidence = confidence
        existing.updated_at = datetime.now()
    else:
        existing = FaceTemplate(
            user_id=user.id,
            feature_vector=json.dumps(feature_vector),
            confidence=confidence,
            status=1,
        )
        db.add(existing)

    # 4. 更新用户标志
    user.has_face_template = True
    db.commit()

    logger.info(f"用户 {user.username} 人脸录入成功")
    return existing


def delete_face(user: User, db: Session) -> None:
    """
    删除人脸模板
    - 删除模板记录
    - 更新用户 has_face_template 标志
    """
    template = db.query(FaceTemplate).filter(
        FaceTemplate.user_id == user.id
    ).first()

    if template:
        db.delete(template)
        user.has_face_template = False
        db.commit()
        logger.info(f"用户 {user.username} 人脸模板已删除")


def get_face_template(user: User, db: Session) -> Optional[FaceTemplate]:
    """获取用户人脸模板"""
    return db.query(FaceTemplate).filter(
        FaceTemplate.user_id == user.id
    ).first()


def get_face_login_logs(user_id: Optional[int] = None, db: Session = None, 
                       page: int = 1, page_size: int = 20) -> Tuple[List[FaceLoginLog], int]:
    """获取人脸登录日志"""
    query = db.query(FaceLoginLog)
    if user_id:
        query = query.filter(FaceLoginLog.user_id == user_id)
    query = query.order_by(FaceLoginLog.created_at.desc())
    
    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()
    return logs, total


def _log_face_login(user_id: Optional[int], confidence: float, success: bool, 
                    message: str, ip: str, device_info: str, db: Session) -> None:
    """记录人脸登录日志"""
    try:
        log = FaceLoginLog(
            user_id=user_id,
            confidence=confidence,
            success=success,
            message=message,
            ip_address=ip,
            device_info=device_info,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"记录人脸登录日志失败: {e}")
```

### 3.4 控制器层（API Router）

#### 3.4.1 创建路由文件：`app/api/v1/face.py`

```python
"""
人脸识别相关路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.face import (
    FaceLoginRequest, FaceEnrollRequest, FaceTemplateResponse,
    FaceLoginLogResponse,
)
from app.services import face_service
from app.utils.response import success
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/face", tags=["人脸识别"])


@router.post("/login")
def face_login(
    body: FaceLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    人脸登录
    - 接收前端提取的人脸特征向量
    - 在数据库中进行特征比对
    - 返回 token
    """
    ip = request.client.host if request.client else "unknown"
    result = face_service.face_login(body.feature_vector, body.device_info, ip, db)
    return success(data=result, message="人脸识别登录成功")


@router.post("/enroll")
def enroll_face(
    body: FaceEnrollRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    录入人脸模板
    - 仅用户本人可录入
    - 保存人脸特征向量到数据库
    """
    template = face_service.enroll_face(user, body.feature_vector, body.confidence, db)
    return success(data={
        "id": template.id,
        "confidence": template.confidence,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }, message="人脸录入成功")


@router.delete("/template")
def delete_face(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    删除人脸模板
    - 仅用户本人可删除
    """
    face_service.delete_face(user, db)
    return success(message="人脸模板已删除")


@router.get("/template")
def get_face_template(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取当前用户的人脸模板信息
    """
    template = face_service.get_face_template(user, db)
    if not template:
        return success(data=None, message="未录入人脸")
    return success(data={
        "id": template.id,
        "confidence": template.confidence,
        "status": template.status,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    })


@router.get("/logs")
def get_face_login_logs(
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取人脸登录日志（管理员可查看所有，普通用户只能查看自己）
    """
    from app.models.user import UserRole, Role
    is_admin = db.query(Role).join(UserRole).filter(
        UserRole.user_id == user.id,
        Role.code == "admin"
    ).first() is not None

    if not is_admin:
        user_id = user.id

    logs, total = face_service.get_face_login_logs(user_id, db, page, page_size)
    return paginate_response([{
        "id": log.id,
        "user_id": log.user_id,
        "confidence": log.confidence,
        "success": log.success,
        "message": log.message,
        "ip_address": log.ip_address,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs], total, page, page_size)
```

#### 3.4.2 注册路由到主路由：`app/api/v1/router.py`

```python
from app.api.v1.auth import router as auth_router
from app.api.v1.face import router as face_router
# ... 其他路由

router.include_router(auth_router)
router.include_router(face_router)
# ... 其他路由
```

---

## 四、前端实现（Vue3 + TypeScript）

### 4.1 API 层

#### 4.1.1 创建 API 文件：`frontend/src/api/face.ts`

```typescript
import request from '@/utils/request'

export function faceLogin(data: {
  feature_vector: number[]
  device_info?: string
}) {
  return request.post('/face/login', data)
}

export function enrollFace(data: {
  feature_vector: number[]
  confidence: number
}) {
  return request.post('/face/enroll', data)
}

export function deleteFace() {
  return request.delete('/face/template')
}

export function getFaceTemplate() {
  return request.get('/face/template')
}

export function getFaceLoginLogs(params?: {
  user_id?: number
  page?: number
  page_size?: number
}) {
  return request.get('/face/logs', { params })
}
```

### 4.2 工具层

#### 4.2.1 创建人脸检测工具：`frontend/src/utils/faceDetection.ts`

```typescript
import * as faceapi from '@vladmandic/face-api'

const MODEL_URL = '/models'

export interface FaceDetectionResult {
  success: boolean
  message: string
  featureVector?: number[]
  confidence?: number
}

export async function initFaceApi(): Promise<void> {
  await faceapi.loadSsdMobilenetv1Model(MODEL_URL)
  await faceapi.loadFaceLandmarkModel(MODEL_URL)
  await faceapi.loadFaceRecognitionModel(MODEL_URL)
}

export async function detectAndExtract(
  image: HTMLImageElement | HTMLVideoElement
): Promise<FaceDetectionResult> {
  try {
    const detections = await faceapi.detectAllFaces(image).withFaceLandmarks().withFaceDescriptors()
    
    if (detections.length === 0) {
      return { success: false, message: '未检测到人脸' }
    }
    
    if (detections.length > 1) {
      return { success: false, message: '检测到多张人脸，请确保只有一个人在镜头前' }
    }
    
    const descriptor = detections[0].descriptor
    const featureVector = Array.from(descriptor)
    
    return {
      success: true,
      message: '人脸检测成功',
      featureVector,
      confidence: 1.0,
    }
  } catch (error) {
    console.error('人脸检测失败:', error)
    return { success: false, message: '人脸检测失败，请重试' }
  }
}

export function drawFaceDetection(
  canvas: HTMLCanvasElement,
  image: HTMLVideoElement
): void {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height)
}
```

### 4.3 组件层

#### 4.3.1 创建人脸登录组件：`frontend/src/components/FaceLogin.vue`

```vue
<template>
  <div class="face-login-container">
    <div v-if="!initialized" class="loading-state">
      <el-icon :size="32" color="#409eff"><Loading /></el-icon>
      <p>正在加载人脸识别模型...</p>
    </div>
    
    <div v-else class="camera-container">
      <video
        ref="videoRef"
        class="camera-feed"
        autoplay
        muted
        playsinline
      ></video>
      <canvas ref="canvasRef" class="camera-overlay"></canvas>
      
      <div class="camera-status" :class="{ 'detecting': detecting, 'success': detectSuccess, 'error': detectError }">
        <el-icon :size="20">
          <Loading v-if="detecting" />
          <CheckCircle v-else-if="detectSuccess" />
          <XCircle v-else-if="detectError" />
          <Camera v-else />
        </el-icon>
        <span>{{ statusText }}</span>
      </div>
      
      <div class="camera-controls">
        <el-button
          type="primary"
          size="large"
          :loading="detecting"
          :disabled="!initialized"
          class="detect-btn"
          @click="handleDetect"
        >
          {{ detecting ? '识别中...' : '开始人脸识别' }}
        </el-button>
        
        <el-button
          size="large"
          @click="handleClose"
        >
          返回密码登录
        </el-button>
      </div>
      
      <div class="camera-tips">
        <p>💡 请确保光线充足，正对摄像头</p>
        <p>💡 保持面部在画面中央</p>
        <p>💡 请摘掉帽子和口罩</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { ElMessage, ElLoading } from 'element-plus'
import { Loading, CheckCircle, XCircle, Camera } from '@element-plus/icons-vue'
import { initFaceApi, detectAndExtract } from '@/utils/faceDetection'
import { faceLogin } from '@/api/face'
import { useUserStore } from '@/stores/user'

const emit = defineEmits<{
  (e: 'login-success'): void
  (e: 'close'): void
}>()

const userStore = useUserStore()

const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const initialized = ref(false)
const detecting = ref(false)
const detectSuccess = ref(false)
const detectError = ref(false)
const statusText = ref('请点击开始人脸识别')

let stream: MediaStream | null = null

const initCamera = async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: 'user',
        width: { ideal: 640 },
        height: { ideal: 480 },
      },
      audio: false,
    })
    
    if (videoRef.value) {
      videoRef.value.srcObject = stream
    }
    
    await initFaceApi()
    initialized.value = true
    statusText.value = '摄像头已就绪'
  } catch (error) {
    console.error('摄像头初始化失败:', error)
    ElMessage.error('无法访问摄像头，请检查权限设置')
    statusText.value = '无法访问摄像头'
  }
}

const handleDetect = async () => {
  if (!videoRef.value || !initialized.value) return
  
  detecting.value = true
  detectSuccess.value = false
  detectError.value = false
  statusText.value = '正在检测人脸...'
  
  try {
    const result = await detectAndExtract(videoRef.value)
    
    if (!result.success) {
      detectError.value = true
      statusText.value = result.message
      return
    }
    
    statusText.value = '人脸特征提取成功，正在比对...'
    
    const response = await faceLogin({
      feature_vector: result.featureVector!,
      device_info: navigator.userAgent,
    })
    
    if (response.data && response.data.access_token) {
      userStore.setToken(response.data.access_token, response.data.refresh_token)
      if (response.data.user) {
        userStore.setUserInfo(response.data.user)
      }
      
      await userStore.fetchMenus()
      
      detectSuccess.value = true
      statusText.value = '人脸识别成功！'
      ElMessage.success('人脸识别登录成功')
      
      setTimeout(() => {
        emit('login-success')
      }, 1000)
    }
  } catch (error: any) {
    detectError.value = true
    statusText.value = error.message || '人脸识别失败，请重试'
    console.error('人脸登录失败:', error)
  } finally {
    detecting.value = false
  }
}

const handleClose = () => {
  if (stream) {
    stream.getTracks().forEach(track => track.stop())
  }
  emit('close')
}

onMounted(() => {
  initCamera()
})

onBeforeUnmount(() => {
  if (stream) {
    stream.getTracks().forEach(track => track.stop())
  }
})
</script>

<style scoped>
.face-login-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: #6b7280;
}

.camera-container {
  position: relative;
  width: 100%;
  max-width: 480px;
}

.camera-feed {
  width: 100%;
  height: 360px;
  object-fit: cover;
  border-radius: 12px;
  background: #1f2937;
}

.camera-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 360px;
  pointer-events: none;
}

.camera-status {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.7);
  border-radius: 20px;
  color: #fff;
  font-size: 14px;
}

.camera-status.detecting {
  background: rgba(64, 158, 255, 0.9);
}

.camera-status.success {
  background: rgba(67, 160, 71, 0.9);
}

.camera-status.error {
  background: rgba(239, 68, 68, 0.9);
}

.camera-controls {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.detect-btn {
  flex: 1;
}

.camera-tips {
  margin-top: 16px;
  padding: 12px;
  background: #f3f4f6;
  border-radius: 8px;
}

.camera-tips p {
  margin: 4px 0;
  font-size: 12px;
  color: #6b7280;
}
</style>
```

#### 4.3.2 创建人脸管理组件：`frontend/src/components/FaceManager.vue`

```vue
<template>
  <div class="face-manager">
    <el-card title="人脸管理" class="manager-card">
      <div v-if="!template" class="no-face-state">
        <div class="no-face-icon">
          <el-icon :size="64" color="#9ca3af"><User /></el-icon>
        </div>
        <p>您尚未录入人脸信息</p>
        <el-button type="primary" @click="showEnroll = true">录入人脸</el-button>
      </div>
      
      <div v-else class="has-face-state">
        <div class="face-info">
          <div class="face-icon">
            <el-icon :size="64" color="#409eff"><CheckCircle /></el-icon>
          </div>
          <div class="face-details">
            <p class="face-title">人脸已录入</p>
            <p class="face-meta">录入时间：{{ formatTime(template.created_at) }}</p>
            <p class="face-meta">置信度：{{ (template.confidence * 100).toFixed(1) }}%</p>
          </div>
        </div>
        
        <el-button type="danger" plain @click="handleDelete">删除人脸</el-button>
        <el-button type="primary" @click="showEnroll = true">重新录入</el-button>
      </div>
    </el-card>
    
    <!-- 人脸录入弹窗 -->
    <el-dialog
      v-model="showEnroll"
      title="录入人脸"
      width="520px"
      :close-on-click-modal="false"
      @close="handleEnrollClose"
    >
      <FaceEnroll @success="handleEnrollSuccess" @close="showEnroll = false" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, CheckCircle } from '@element-plus/icons-vue'
import { getFaceTemplate, deleteFace } from '@/api/face'
import FaceEnroll from './FaceEnroll.vue'

interface FaceTemplate {
  id: number
  confidence: number
  status: number
  created_at: string
}

const template = ref<FaceTemplate | null>(null)
const showEnroll = ref(false)

const loadTemplate = async () => {
  try {
    const response = await getFaceTemplate()
    if (response.data) {
      template.value = response.data
    }
  } catch (error) {
    console.error('获取人脸模板失败:', error)
  }
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm('确定要删除人脸模板吗？删除后将无法使用人脸登录', '确认删除', {
      type: 'warning',
    })
    
    await deleteFace()
    template.value = null
    ElMessage.success('人脸模板已删除')
  } catch (error) {
    // 用户取消删除
  }
}

const handleEnrollSuccess = () => {
  showEnroll.value = false
  loadTemplate()
}

const handleEnrollClose = () => {
  showEnroll.value = false
}

const formatTime = (timeStr: string) => {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadTemplate()
})
</script>

<style scoped>
.face-manager {
  padding: 20px;
}

.manager-card {
  max-width: 400px;
  margin: 0 auto;
}

.no-face-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 0;
}

.no-face-icon {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.no-face-state p {
  color: #6b7280;
  margin-bottom: 20px;
}

.has-face-state {
  padding: 20px 0;
}

.face-info {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
}

.face-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: #dcfce7;
  display: flex;
  align-items: center;
  justify-content: center;
}

.face-details {
  flex: 1;
}

.face-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.face-meta {
  font-size: 14px;
  color: #6b7280;
  margin: 4px 0;
}

.has-face-state .el-button {
  margin-right: 12px;
}
</style>
```

#### 4.3.3 创建人脸录入组件：`frontend/src/components/FaceEnroll.vue`

```vue
<template>
  <div class="face-enroll">
    <div v-if="!initialized" class="loading-state">
      <el-icon :size="32" color="#409eff"><Loading /></el-icon>
      <p>正在加载人脸识别模型...</p>
    </div>
    
    <div v-else class="camera-area">
      <video
        ref="videoRef"
        class="enroll-video"
        autoplay
        muted
        playsinline
      ></video>
      
      <div class="enroll-status" :class="{ 'detecting': detecting, 'success': enrollSuccess }">
        <el-icon :size="20">
          <Loading v-if="detecting" />
          <Camera v-else />
        </el-icon>
        <span>{{ statusText }}</span>
      </div>
      
      <div class="enroll-controls">
        <el-button
          type="primary"
          :loading="detecting"
          :disabled="!initialized"
          @click="handleCapture"
        >
          {{ detecting ? '正在录入...' : '拍照录入' }}
        </el-button>
      </div>
      
      <div class="enroll-tips">
        <p>💡 请正对摄像头，保持面部清晰</p>
        <p>💡 请确保光线充足</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading, Camera } from '@element-plus/icons-vue'
import { initFaceApi, detectAndExtract } from '@/utils/faceDetection'
import { enrollFace } from '@/api/face'

const emit = defineEmits<{
  (e: 'success'): void
  (e: 'close'): void
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const initialized = ref(false)
const detecting = ref(false)
const enrollSuccess = ref(false)
const statusText = ref('点击拍照录入人脸')

let stream: MediaStream | null = null

const initCamera = async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: 'user',
        width: { ideal: 640 },
        height: { ideal: 480 },
      },
      audio: false,
    })
    
    if (videoRef.value) {
      videoRef.value.srcObject = stream
    }
    
    await initFaceApi()
    initialized.value = true
    statusText.value = '摄像头已就绪，请点击拍照'
  } catch (error) {
    console.error('摄像头初始化失败:', error)
    ElMessage.error('无法访问摄像头')
  }
}

const handleCapture = async () => {
  if (!videoRef.value || !initialized.value) return
  
  detecting.value = true
  statusText.value = '正在检测人脸...'
  
  try {
    const result = await detectAndExtract(videoRef.value)
    
    if (!result.success) {
      statusText.value = result.message
      return
    }
    
    statusText.value = '正在上传人脸特征...'
    
    await enrollFace({
      feature_vector: result.featureVector!,
      confidence: result.confidence || 0.95,
    })
    
    statusText.value = '人脸录入成功！'
    enrollSuccess.value = true
    ElMessage.success('人脸录入成功')
    
    setTimeout(() => {
      emit('success')
    }, 1500)
  } catch (error: any) {
    statusText.value = error.message || '人脸录入失败，请重试'
    console.error('人脸录入失败:', error)
  } finally {
    detecting.value = false
  }
}

onMounted(() => {
  initCamera()
})

onBeforeUnmount(() => {
  if (stream) {
    stream.getTracks().forEach(track => track.stop())
  }
})
</script>

<style scoped>
.face-enroll {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px;
}

.camera-area {
  width: 100%;
}

.enroll-video {
  width: 100%;
  height: 320px;
  object-fit: cover;
  border-radius: 8px;
  background: #1f2937;
}

.enroll-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  margin-top: 16px;
  background: #f3f4f6;
  border-radius: 8px;
  color: #6b7280;
}

.enroll-status.detecting {
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
}

.enroll-status.success {
  background: rgba(67, 160, 71, 0.1);
  color: #43a047;
}

.enroll-controls {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.enroll-tips {
  margin-top: 16px;
  text-align: center;
}

.enroll-tips p {
  margin: 4px 0;
  font-size: 12px;
  color: #9ca3af;
}
</style>
```

### 4.4 页面层

#### 4.4.1 修改登录页面：`frontend/src/views/Login.vue`

在登录表单上方添加切换按钮：

```vue
<!-- 在 login-header 和 login-form 之间添加 -->
<div class="login-tabs">
  <span 
    class="tab-item" 
    :class="{ active: loginMode === 'password' }"
    @click="loginMode = 'password'"
  >密码登录</span>
  <span 
    class="tab-item" 
    :class="{ active: loginMode === 'face' }"
    @click="loginMode = 'face'"
  >人脸登录</span>
</div>

<!-- 将原表单改为条件渲染 -->
<el-form v-if="loginMode === 'password'" ...>
  <!-- 原密码登录表单内容 -->
</el-form>

<!-- 添加人脸登录组件 -->
<FaceLogin 
  v-else 
  @login-success="handleFaceLoginSuccess" 
  @close="loginMode = 'password'" 
/>
```

在 script 中添加：

```typescript
const loginMode = ref<'password' | 'face'>('password')

const handleFaceLoginSuccess = () => {
  ElMessage.success('登录成功，欢迎回来！')
  router.push('/dashboard')
}
```

添加样式：

```css
.login-tabs {
  display: flex;
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.tab-item {
  flex: 1;
  text-align: center;
  padding: 8px;
  cursor: pointer;
  font-size: 15px;
  color: #6b7280;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
}

.tab-item:hover {
  color: #409eff;
}

.tab-item.active {
  color: #409eff;
  border-bottom-color: #409eff;
  font-weight: 600;
}
```

#### 4.4.2 修改用户管理页面（可选）：`frontend/src/views/system/UserManage.vue`

在用户详情弹窗中添加人脸管理组件，让管理员可以查看用户人脸状态。

### 4.5 路由层

无需修改路由，人脸登录在登录页内切换，人脸管理在个人中心或用户管理页面中。

---

## 五、资源文件

### 5.1 face-api.js 模型文件

需要将以下模型文件放置在 `frontend/public/models/` 目录：

| 文件 | 大小 | 说明 |
|------|------|------|
| `ssd_mobilenetv1_model-shard1` | ~6MB | SSD 人脸检测模型 |
| `ssd_mobilenetv1_model-weights_manifest.json` | 小 | 模型权重清单 |
| `face_landmark_68_model-shard1` | ~3MB | 68点人脸关键点模型 |
| `face_landmark_68_model-weights_manifest.json` | 小 | 模型权重清单 |
| `face_recognition_model-shard1` | ~6MB | 人脸特征提取模型 |
| `face_recognition_model-weights_manifest.json` | 小 | 模型权重清单 |

### 5.2 前端依赖安装

```bash
npm install @vladmandic/face-api
```

---

## 六、安全考虑

| 风险点 | 解决方案 |
|--------|---------|
| **照片攻击** | 眨眼检测（活体检测），要求用户在检测过程中眨眼 |
| **特征泄露** | 前端仅上传特征向量，不上传原始图片 |
| **暴力破解** | Redis 限流：同 IP 5分钟最多尝试5次 |
| **特征伪造** | 设置相似度阈值（0.6），低于阈值拒绝登录 |
| **数据存储** | 特征向量加密存储（可选），日志记录审计 |
| **权限控制** | 仅用户本人可录入/删除人脸，管理员可查看日志 |

---

## 七、部署注意事项

### 7.1 HTTPS 要求

浏览器访问摄像头需要 HTTPS 环境（localhost 除外），生产环境必须配置 HTTPS。

### 7.2 模型文件托管

将模型文件放在 CDN 或静态资源服务器，首次加载可能需要较长时间。

### 7.3 Redis 依赖

人脸登录限流依赖 Redis，确保 Redis 服务正常运行。

---

## 八、测试用例

### 8.1 人脸登录测试

| 测试场景 | 预期结果 |
|---------|---------|
| 未录入人脸的用户尝试登录 | 返回错误："系统暂无已录入人脸" |
| 录入人脸后尝试登录（光线充足） | 登录成功，返回 token |
| 光线不足/人脸不清晰 | 返回错误："未检测到人脸" |
| 多张人脸同时出现 | 返回错误："检测到多张人脸" |
| 相似度低于阈值 | 返回错误："人脸匹配失败" |
| 超过5次尝试 | 返回错误："尝试次数过多" |

### 8.2 人脸管理测试

| 测试场景 | 预期结果 |
|---------|---------|
| 用户首次录入人脸 | 录入成功，数据库新增记录 |
| 用户重新录入人脸 | 更新原有记录，不新增 |
| 用户删除人脸 | 删除成功，has_face_template 变为 false |
| 管理员查看人脸日志 | 可查看所有用户的人脸登录记录 |
| 普通用户查看人脸日志 | 只能查看自己的人脸登录记录 |

---

## 九、开发进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| 1 | 数据库表设计与创建 | 待开发 |
| 2 | 后端模型层（Model） | 待开发 |
| 3 | 后端数据传输层（Schema） | 待开发 |
| 4 | 后端服务层（Service） | 待开发 |
| 5 | 后端控制器层（API） | 待开发 |
| 6 | 前端 API 封装 | 待开发 |
| 7 | 前端工具层（人脸检测） | 待开发 |
| 8 | 前端人脸登录组件 | 待开发 |
| 9 | 前端人脸管理组件 | 待开发 |
| 10 | 前端人脸录入组件 | 待开发 |
| 11 | 登录页集成 | 待开发 |
| 12 | 测试与验证 | 待开发 |