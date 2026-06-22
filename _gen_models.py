import os

files = {}

# ========== models/base.py ==========
files['app/models/base.py'] = '''"""
ORM 基类和通用 Mixin
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Boolean, DateTime, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 声明基类"""
    pass


class TimestampMixin:
    """时间戳 Mixin：created_at + updated_at"""
    created_at = Column(DateTime, default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")


class SoftDeleteMixin(TimestampMixin):
    """软删除 Mixin：is_deleted + deleted_at + created_at + updated_at"""
    is_deleted = Column(Boolean, default=False, nullable=False, comment="软删除标记")
    deleted_at = Column(DateTime, nullable=True, comment="删除时间")

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = datetime.now()
'''

# ========== models/user.py (User, Role, Menu, UserRole, RoleMenu, OperationLog) ==========
files['app/models/user.py'] = '''"""
RBAC 权限体系模型：User, Role, Menu, UserRole, RoleMenu, OperationLog
"""
from sqlalchemy import Column, Integer, String, SmallInteger, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class User(SoftDeleteMixin, Base):
    """用户表 - 所有登录信息的唯一入口"""
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    username = Column(String(50), unique=True, nullable=False, comment="登录用户名")
    password_hash = Column(String(255), nullable=False, comment="bcrypt加密密码")
    real_name = Column(String(50), nullable=False, comment="真实姓名")
    phone = Column(String(20), unique=True, nullable=True, comment="手机号")
    email = Column(String(100), unique=True, nullable=True, comment="邮箱")
    id_card = Column(String(18), unique=True, nullable=True, comment="身份证号")
    avatar = Column(String(255), nullable=True, comment="头像URL")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=正常 0=禁用")
    must_change_password = Column(Boolean, default=True, nullable=False, comment="首次登录强制改密")
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")

    # relationships
    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    teacher = relationship("Teacher", back_populates="user", uselist=False)
    student = relationship("Student", back_populates="user", uselist=False)


class Role(TimestampMixin, Base):
    """角色表"""
    __tablename__ = "role"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    code = Column(String(50), unique=True, nullable=False, comment="角色代码")
    name = Column(String(50), nullable=False, comment="角色名称")
    description = Column(String(255), nullable=True, comment="角色描述")

    # relationships
    role_menus = relationship("RoleMenu", back_populates="role", cascade="all, delete-orphan")
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")


class Menu(TimestampMixin, Base):
    """菜单/权限表 - 树形结构"""
    __tablename__ = "menu"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    parent_id = Column(Integer, ForeignKey("menu.id"), nullable=True, comment="父菜单ID")
    name = Column(String(50), nullable=False, comment="菜单名称")
    code = Column(String(100), unique=True, nullable=False, comment="权限标识")
    type = Column(SmallInteger, nullable=False, comment="1=目录 2=菜单 3=按钮")
    path = Column(String(200), nullable=True, comment="前端路由路径")
    icon = Column(String(50), nullable=True, comment="图标名称")
    sort_order = Column(Integer, default=0, nullable=False, comment="排序权重")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=启用 0=禁用")

    # self-referential relationship
    children = relationship("Menu", backref="parent", remote_side="Menu.id", foreign_keys="Menu.parent_id")
    role_menus = relationship("RoleMenu", back_populates="menu", cascade="all, delete-orphan")


class UserRole(Base):
    """用户-角色关联表"""
    __tablename__ = "user_role"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, comment="用户ID")
    role_id = Column(Integer, ForeignKey("role.id"), nullable=False, comment="角色ID")

    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")


class RoleMenu(Base):
    """角色-菜单关联表"""
    __tablename__ = "role_menu"
    __table_args__ = (UniqueConstraint("role_id", "menu_id", name="uq_role_menu"),)

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    role_id = Column(Integer, ForeignKey("role.id"), nullable=False, comment="角色ID")
    menu_id = Column(Integer, ForeignKey("menu.id"), nullable=False, comment="菜单ID")

    role = relationship("Role", back_populates="role_menus")
    menu = relationship("Menu", back_populates="role_menus")


class OperationLog(Base):
    """操作审计日志表"""
    __tablename__ = "operation_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True, comment="操作人")
    module = Column(String(50), nullable=False, comment="模块名")
    action = Column(String(20), nullable=False, comment="操作类型")
    target_id = Column(Integer, nullable=True, comment="操作对象ID")
    detail = Column(Text, nullable=True, comment="变更详情JSON")
    ip_address = Column(String(50), nullable=True, comment="请求IP")
    created_at = Column(DateTime, nullable=False, comment="操作时间", server_default="CURRENT_TIMESTAMP")
'''

for filepath, content in files.items():
    full_path = os.path.join(r'e:\\student', filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Created: {filepath}')

print('Batch 1 done!')
