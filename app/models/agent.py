"""Campus agent persistence models."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func

from app.models.base import Base


class AgentPendingAction(Base):
    """Pending assistant action waiting for user confirmation."""

    __tablename__ = "agent_pending_action"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, comment="发起用户")
    session_id = Column(String(64), nullable=True, index=True, comment="会话ID")
    tool_code = Column(String(80), nullable=False, index=True, comment="工具编码")
    risk = Column(String(20), nullable=False, default="medium", comment="风险等级")
    status = Column(String(20), nullable=False, default="pending", index=True, comment="状态")
    args_json = Column(Text, nullable=False, comment="工具参数JSON")
    summary = Column(Text, nullable=True, comment="确认摘要")
    result_json = Column(Text, nullable=True, comment="执行结果JSON")
    error_message = Column(Text, nullable=True, comment="错误信息")
    expires_at = Column(DateTime, nullable=False, comment="过期时间")
    executed_at = Column(DateTime, nullable=True, comment="执行时间")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="更新时间")


class AgentTaskDraft(Base):
    """Assistant task draft for multi-turn slot filling."""

    __tablename__ = "agent_task_draft"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, comment="所属用户")
    session_id = Column(String(64), nullable=True, index=True, comment="会话ID")
    module_code = Column(String(50), nullable=False, default="campus_agent", index=True, comment="能力模块")
    mode = Column(String(50), nullable=True, comment="助手模式")
    tool_code = Column(String(80), nullable=False, index=True, comment="工具编码")
    status = Column(String(20), nullable=False, default="active", index=True, comment="状态")
    args_json = Column(Text, nullable=False, comment="已收集参数JSON")
    missing_fields_json = Column(Text, nullable=True, comment="缺失字段JSON")
    candidates_json = Column(Text, nullable=True, comment="候选项JSON")
    message = Column(Text, nullable=True, comment="最近一次追问或说明")
    expires_at = Column(DateTime, nullable=False, index=True, comment="过期时间")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="更新时间")


class AgentLongTermMemory(Base):
    """Durable assistant memory shared by all assistant capabilities."""

    __tablename__ = "agent_long_term_memory"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, comment="所属用户")
    module_code = Column(String(50), nullable=False, default="campus_agent", index=True, comment="能力模块")
    memory_type = Column(String(50), nullable=False, default="event", index=True, comment="记忆类型")
    content = Column(Text, nullable=False, comment="记忆内容")
    payload_json = Column(Text, nullable=True, comment="结构化内容JSON")
    importance = Column(SmallInteger, nullable=False, default=1, comment="重要程度1-5")
    status = Column(String(20), nullable=False, default="active", index=True, comment="状态")
    last_used_at = Column(DateTime, nullable=True, comment="最近召回时间")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="更新时间")
