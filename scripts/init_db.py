"""
种子数据脚本：初始化 admin 账号、预设角色、菜单树、示例数据
运行方式：cd e:\\student && python -m scripts.init_db
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta
from app.database import SessionLocal, engine
from app.core.security import hash_password
from app.config import settings
from app.models.base import Base
from app.models.user import User, Role, Menu, UserRole, RoleMenu
from app.models.department import Department
from app.models.clazz import Clazz
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.course import Course
from app.models.exam import Exam
from app.models.score import Score
from app.models.announcement import Announcement
from app.models.email import EmailMessage, EmailAttachment


def seed_roles(db):
    """创建预设角色"""
    roles_data = [
        {"code": "admin", "name": "系统管理员", "description": "拥有全部权限"},
        {"code": "staff", "name": "教职工", "description": "教职工角色（校长/主任/班主任/教师）"},
        {"code": "student", "name": "学生", "description": "学生角色"},
    ]
    roles = {}
    for rd in roles_data:
        role = db.query(Role).filter(Role.code == rd["code"]).first()
        if not role:
            role = Role(**rd)
            db.add(role)
            db.flush()
            print(f"  [新增] 角色: {rd['name']}")
        else:
            print(f"  [已有] 角色: {rd['name']}")
        roles[rd["code"]] = role
    return roles


def seed_admin(db, admin_role: Role):
    """创建管理员账号"""
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            real_name="系统管理员",
            phone="13800000000",
            email="15893634594@163.com",
            status=1,
            must_change_password=True,
        )
        db.add(admin)
        db.flush()
        db.add(UserRole(user_id=admin.id, role_id=admin_role.id))
        print(f"  [新增] 管理员账号: admin / {settings.DEFAULT_ADMIN_PASSWORD} (邮箱: 15893634594@163.com)")
    else:
        # 如果已有 admin 但邮箱为空或不对，更新为 163 邮箱
        if admin.email != "15893634594@163.com":
            admin.email = "15893634594@163.com"
            db.commit()
            print(f"  [更新] 管理员邮箱 -> 15893634594@163.com")
        else:
            print(f"  [已有] 管理员账号: admin")
    return admin


def seed_menus(db, roles: dict):
    """创建菜单树"""
    menus_data = [
        # 一级目录
        {"name": "系统管理", "code": "system", "type": 1, "path": "/system", "icon": "setting", "sort_order": 1, "status": 1, "children": [
            {"name": "用户管理", "code": "system:user", "type": 2, "path": "/system/user", "icon": "user", "sort_order": 1, "status": 1, "children": [
                {"name": "查看", "code": "system:user:list", "type": 3, "sort_order": 1, "status": 1},
                {"name": "新增", "code": "system:user:create", "type": 3, "sort_order": 2, "status": 1},
                {"name": "编辑", "code": "system:user:update", "type": 3, "sort_order": 3, "status": 1},
                {"name": "删除", "code": "system:user:delete", "type": 3, "sort_order": 4, "status": 1},
            ]},
            {"name": "角色管理", "code": "system:role", "type": 2, "path": "/system/role", "icon": "peoples", "sort_order": 2, "status": 1, "children": [
                {"name": "查看", "code": "system:role:list", "type": 3, "sort_order": 1, "status": 1},
                {"name": "新增", "code": "system:role:create", "type": 3, "sort_order": 2, "status": 1},
                {"name": "编辑", "code": "system:role:update", "type": 3, "sort_order": 3, "status": 1},
                {"name": "删除", "code": "system:role:delete", "type": 3, "sort_order": 4, "status": 1},
            ]},
            {"name": "菜单管理", "code": "system:menu", "type": 2, "path": "/system/menu", "icon": "tree-table", "sort_order": 3, "status": 1, "children": [
                {"name": "查看", "code": "system:menu:list", "type": 3, "sort_order": 1, "status": 1},
                {"name": "新增", "code": "system:menu:create", "type": 3, "sort_order": 2, "status": 1},
                {"name": "编辑", "code": "system:menu:update", "type": 3, "sort_order": 3, "status": 1},
                {"name": "删除", "code": "system:menu:delete", "type": 3, "sort_order": 4, "status": 1},
            ]},
        ]},
        # 组织架构
        {"name": "组织架构", "code": "org", "type": 1, "path": "/org", "icon": "tree", "sort_order": 2, "status": 1, "children": [
            {"name": "院系管理", "code": "org:department", "type": 2, "path": "/org/department", "icon": "school", "sort_order": 1, "status": 1, "children": [
                {"name": "查看", "code": "org:department:list", "type": 3, "sort_order": 1, "status": 1},
                {"name": "新增", "code": "org:department:create", "type": 3, "sort_order": 2, "status": 1},
                {"name": "编辑", "code": "org:department:update", "type": 3, "sort_order": 3, "status": 1},
                {"name": "删除", "code": "org:department:delete", "type": 3, "sort_order": 4, "status": 1},
            ]},
            {"name": "班级管理", "code": "org:clazz", "type": 2, "path": "/org/clazz", "icon": "education", "sort_order": 2, "status": 1, "children": [
                {"name": "查看", "code": "org:clazz:list", "type": 3, "sort_order": 1, "status": 1},
                {"name": "新增", "code": "org:clazz:create", "type": 3, "sort_order": 2, "status": 1},
                {"name": "编辑", "code": "org:clazz:update", "type": 3, "sort_order": 3, "status": 1},
                {"name": "删除", "code": "org:clazz:delete", "type": 3, "sort_order": 4, "status": 1},
            ]},
        ]},
        # 人员管理
        {"name": "人员管理", "code": "people", "type": 1, "path": "/people", "icon": "people", "sort_order": 3, "status": 1, "children": [
            {"name": "教职工管理", "code": "people:teacher", "type": 2, "path": "/people/teacher", "icon": "person", "sort_order": 1, "status": 1, "children": [
                {"name": "查看", "code": "people:teacher:list", "type": 3, "sort_order": 1, "status": 1},
                {"name": "新增", "code": "people:teacher:create", "type": 3, "sort_order": 2, "status": 1},
                {"name": "编辑", "code": "people:teacher:update", "type": 3, "sort_order": 3, "status": 1},
                {"name": "删除", "code": "people:teacher:delete", "type": 3, "sort_order": 4, "status": 1},
            ]},
            {"name": "学生管理", "code": "people:student", "type": 2, "path": "/people/student", "icon": "user", "sort_order": 2, "status": 1, "children": [
                {"name": "查看", "code": "people:student:list", "type": 3, "sort_order": 1, "status": 1},
                {"name": "新增", "code": "people:student:create", "type": 3, "sort_order": 2, "status": 1},
                {"name": "编辑", "code": "people:student:update", "type": 3, "sort_order": 3, "status": 1},
                {"name": "删除", "code": "people:student:delete", "type": 3, "sort_order": 4, "status": 1},
            ]},
        ]},
        # 教学管理
        {"name": "教学管理", "code": "teaching", "type": 1, "path": "/teaching", "icon": "education", "sort_order": 4, "status": 1, "children": [
            {"name": "课程管理", "code": "teaching:course", "type": 2, "path": "/teaching/course", "icon": "documentation", "sort_order": 1, "status": 1, "children": [
                {"name": "查看", "code": "teaching:course:list", "type": 3, "sort_order": 1, "status": 1},
                {"name": "新增", "code": "teaching:course:create", "type": 3, "sort_order": 2, "status": 1},
                {"name": "编辑", "code": "teaching:course:update", "type": 3, "sort_order": 3, "status": 1},
                {"name": "删除", "code": "teaching:course:delete", "type": 3, "sort_order": 4, "status": 1},
            ]},
            {"name": "考试管理", "code": "teaching:exam", "type": 2, "path": "/teaching/exam", "icon": "list", "sort_order": 2, "status": 1, "children": [
                {"name": "查看", "code": "teaching:exam:list", "type": 3, "sort_order": 1, "status": 1},
                {"name": "新增", "code": "teaching:exam:create", "type": 3, "sort_order": 2, "status": 1},
                {"name": "编辑", "code": "teaching:exam:update", "type": 3, "sort_order": 3, "status": 1},
                {"name": "删除", "code": "teaching:exam:delete", "type": 3, "sort_order": 4, "status": 1},
            ]},
            {"name": "成绩管理", "code": "teaching:score", "type": 2, "path": "/teaching/score", "icon": "chart", "sort_order": 3, "status": 1, "children": [
                {"name": "查看", "code": "teaching:score:list", "type": 3, "sort_order": 1, "status": 1},
                {"name": "录入", "code": "teaching:score:create", "type": 3, "sort_order": 2, "status": 1},
                {"name": "编辑", "code": "teaching:score:update", "type": 3, "sort_order": 3, "status": 1},
                {"name": "删除", "code": "teaching:score:delete", "type": 3, "sort_order": 4, "status": 1},
            ]},
        ]},
        # 公告管理
        {"name": "公告管理", "code": "announcement", "type": 1, "path": "/announcement", "icon": "message", "sort_order": 5, "status": 1, "children": [
            {"name": "公告列表", "code": "announcement:list", "type": 2, "path": "/announcement/list", "icon": "list", "sort_order": 1, "status": 1, "children": [
                {"name": "查看", "code": "announcement:list:view", "type": 3, "sort_order": 1, "status": 1},
            ]},
            {"name": "发布公告", "code": "announcement:create", "type": 2, "path": "/announcement/create", "icon": "edit", "sort_order": 2, "status": 1, "children": [
                {"name": "发布", "code": "announcement:publish", "type": 3, "sort_order": 1, "status": 1},
                {"name": "编辑", "code": "announcement:update", "type": 3, "sort_order": 2, "status": 1},
                {"name": "删除", "code": "announcement:delete", "type": 3, "sort_order": 3, "status": 1},
            ]},
        ]},
    ]

    all_menu_ids = []

    def _create_menus(items, parent_id=None):
        for item in items:
            children = item.pop("children", [])
            existing = db.query(Menu).filter(Menu.code == item["code"]).first()
            if existing:
                menu = existing
            else:
                menu = Menu(**item, parent_id=parent_id)
                db.add(menu)
                db.flush()
                print(f"  [新增] 菜单: {item['name']} ({item['code']})")
            all_menu_ids.append(menu.id)
            if children:
                _create_menus(children, menu.id)

    _create_menus(menus_data)

    # admin 角色分配所有菜单
    admin_role = roles.get("admin")
    if admin_role:
        existing_menu_ids = {rm.menu_id for rm in db.query(RoleMenu).filter(RoleMenu.role_id == admin_role.id).all()}
        for mid in all_menu_ids:
            if mid not in existing_menu_ids:
                db.add(RoleMenu(role_id=admin_role.id, menu_id=mid))
        print(f"  [分配] admin 角色已分配 {len(all_menu_ids)} 个菜单权限")

    # staff 角色分配查看类权限 + 公告发布
    staff_role = roles.get("staff")
    if staff_role:
        staff_menu_codes = [
            "org", "org:department", "org:department:list",
            "org:clazz", "org:clazz:list", "org:clazz:create", "org:clazz:update", "org:clazz:delete",
            "people", "people:teacher", "people:teacher:list",
            "people:student", "people:student:list", "people:student:create", "people:student:update", "people:student:delete",
            "teaching", "teaching:course", "teaching:course:list", "teaching:course:create", "teaching:course:update", "teaching:course:delete",
            "teaching:exam", "teaching:exam:list", "teaching:exam:create", "teaching:exam:update", "teaching:exam:delete",
            "teaching:score", "teaching:score:list", "teaching:score:create", "teaching:score:update",
            "announcement", "announcement:list", "announcement:list:view",
            "announcement:create", "announcement:publish", "announcement:update", "announcement:delete",
        ]
        staff_menus = db.query(Menu).filter(Menu.code.in_(staff_menu_codes)).all()
        existing_ids = {rm.menu_id for rm in db.query(RoleMenu).filter(RoleMenu.role_id == staff_role.id).all()}
        for m in staff_menus:
            if m.id not in existing_ids:
                db.add(RoleMenu(role_id=staff_role.id, menu_id=m.id))
        print(f"  [分配] staff 角色已分配 {len(staff_menus)} 个菜单权限")

    # student 角色分配查看类权限
    student_role = roles.get("student")
    if student_role:
        student_menu_codes = [
            "org", "org:department", "org:department:list",
            "org:clazz", "org:clazz:list",
            "people", "people:teacher", "people:teacher:list",
            "people:student", "people:student:list",
            "teaching", "teaching:course", "teaching:course:list",
            "teaching:exam", "teaching:exam:list",
            "teaching:score", "teaching:score:list",
            "announcement", "announcement:list", "announcement:list:view",
        ]
        student_menus = db.query(Menu).filter(Menu.code.in_(student_menu_codes)).all()
        existing_ids = {rm.menu_id for rm in db.query(RoleMenu).filter(RoleMenu.role_id == student_role.id).all()}
        for m in student_menus:
            if m.id not in existing_ids:
                db.add(RoleMenu(role_id=student_role.id, menu_id=m.id))
        print(f"  [分配] student 角色已分配 {len(student_menus)} 个菜单权限")


def seed_sample_data(db, roles: dict):
    """创建示例数据：院系、班级、教职工、学生、课程、考试、成绩、公告"""
    # ============ 院系 ============
    depts_data = [
        {"name": "计算机科学与技术学院", "code": "CS", "description": "培养计算机专业人才", "status": 1},
        {"name": "数学与统计学院", "code": "MATH", "description": "数学研究与统计学科建设", "status": 1},
        {"name": "外国语学院", "code": "LANG", "description": "英语及其他外国语教学", "status": 1},
        {"name": "经济管理学院", "code": "ECON", "description": "经济学与管理学教学", "status": 1},
        {"name": "艺术与设计学院", "code": "ART", "description": "艺术创作与设计教育", "status": 1},
    ]
    depts = {}
    for dd in depts_data:
        dept = db.query(Department).filter(Department.code == dd["code"]).first()
        if not dept:
            dept = Department(**dd)
            db.add(dept)
            db.flush()
            print(f"  [新增] 院系: {dd['name']}")
        depts[dd["code"]] = dept

    # ============ 班级 ============
    clazzes_data = [
        # 计算机
        {"name": "计算机2201班", "code": "CS2201", "department_id": depts["CS"].id, "grade": "2022", "status": 1},
        {"name": "计算机2202班", "code": "CS2202", "department_id": depts["CS"].id, "grade": "2022", "status": 1},
        {"name": "计算机2301班", "code": "CS2301", "department_id": depts["CS"].id, "grade": "2023", "status": 1},
        {"name": "计算机2302班", "code": "CS2302", "department_id": depts["CS"].id, "grade": "2023", "status": 1},
        # 数学
        {"name": "数学2201班", "code": "MATH2201", "department_id": depts["MATH"].id, "grade": "2022", "status": 1},
        {"name": "数学2301班", "code": "MATH2301", "department_id": depts["MATH"].id, "grade": "2023", "status": 1},
        # 外语
        {"name": "英语2201班", "code": "LANG2201", "department_id": depts["LANG"].id, "grade": "2022", "status": 1},
        {"name": "英语2301班", "code": "LANG2301", "department_id": depts["LANG"].id, "grade": "2023", "status": 1},
        # 经管
        {"name": "经济2301班", "code": "ECON2301", "department_id": depts["ECON"].id, "grade": "2023", "status": 1},
        {"name": "管理2301班", "code": "ECON2302", "department_id": depts["ECON"].id, "grade": "2023", "status": 1},
        # 艺术
        {"name": "艺术设计2301班", "code": "ART2301", "department_id": depts["ART"].id, "grade": "2023", "status": 1},
        {"name": "艺术设计2302班", "code": "ART2302", "department_id": depts["ART"].id, "grade": "2023", "status": 1},
    ]
    clazzes = {}
    for cd in clazzes_data:
        clazz = db.query(Clazz).filter(Clazz.code == cd["code"]).first()
        if not clazz:
            clazz = Clazz(**cd)
            db.add(clazz)
            db.flush()
            print(f"  [新增] 班级: {cd['name']}")
        clazzes[cd["code"]] = clazz

    # ============ 教职工 ============
    staff_role = roles.get("staff")
    teachers_data = [
        {"username": "teacher01", "real_name": "张伟", "phone": "13800000001",
         "employee_no": "T2022001", "name": "张伟", "gender": 1, "id_card": "110101198001011234",
         "position": "教师", "title": "教授", "department_id": depts["CS"].id, "entry": 2008},
        {"username": "teacher02", "real_name": "李娜", "phone": "13800000002",
         "employee_no": "T2022002", "name": "李娜", "gender": 2, "id_card": "110101198505051234",
         "position": "院系主任", "title": "副教授", "department_id": depts["CS"].id, "entry": 2012},
        {"username": "teacher03", "real_name": "王强", "phone": "13800000003",
         "employee_no": "T2022003", "name": "王强", "gender": 1, "id_card": "110101198803031234",
         "position": "教师", "title": "讲师", "department_id": depts["CS"].id, "entry": 2015},
        {"username": "teacher04", "real_name": "刘敏", "phone": "13800000004",
         "employee_no": "T2022004", "name": "刘敏", "gender": 2, "id_card": "110101198904041234",
         "position": "教师", "title": "讲师", "department_id": depts["CS"].id, "entry": 2017},
        {"username": "teacher05", "real_name": "陈静", "phone": "13800000005",
         "employee_no": "T2022005", "name": "陈静", "gender": 2, "id_card": "110101198706061234",
         "position": "教师", "title": "副教授", "department_id": depts["MATH"].id, "entry": 2013},
        {"username": "teacher06", "real_name": "杨光", "phone": "13800000006",
         "employee_no": "T2022006", "name": "杨光", "gender": 1, "id_card": "110101198202021234",
         "position": "教师", "title": "讲师", "department_id": depts["MATH"].id, "entry": 2010},
        {"username": "teacher07", "real_name": "周丽", "phone": "13800000007",
         "employee_no": "T2022007", "name": "周丽", "gender": 2, "id_card": "110101199007071234",
         "position": "教师", "title": "讲师", "department_id": depts["LANG"].id, "entry": 2016},
        {"username": "teacher08", "real_name": "吴磊", "phone": "13800000008",
         "employee_no": "T2022008", "name": "吴磊", "gender": 1, "id_card": "110101199108081234",
         "position": "教师", "title": "助教", "department_id": depts["LANG"].id, "entry": 2018},
        {"username": "teacher09", "real_name": "赵敏", "phone": "13800000009",
         "employee_no": "T2022009", "name": "赵敏", "gender": 2, "id_card": "110101198609091234",
         "position": "教师", "title": "讲师", "department_id": depts["ECON"].id, "entry": 2014},
        {"username": "teacher10", "real_name": "钱峰", "phone": "13800000010",
         "employee_no": "T2022010", "name": "钱峰", "gender": 1, "id_card": "110101198410101234",
         "position": "教师", "title": "讲师", "department_id": depts["ECON"].id, "entry": 2011},
        {"username": "teacher11", "real_name": "孙悦", "phone": "13800000011",
         "employee_no": "T2022011", "name": "孙悦", "gender": 2, "id_card": "110101198311111234",
         "position": "教师", "title": "讲师", "department_id": depts["ART"].id, "entry": 2009},
        {"username": "teacher12", "real_name": "郑凯", "phone": "13800000012",
         "employee_no": "T2022012", "name": "郑凯", "gender": 1, "id_card": "110101198512121234",
         "position": "教师", "title": "讲师", "department_id": depts["ART"].id, "entry": 2015},
    ]
    teachers_map = {}
    for td in teachers_data:
        user = db.query(User).filter(User.username == td["username"]).first()
        if not user:
            user = User(
                username=td["username"],
                password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
                real_name=td["real_name"],
                phone=td["phone"],
                status=1,
                must_change_password=True,
            )
            db.add(user)
            db.flush()
            if staff_role:
                db.add(UserRole(user_id=user.id, role_id=staff_role.id))
            teacher = Teacher(
                user_id=user.id,
                employee_no=td["employee_no"],
                name=td["name"],
                gender=td["gender"],
                id_card=td["id_card"],
                position=td["position"],
                title=td["title"],
                department_id=td["department_id"],
                entry_date=date(td["entry"], 9, 1),
                status=1,
            )
            db.add(teacher)
            db.flush()
            print(f"  [新增] 教职工: {td['name']} ({td['username']})")
            teachers_map[td["username"]] = teacher

    # ============ 学生 ============
    student_role = roles.get("student")
    # 学生姓名模板：姓氏 + 名字
    surnames = ["王", "李", "张", "刘", "陈", "杨", "赵", "周", "吴", "徐", "孙", "胡", "朱", "高", "马", "郑", "何", "林", "黄"]
    given_names_m = ["伟", "强", "磊", "军", "勇", "杰", "涛", "鹏", "浩", "宇", "轩", "然", "昊", "博", "凯", "毅", "泽", "天", "文"]
    given_names_f = ["芳", "娜", "敏", "静", "丽", "艳", "婷", "颖", "蕾", "娟", "燕", "华", "芬", "欣", "怡", "琳", "琪", "晴", "妍"]
    clazz_codes = list(clazzes.keys())

    total_students = 48  # 平均每班 4 人
    student_counter = 0
    students_map = {}
    for idx in range(total_students):
        clazz_code = clazz_codes[idx % len(clazz_codes)]
        clazz_id = clazzes[clazz_code].id
        student_idx = idx + 1
        gender = 1 if idx % 3 != 0 else 2
        if gender == 1:
            name = surnames[idx % len(surnames)] + given_names_m[idx % len(given_names_m)]
        else:
            name = surnames[(idx + 2) % len(surnames)] + given_names_f[(idx * 2) % len(given_names_f)]

        username = f"student{student_idx:02d}"
        phone = f"139{student_idx:08d}"  # 11 位手机号
        id_card = f"320101199910{student_idx:04d}"
        id_card = id_card[:18] if len(id_card) > 18 else id_card.ljust(18, "0")
        student_no = f"S2023{student_idx:04d}"

        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(
                username=username,
                password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
                real_name=name,
                phone=phone,
                status=1,
                must_change_password=True,
            )
            db.add(user)
            db.flush()
            if student_role:
                db.add(UserRole(user_id=user.id, role_id=student_role.id))

            student = Student(
                user_id=user.id,
                student_no=student_no,
                name=name,
                gender=gender,
                id_card=id_card,
                clazz_id=clazz_id,
                enrollment_date=date(2023, 9, 1),
                status=1,
            )
            db.add(student)
            db.flush()
            students_map[username] = student
            student_counter += 1
            if student_counter % 10 == 0:
                print(f"  [新增] 学生: {name} ({username})")
        else:
            students_map[username] = db.query(Student).filter(Student.user_id == user.id).first()

    if student_counter > 0:
        print(f"  [新增] 共新增 {student_counter} 名学生")

    # ============ 课程 ============
    # 以院系教师ID
    cs_teacher_id = teachers_map.get("teacher01").id
    math_teacher_id = teachers_map.get("teacher02").id
    lang_teacher_id = teachers_map.get("teacher07").id
    econ_teacher_id = teachers_map.get("teacher09").id
    art_teacher_id = teachers_map.get("teacher11").id

    courses_data = [
        # 计算机学院课程
        {"name": "高等数学", "code": "MATH101", "department_id": depts["CS"].id, "teacher_id": cs_teacher_id, "credits": 4, "hours": 64, "status": 1, "description": "高数"},
        {"name": "线性代数", "code": "MATH102", "department_id": depts["CS"].id, "teacher_id": cs_teacher_id, "credits": 3, "hours": 48, "status": 1, "description": "线性代数基础"},
        {"name": "计算机程序设计", "code": "CS101", "department_id": depts["CS"].id, "teacher_id": cs_teacher_id, "credits": 4, "hours": 64, "status": 1, "description": "程序设计入门"},
        {"name": "数据结构", "code": "CS201", "department_id": depts["CS"].id, "teacher_id": cs_teacher_id, "credits": 3, "hours": 48, "status": 1, "description": "数据结构与算法"},
        {"name": "计算机网络", "code": "CS301", "department_id": depts["CS"].id, "teacher_id": cs_teacher_id, "credits": 3, "hours": 48, "status": 1, "description": "网络基础"},
        # 数学学院课程
        {"name": "数学分析", "code": "MATH201", "department_id": depts["MATH"].id, "teacher_id": math_teacher_id, "credits": 4, "hours": 64, "status": 1, "description": "实分析与复分析"},
        {"name": "概率论", "code": "MATH202", "department_id": depts["MATH"].id, "teacher_id": math_teacher_id, "credits": 3, "hours": 48, "status": 1, "description": "概率基础"},
        # 外语学院课程
        {"name": "大学英语", "code": "LANG101", "department_id": depts["LANG"].id, "teacher_id": lang_teacher_id, "credits": 4, "hours": 64, "status": 1, "description": "大学英语课程"},
        {"name": "英语口语", "code": "LANG201", "department_id": depts["LANG"].id, "teacher_id": lang_teacher_id, "credits": 2, "hours": 32, "status": 1, "description": "口语训练"},
        # 经管学院课程
        {"name": "经济学原理", "code": "ECON101", "department_id": depts["ECON"].id, "teacher_id": econ_teacher_id, "credits": 3, "hours": 48, "status": 1, "description": "经济学基础"},
        # 艺术学院课程
        {"name": "设计基础", "code": "ART101", "department_id": depts["ART"].id, "teacher_id": art_teacher_id, "credits": 3, "hours": 48, "status": 1, "description": "设计学基础"},
    ]
    course_map = {}
    for cd in courses_data:
        course = db.query(Course).filter(Course.code == cd["code"]).first()
        if not course:
            course = Course(
                name=cd["name"], code=cd["code"], department_id=cd["department_id"],
                teacher_id=cd["teacher_id"], credits=cd["credits"], hours=cd["hours"],
                status=cd["status"], description=cd["description"],
            )
            db.add(course)
            db.flush()
            course_map[cd["code"]] = course
    print(f"  [新增] 课程总数: {len(course_map)}")

    # ============ 考试 ============
    # 为每门课生成一个期末考试（只给前 3 个班级，避免数据过多）
    import random
    random.seed(42)  # 固定种子，保证可重复

    exam_counter = 0
    for code, course in course_map.items():
        for clazz_code in clazz_codes[:3]:  # 只给前 3 个班级生成考试
            exam = Exam(
                name=f"{course.name} - 期末考试",
                course_id=course.id,
                clazz_id=clazzes[clazz_code].id,
                exam_date=date(2024, 1, 15),
                exam_time="09:00:00",
                duration=120,
                total_score=100,
                status=1,
                description=f"{course.name}期末考试",
            )
            db.add(exam)
            db.flush()
            exam_counter += 1

            # 为该班级的所有学生添加成绩
            clazz_id = clazzes[clazz_code].id
            student_list = db.query(Student).filter(Student.clazz_id == clazz_id).all()
            for student in student_list:
                score_val = random.randint(55, 100)
                grade = "优" if score_val >= 90 else "良" if score_val >= 80 else "中" if score_val >= 70 else "及格" if score_val >= 60 else "不及格"
                score = Score(
                    student_id=student.id,
                    exam_id=exam.id,
                    score=score_val,
                    grade=grade,
                    scorer_id=teachers_map.get("teacher01").id,
                    comments="考试成绩",
                )
                db.add(score)
                db.flush()

    if exam_counter > 0:
        print(f"  [新增] 考试/成绩记录共 {exam_counter} 场考试")

    # ============ 公告 ============
    announcements_data = [
        {"title": "2024春季学期开学典礼通知", "content": "各位同学、老师：2024春季学期开学典礼定于2024年2月26日上午9点在学校大礼堂举行，请全体师生准时参加。"},
        {"title": "关于2024年春季运动会通知", "content": "学校将于2024年4月15日至17日举办春季运动会，各学院请于3月1日前完成报名。"},
        {"title": "图书馆新书上架通知", "content": "图书馆新采购了一批计算机专业书籍，涵盖数据结构、算法、操作系统等热门领域，欢迎同学们前往借阅。"},
        {"title": "期末考试时间安排通知", "content": "2024春季学期期末考试定于6月15日至6月30日，具体时间安排请以系办公室公告为准。"},
        {"title": "学生信息管理系统使用培训通知", "content": "新学生信息管理系统已上线，请各位师生使用新系统进行信息管理，如有问题请联系管理员。"},
    ]
    existing_announcements = db.query(Announcement).count()
    if existing_announcements == 0:
        admin_user = db.query(User).filter(User.username == "admin").first()
        admin_id = admin_user.id if admin_user else 1
        for ad in announcements_data:
            announcement = Announcement(
                title=ad["title"], content=ad["content"], publisher_id=admin_id,
                status=1,
            )
            db.add(announcement)
            db.flush()
        print(f"  [新增] 公告数量: {len(announcements_data)}")
    else:
        print(f"  [跳过] 公告已存在: {existing_announcements}")



def main():
    print("=" * 60)
    print("  学生信息管理系统 - 种子数据初始化")
    print("=" * 60)

    # [0] 先创建所有表结构（若数据库不存在）
    print("\n[0/4] 创建数据库表结构...")
    try:
        Base.metadata.create_all(bind=engine)
        print(f"  [成功] 已创建 {len(Base.metadata.tables)} 张表: {', '.join(Base.metadata.tables.keys())}")
    except Exception as e:
        print(f"  [警告] 表结构创建失败（若表已存在可忽略）: {e}")

    db = SessionLocal()
    try:
        print("\n[1/4] 创建角色...")
        roles = seed_roles(db)

        print("\n[2/4] 创建管理员账号...")
        seed_admin(db, roles["admin"])

        print("\n[3/4] 创建菜单树...")
        seed_menus(db, roles)

        print("\n[4/4] 创建示例数据（院系/班级/师生/课程/考试/成绩/公告）...")
        seed_sample_data(db, roles)

        db.commit()
        print("\n" + "=" * 60)
        print("  种子数据初始化完成!")
        print(f"  管理员账号: admin / {settings.DEFAULT_ADMIN_PASSWORD}")
        print(f"  教职工账号: teacher01 / {settings.DEFAULT_USER_PASSWORD}")
        print(f"  学生账号: student01 / {settings.DEFAULT_USER_PASSWORD}")
        print("=" * 60)
    except Exception as e:
        db.rollback()
        print(f"\n  [错误] 初始化失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
