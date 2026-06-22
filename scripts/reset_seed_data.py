"""清理并重新插入完整的种子数据
运行方式: cd e:\student && python -m scripts.reset_seed_data
"""
import sys
import os
from datetime import date, datetime
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def main():
    print("=" * 60)
    print("  学生信息管理系统 - 种子数据初始化")
    print("=" * 60)

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # ============================================================
        # 1. 清理旧数据
        # ============================================================
        print("\n[1/7] 清理旧数据...")
        conn = db.connection()
        conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 0")
        tables = [
            "email_attachment", "email_message", "score", "exam", "course",
            "student_course", "teacher_clazz", "student", "teacher",
            "clazz", "department", "announcement_read", "announcement",
            "role_menu", "user_role", "role", "menu", "operation_log",
        ]
        for t in tables:
            conn.exec_driver_sql(f"DELETE FROM `{t}`")
        conn.exec_driver_sql("DELETE FROM user WHERE username != 'admin'")
        conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 1")
        db.commit()
        print("  [完成] 旧数据已清理")

        # ============================================================
        # 2. 创建角色（精细化角色体系）
        # ============================================================
        print("\n[2/7] 创建角色...")
        roles_data = [
            {"code": "admin",          "name": "系统管理员", "description": "拥有全部权限"},
            {"code": "staff_teacher",  "name": "任课教师",   "description": "管理课程、考试、成绩，查看学生信息"},
            {"code": "staff_dean",     "name": "院系主任",   "description": "管理本院系的教师、学生、课程"},
            {"code": "staff_counselor","name": "辅导员",     "description": "管理班级和学生信息"},
            {"code": "staff_affairs",  "name": "教务管理员", "description": "管理课程、考试、成绩的系统级配置"},
            {"code": "student",        "name": "学生",       "description": "查看个人信息、成绩、课程、公告、邮件"},
        ]
        roles = {}
        for rd in roles_data:
            role = Role(code=rd["code"], name=rd["name"], description=rd["description"])
            db.add(role)
            db.flush()
            roles[rd["code"]] = role
            print(f"  [新增] 角色: {rd['name']}")

        # ============================================================
        # 3. 管理员账号
        # ============================================================
        print("\n[3/7] 管理员账号...")
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                real_name="系统管理员",
                phone="13800000000",
                email="admin@school.edu.cn",
                status=1,
                must_change_password=True,
            )
            db.add(admin)
            db.flush()
            db.add(UserRole(user_id=admin.id, role_id=roles["admin"].id))
            print(f"  [新增] 管理员: admin / {settings.DEFAULT_ADMIN_PASSWORD}")
        else:
            admin.real_name = "系统管理员"
            admin.email = "admin@school.edu.cn"
            if not db.query(UserRole).filter(UserRole.user_id == admin.id).first():
                db.add(UserRole(user_id=admin.id, role_id=roles["admin"].id))
            print(f"  [更新] 管理员: admin")

        # ============================================================
        # 4. 菜单树 + 角色-菜单关联（精细化权限）
        # ============================================================
        print("\n[4/7] 创建菜单树...")
        # (name, code, type, path, icon, children)
        menus_data = [
            ("首页概览", "dashboard", 2, "/dashboard", "HomeFilled", []),
            ("系统管理", "system", 1, "/system", "Setting", [
                ("用户管理", "system:user", 2, "/system/user", "User", []),
                ("角色管理", "system:role", 2, "/system/role", "UserFilled", []),
                ("菜单管理", "system:menu", 2, "/system/menu", "Menu", []),
            ]),
            ("组织架构", "org", 1, "/org", "OfficeBuilding", [
                ("院系管理", "org:department", 2, "/org/department", "School", []),
                ("班级管理", "org:clazz", 2, "/org/clazz", "Collection", []),
            ]),
            ("人员管理", "people", 1, "/people", "Avatar", [
                ("教职工管理", "people:teacher", 2, "/people/teacher", "Avatar", []),
                ("学生管理", "people:student", 2, "/people/student", "Postcard", []),
            ]),
            ("教学管理", "teaching", 1, "/teaching", "Reading", [
                ("课程管理", "teaching:course", 2, "/teaching/course", "Notebook", []),
                ("考试管理", "teaching:exam", 2, "/teaching/exam", "Tickets", []),
                ("成绩管理", "teaching:score", 2, "/teaching/score", "DataAnalysis", []),
            ]),
            ("公告管理", "announcement", 1, "/announcement", "Bell", [
                ("公告列表", "announcement:list", 2, "/announcement", "Bell", []),
            ]),
            ("邮件系统", "email", 1, "/email", "Message", [
                ("收件箱", "email:inbox", 2, "/email/inbox", "Inbox", []),
                ("已发送", "email:sent", 2, "/email/sent", "Promotion", []),
                ("写邮件", "email:compose", 2, "/email/compose", "EditPen", []),
            ]),
        ]

        # 每个角色允许的菜单 code 列表
        role_menu_codes = {
            "admin": None,  # None = 全部菜单
            "staff_teacher": {
                "dashboard",
                "org", "org:department", "org:clazz",
                "people", "people:student",
                "teaching", "teaching:course", "teaching:exam", "teaching:score",
                "announcement", "announcement:list",
                "email", "email:inbox", "email:sent", "email:compose",
            },
            "staff_dean": {
                "dashboard",
                "org", "org:department", "org:clazz",
                "people", "people:teacher", "people:student",
                "teaching", "teaching:course", "teaching:exam", "teaching:score",
                "announcement", "announcement:list",
                "email", "email:inbox", "email:sent", "email:compose",
            },
            "staff_counselor": {
                "dashboard",
                "org", "org:department", "org:clazz",
                "people", "people:student",
                "announcement", "announcement:list",
                "email", "email:inbox", "email:sent", "email:compose",
            },
            "staff_affairs": {
                "dashboard",
                "org", "org:department", "org:clazz",
                "people", "people:teacher", "people:student",
                "teaching", "teaching:course", "teaching:exam", "teaching:score",
                "announcement", "announcement:list",
                "email", "email:inbox", "email:sent", "email:compose",
            },
            "student": {
                "dashboard",
                "announcement", "announcement:list",
                "email", "email:inbox", "email:sent", "email:compose",
            },
        }

        def add_menus(items, parent_id=None, created_map=None):
            if created_map is None:
                created_map = {}
            for idx, (name, code, type_, path, icon, children) in enumerate(items):
                menu = Menu(
                    name=name, code=code, type=type_, path=path, icon=icon,
                    sort_order=idx + 1, status=1, parent_id=parent_id,
                )
                db.add(menu)
                db.flush()
                created_map[code] = menu
                if children:
                    add_menus(children, parent_id=menu.id, created_map=created_map)
            return created_map

        menus_map = add_menus(menus_data)
        all_menus = list(menus_map.values())

        # 为每个角色分配菜单
        for role_code, allowed_codes in role_menu_codes.items():
            if role_code not in roles:
                continue
            if allowed_codes is None:
                # 全部菜单
                for m in all_menus:
                    db.add(RoleMenu(role_id=roles[role_code].id, menu_id=m.id))
            else:
                for code, m in menus_map.items():
                    if code in allowed_codes:
                        db.add(RoleMenu(role_id=roles[role_code].id, menu_id=m.id))
        db.flush()
        print(f"  [新增] 共 {len(all_menus)} 项菜单, {len(roles)} 个角色")

        # ============================================================
        # 5. 院系、班级
        # ============================================================
        print("\n[5/7] 创建院系和班级...")
        depts_data = [
            ("计算机科学与技术学院", "CS", "培养计算机专业人才"),
            ("数学与统计学院", "MATH", "数学研究与统计学科建设"),
            ("外国语学院", "LANG", "英语及其他外国语教学"),
            ("经济管理学院", "ECON", "经济学与管理学教学"),
            ("艺术与设计学院", "ART", "艺术创作与设计教育"),
        ]
        depts = {}
        for name, code, desc in depts_data:
            d = Department(name=name, code=code, description=desc, status=1)
            db.add(d)
            db.flush()
            depts[code] = d
            print(f"  [新增] 院系: {name}")

        clazzes_data = [
            ("计算机2201班", "CS2201", "CS", "2022"),
            ("计算机2202班", "CS2202", "CS", "2022"),
            ("计算机2301班", "CS2301", "CS", "2023"),
            ("计算机2302班", "CS2302", "CS", "2023"),
            ("数学2201班", "MATH2201", "MATH", "2022"),
            ("数学2301班", "MATH2301", "MATH", "2023"),
            ("英语2201班", "LANG2201", "LANG", "2022"),
            ("英语2301班", "LANG2301", "LANG", "2023"),
            ("经济2301班", "ECON2301", "ECON", "2023"),
            ("管理2301班", "ECON2302", "ECON", "2023"),
            ("艺术设计2301班", "ART2301", "ART", "2023"),
            ("艺术设计2302班", "ART2302", "ART", "2023"),
        ]
        clazzes = {}
        for name, code, dcode, grade in clazzes_data:
            c = Clazz(name=name, code=code, department_id=depts[dcode].id,
                      grade=grade, status=1)
            db.add(c)
            db.flush()
            clazzes[code] = c
            print(f"  [新增] 班级: {name}")

        # ============================================================
        # 6. 教职工、学生
        # ============================================================
        print("\n[6/7] 创建教职工和学生...")
        teachers_info = [
            # (uname, name, gender, position, title, dept_code, entry_year, role_code)
            ("teacher01", "张伟", 1, "教师",   "教授",   "CS",   2008, "staff_teacher"),
            ("teacher02", "李娜", 2, "院系主任", "副教授", "CS",   2012, "staff_dean"),
            ("teacher03", "王强", 1, "教师",   "讲师",   "CS",   2015, "staff_teacher"),
            ("teacher04", "刘敏", 2, "辅导员", "讲师",   "CS",   2017, "staff_counselor"),
            ("teacher05", "陈静", 2, "院系主任", "副教授", "MATH", 2013, "staff_dean"),
            ("teacher06", "杨光", 1, "教师",   "讲师",   "MATH", 2010, "staff_teacher"),
            ("teacher07", "周丽", 2, "教务管理员", "讲师", "LANG", 2016, "staff_affairs"),
            ("teacher08", "吴磊", 1, "教师",   "助教",   "LANG", 2018, "staff_teacher"),
            ("teacher09", "赵敏", 2, "教师",   "讲师",   "ECON", 2014, "staff_teacher"),
            ("teacher10", "钱峰", 1, "辅导员", "讲师",   "ECON", 2011, "staff_counselor"),
            ("teacher11", "孙悦", 2, "教师",   "讲师",   "ART",  2009, "staff_teacher"),
            ("teacher12", "郑凯", 1, "教务管理员", "讲师", "ART",  2015, "staff_affairs"),
        ]
        teachers_map = {}
        for idx, (uname, name, gender, pos, title, dcode, entry, rcode) in enumerate(teachers_info):
            phone = f"1381000{idx + 1:04d}"
            id_card = f"110101198{idx:02d}01011234"[:18]
            u = User(
                username=uname,
                password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
                real_name=name,
                phone=phone,
                status=1,
                must_change_password=True,
            )
            db.add(u)
            db.flush()
            db.add(UserRole(user_id=u.id, role_id=roles[rcode].id))
            t = Teacher(
                user_id=u.id, employee_no=f"T2022{idx + 1:03d}",
                name=name, gender=gender, id_card=id_card,
                position=pos, title=title,
                department_id=depts[dcode].id,
                entry_date=date(entry, 9, 1), status=1,
            )
            db.add(t)
            db.flush()
            teachers_map[uname] = t
        print(f"  [新增] 教职工: {len(teachers_info)} 人")

        surnames = ["王", "李", "张", "刘", "陈", "杨", "赵", "周", "吴", "徐",
                    "孙", "胡", "朱", "高", "马", "郑", "何", "林", "黄"]
        given_names_m = ["伟", "强", "磊", "军", "勇", "杰", "涛", "鹏", "浩", "宇",
                         "轩", "然", "昊", "博", "凯", "毅", "泽", "天", "文"]
        given_names_f = ["芳", "娜", "敏", "静", "丽", "艳", "婷", "颖", "蕾", "娟",
                         "燕", "华", "芬", "欣", "怡", "琳", "琪", "晴", "妍"]
        clazz_codes_list = list(clazzes.keys())

        students_map = {}
        for idx in range(48):
            clazz_code = clazz_codes_list[idx % len(clazz_codes_list)]
            student_idx = idx + 1
            gender = 1 if idx % 3 != 0 else 2
            if gender == 1:
                name = surnames[idx % len(surnames)] + given_names_m[idx % len(given_names_m)]
            else:
                name = surnames[(idx + 2) % len(surnames)] + given_names_f[(idx * 2) % len(given_names_f)]
            username = f"student{student_idx:02d}"
            phone = f"139000{student_idx:05d}"
            id_card = f"320101199910{student_idx:04d}"[:18]
            if len(id_card) < 18:
                id_card = id_card.ljust(18, "0")
            student_no = f"S2023{student_idx:04d}"

            u = User(
                username=username,
                password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
                real_name=name,
                phone=phone,
                status=1,
                must_change_password=True,
            )
            db.add(u)
            db.flush()
            db.add(UserRole(user_id=u.id, role_id=roles["student"].id))
            s = Student(
                user_id=u.id, student_no=student_no, name=name, gender=gender,
                id_card=id_card, clazz_id=clazzes[clazz_code].id,
                enrollment_date=date(2023, 9, 1), status=1,
            )
            db.add(s)
            db.flush()
            students_map[username] = s
        print(f"  [新增] 学生: 48 人")

        # ============================================================
        # 7. 课程、考试、成绩、公告、邮件
        # ============================================================
        print("\n[7/7] 创建课程/考试/成绩/公告/邮件...")

        courses_info = [
            ("高等数学", "MATH101", 4, 64, 1, "MATH", "teacher05", "高等数学基础课程"),
            ("线性代数", "MATH102", 3, 48, 1, "MATH", "teacher06", "线性代数基础"),
            ("计算机程序设计", "CS101", 4, 64, 1, "CS", "teacher01", "程序设计入门"),
            ("数据结构", "CS201", 3, 48, 1, "CS", "teacher03", "数据结构与算法"),
            ("计算机网络", "CS301", 3, 48, 1, "CS", "teacher04", "网络基础"),
            ("数据库原理", "CS302", 3, 48, 1, "CS", "teacher02", "数据库系统"),
            ("数学分析", "MATH201", 4, 64, 1, "MATH", "teacher05", "实分析与复分析"),
            ("大学英语", "LANG101", 4, 64, 1, "LANG", "teacher07", "大学英语"),
            ("英语口语", "LANG201", 2, 32, 2, "LANG", "teacher08", "口语训练"),
            ("经济学原理", "ECON101", 3, 48, 1, "ECON", "teacher09", "经济学基础"),
            ("设计基础", "ART101", 3, 48, 1, "ART", "teacher11", "设计学基础"),
            ("视觉传达", "ART201", 3, 48, 2, "ART", "teacher12", "视觉传达设计"),
        ]
        course_map = {}
        for cname, ccode, credit, hours, ctype, dcode, tkey, desc in courses_info:
            course = Course(
                name=cname, code=ccode, credit=credit, hours=hours,
                course_type=ctype, department_id=depts[dcode].id,
                teacher_id=teachers_map[tkey].id,
                description=desc, status=1,
            )
            db.add(course)
            db.flush()
            course_map[ccode] = course
        print(f"  [新增] 课程: {len(course_map)} 门")

        # 考试与成绩
        random.seed(42)
        exam_count = 0
        for ccode, course in course_map.items():
            for i, clazz_code in enumerate(clazz_codes_list[:4]):
                exam = Exam(
                    name=f"{course.name} - 期末考试",
                    course_id=course.id,
                    exam_type=2,
                    exam_date=date(2024, 1, 15),
                    exam_time="09:00-11:00",
                    location=f"教学楼 {i + 1}01",
                    clazz_id=clazzes[clazz_code].id,
                    description=f"{course.name}期末考试",
                    status=1,
                )
                db.add(exam)
                db.flush()
                cls_students = [s for s in students_map.values() if s.clazz_id == clazzes[clazz_code].id]
                for stu in cls_students:
                    s_val = round(random.uniform(45, 98), 1)
                    grade = "A" if s_val >= 90 else ("B" if s_val >= 80 else ("C" if s_val >= 70 else ("D" if s_val >= 60 else "F")))
                    db.add(Score(
                        student_id=stu.id, exam_id=exam.id, course_id=course.id,
                        score=s_val, grade=grade,
                        scorer_id=course.teacher_id,
                    ))
                exam_count += 1
        db.flush()
        print(f"  [新增] 考试: {exam_count} 次, 成绩: {db.query(Score).count()} 条")

        # 公告
        announcements_data = [
            ("2024 春季学期开学通知", "各位同学，2024 春季学期将于 2 月 26 日正式开学，请按时返校。", 1, 1),
            ("期末考试安排公告", "本学期期末考试将于 1 月 15 日开始，请各位同学认真复习。", 1, 1),
            ("校园文化节活动通知", "校园文化节将于 3 月 15 日举办，欢迎各位同学积极参与。", 1, 1),
            ("图书馆延长开放时间通知", "为配合期末复习，图书馆开放时间延长至 22:00。", 1, 1),
            ("教学质量评估公告", "请各位同学完成本学期教学质量评估。", 1, 1),
        ]
        for title, content, atype, status in announcements_data:
            a = Announcement(
                title=title, content=content, type=atype,
                publisher_id=admin.id, status=status,
                published_at=datetime(2024, 1, 1),
            )
            db.add(a)
        db.flush()
        print(f"  [新增] 公告: {len(announcements_data)} 条")

        # 邮件
        emails_data = [
            (admin.id, "系统管理员", "admin@school.edu.cn",
             teachers_map["teacher01"].user_id, "课程安排通知", "老师您好，本学期课程安排已确定。"),
            (admin.id, "系统管理员", "admin@school.edu.cn",
             students_map["student01"].user_id, "欢迎来到学校", "欢迎您加入本学校，祝您学业顺利！"),
            (admin.id, "系统管理员", "admin@school.edu.cn",
             students_map["student10"].user_id, "选课提醒", "请在规定时间内完成课程选择。"),
            (admin.id, "系统管理员", "admin@school.edu.cn",
             teachers_map["teacher05"].user_id, "教学会议通知", "请参加本周四下午的教学工作会议。"),
            (admin.id, "系统管理员", "admin@school.edu.cn",
             students_map["student20"].user_id, "成绩提醒", "您的期末考试成绩已发布，请查看。"),
        ]
        for sender_id, sender_name, sender_email, recipient_id, subject, body in emails_data:
            msg = EmailMessage(
                sender_id=sender_id, sender_name=sender_name, sender_email=sender_email,
                recipient_email="internal@school.edu.cn",
                recipient_user_id=recipient_id,
                subject=subject, body=body,
                is_external=False, status="sent", is_read=False,
                is_deleted_by_sender=False, is_deleted_by_recipient=False,
                sent_at=datetime(2024, 1, 10),
            )
            db.add(msg)
        db.flush()
        print(f"  [新增] 邮件: {len(emails_data)} 封")

        # 提交
        db.commit()

        print("\n" + "=" * 60)
        print("  数据插入完成，各表统计：")
        print(f"    用户: {db.query(User).count()} 人")
        print(f"    角色: {db.query(Role).count()} 个")
        print(f"    菜单: {db.query(Menu).count()} 项")
        print(f"    院系: {db.query(Department).count()} 个")
        print(f"    班级: {db.query(Clazz).count()} 个")
        print(f"    教职工: {db.query(Teacher).count()} 人")
        print(f"    学生: {db.query(Student).count()} 人")
        print(f"    课程: {db.query(Course).count()} 门")
        print(f"    考试: {db.query(Exam).count()} 次")
        print(f"    成绩: {db.query(Score).count()} 条")
        print(f"    公告: {db.query(Announcement).count()} 条")
        print(f"    邮件: {db.query(EmailMessage).count()} 封")
        print(f"\n  登录账号:")
        print(f"    admin / {settings.DEFAULT_ADMIN_PASSWORD}")
        print(f"    teacher01-teacher12 / {settings.DEFAULT_USER_PASSWORD}")
        print(f"    student01-student48 / {settings.DEFAULT_USER_PASSWORD}")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n  [错误] 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
