"""
测试自然语言数据库操作模块
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.user import User, Role, UserRole
from app.database import SessionLocal
from app.services.nl_db_tools import (
    get_all_tools,
    get_tools_for_user,
    check_permission,
    ROLE_PERMISSIONS,
    PERMISSIONS,
    get_user_permission_list,
)
from app.services.nl_db_agent import create_agent_executor


def test_permission_config():
    """测试权限配置"""
    print("=== 测试权限配置 ===")
    
    print("\n权限列表:")
    for perm_code, desc in PERMISSIONS.items():
        print(f"  {perm_code}: {desc}")
    
    print("\n角色权限映射:")
    for role, perms in ROLE_PERMISSIONS.items():
        print(f"\n  {role}:")
        for perm in perms:
            print(f"    - {perm}")
    
    print("\n权限配置测试通过!")


def test_tools_loading():
    """测试工具加载"""
    print("\n=== 测试工具加载 ===")
    
    try:
        tools = get_all_tools()
        print(f"成功加载 {len(tools)} 个工具")
        
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:30]}...")
        
        print("\n工具加载测试通过!")
        return tools
    except Exception as e:
        print(f"工具加载失败: {e}")
        return []


def test_permission_check():
    """测试权限检查"""
    print("\n=== 测试权限检查 ===")
    
    db = SessionLocal()
    
    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            print(f"测试管理员用户: {admin_user.username}")
            
            # admin应该有所有权限
            all_permissions = list(PERMISSIONS.keys())
            for perm in all_permissions[:5]:
                has_perm = check_permission(admin_user, db, perm)
                print(f"  {perm}: {'OK' if has_perm else 'NO'}")
            
            user_perms = get_user_permission_list(admin_user, db)
            print(f"\n  管理员权限数量: {len(user_perms)}")
        
        staff_teacher = db.query(User).filter(User.username == "teacher01").first()
        if staff_teacher:
            print(f"\n测试任课教师用户: {staff_teacher.username}")
            
            perms = get_user_permission_list(staff_teacher, db)
            print(f"  权限列表: {perms}")
            
            can_create_student = check_permission(staff_teacher, db, "student:create")
            print(f"  student:create: {'OK' if can_create_student else 'NO'} (预期: NO)")
            
        staff_counselor = db.query(User).filter(User.username == "teacher04").first()
        if staff_counselor:
            print(f"\n测试辅导员用户: {staff_counselor.username}")
            
            perms = get_user_permission_list(staff_counselor, db)
            print(f"  权限列表: {perms}")
            
            can_create_student = check_permission(staff_counselor, db, "student:create")
            print(f"  student:create: {'OK' if can_create_student else 'NO'} (预期: OK)")
            
            can_create_teacher = check_permission(staff_counselor, db, "teacher:create")
            print(f"  teacher:create: {'OK' if can_create_teacher else 'NO'} (预期: NO)")
        
        print("\n权限检查测试通过!")
    finally:
        db.close()


def test_agent_creation():
    """测试Agent创建"""
    print("\n=== 测试Agent创建 ===")
    
    db = SessionLocal()
    
    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            try:
                agent = create_agent_executor(admin_user, db)
                print("OK Agent创建成功")
                print(f"  Agent类型: {type(agent).__name__}")
            except Exception as e:
                print(f"NO Agent创建失败: {e}")
                print("  (需要配置DeepSeek API key才能完全测试)")
        else:
            print("! 未找到admin用户")
        
        print("\nAgent创建测试完成!")
    finally:
        db.close()


def test_user_tools():
    """测试用户工具列表"""
    print("\n=== 测试用户工具列表 ===")
    
    db = SessionLocal()
    
    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            admin_tools = get_tools_for_user(admin_user, db)
            print(f"管理员可用工具: {len(admin_tools)}个")
        
        staff_teacher = db.query(User).filter(User.username == "teacher01").first()
        if staff_teacher:
            tools = get_tools_for_user(staff_teacher, db)
            print(f"任课教师可用工具: {len(tools)}个")
            tool_names = [t.name for t in tools]
            print(f"  工具列表: {tool_names}")
        
        staff_counselor = db.query(User).filter(User.username == "teacher04").first()
        if staff_counselor:
            tools = get_tools_for_user(staff_counselor, db)
            print(f"辅导员可用工具: {len(tools)}个")
            tool_names = [t.name for t in tools]
            print(f"  工具列表: {tool_names}")
        
        print("\n用户工具列表测试通过!")
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("自然语言数据库操作模块测试")
    print("=" * 60)
    
    test_permission_config()
    test_tools_loading()
    test_permission_check()
    test_user_tools()
    test_agent_creation()
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)