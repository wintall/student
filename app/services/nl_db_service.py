"""
自然语言数据库操作业务服务层
提供完整的业务逻辑，包括限流、日志、错误处理等
"""
import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.nl_db_agent import run_agent, clear_conversation, get_conversation_history, save_conversation_history
from app.redis import redis_get, redis_set


# ============ 限流配置 ============

RATE_LIMIT = 30  # 每分钟最多30条消息


def check_rate_limit(user_id: int) -> bool:
    """检查限流"""
    try:
        rate_key = f"nl_db_rate:{user_id}"
        raw = redis_get(rate_key)
        count = int(raw) if raw and raw.isdigit() else 0
        if count >= RATE_LIMIT:
            return False
        redis_set(rate_key, str(count + 1), ex=60)
        return True
    except Exception:
        return True  # Redis不可用时不限制


def execute_create_student(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行创建学生操作"""
    from app.services.student_service import create_student
    from app.schemas.student import StudentCreate
    from app.services.clazz_service import get_clazz
    from app.models.student import Student
    from app.models.user import User
    
    try:
        student_no = params.get("student_no")
        id_card = params.get("id_card")
        
        existing_student = db.query(Student).filter(Student.id_card == id_card).first()
        if existing_student:
            return {
                "success": False,
                "message": f"创建学生失败：身份证号已被使用（姓名：{existing_student.name}，学号：{existing_student.student_no}）",
                "data": None
            }
        
        existing_by_student_no = db.query(Student).filter(Student.student_no == student_no).first()
        if existing_by_student_no:
            return {
                "success": False,
                "message": f"创建学生失败：学号 {student_no} 已被使用",
                "data": None
            }
        
        clazz_id = int(params.get("clazz_id"))
        
        try:
            clazz = get_clazz(clazz_id, db)
        except Exception:
            return {
                "success": False,
                "message": f"创建学生失败：班级ID {clazz_id} 不存在",
                "data": None
            }
        
        data = StudentCreate(
            user_id=0,
            student_no=student_no,
            name=params.get("name"),
            gender=int(params.get("gender")),
            id_card=id_card,
            clazz_id=clazz_id,
            enrollment_date=params.get("enrollment_date"),
            status=int(params.get("status", 1))
        )
        
        existing_user = db.query(User).filter(User.username == f"stu_{student_no}").first()
        if existing_user:
            return {
                "success": False,
                "message": f"创建学生失败：用户名 stu_{student_no} 已存在",
                "data": None
            }
        
        if not data.user_id:
            from app.services.user_service import create_user
            from app.schemas.user import UserCreate
            user_obj = create_user(UserCreate(
                username=f"stu_{student_no}",
                password="123456Ab",
                real_name=data.name,
                role_code="student"
            ), db)
            data.user_id = user_obj.id
        
        student = create_student(data, db)
        return {
            "success": True,
            "message": f"学生 {data.name} 创建成功",
            "data": {
                "id": student.id,
                "name": student.name,
                "student_no": student.student_no,
                "clazz_id": student.clazz_id,
                "status": student.status
            }
        }
    except ValueError as e:
        return {
            "success": False,
            "message": f"创建学生失败：参数格式错误 - {str(e)}",
            "data": None
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"创建学生失败: {str(e)}",
            "data": None
        }


def execute_query_student(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行查询学生操作"""
    from app.services.student_service import get_student, list_students
    from app.schemas.common import PageParams
    
    try:
        student_id = params.get("student_id")
        name = params.get("name")
        student_no = params.get("student_no")
        clazz_id = params.get("clazz_id")
        id_card = params.get("id_card")
        
        if student_id:
            student = get_student(int(student_id), db)
            return {
                "success": True,
                "message": "查询成功",
                "data": [{
                    "id": student.id,
                    "name": student.name,
                    "student_no": student.student_no,
                    "gender": student.gender,
                    "clazz_id": student.clazz_id,
                    "status": student.status
                }]
            }
        
        q = list_students(PageParams(page=1, size=20), db, clazz_id=clazz_id)
        
        if name:
            from app.models.student import Student
            q = q.filter(Student.name.contains(name))
        if student_no:
            from app.models.student import Student
            q = q.filter(Student.student_no.contains(student_no))
        if id_card:
            from app.models.student import Student
            q = q.filter(Student.id_card.contains(id_card))
        
        students = q.all()
        return {
            "success": True,
            "message": f"查询到 {len(students)} 条记录",
            "data": [{
                "id": s.id,
                "name": s.name,
                "student_no": s.student_no,
                "gender": s.gender,
                "clazz_id": s.clazz_id,
                "status": s.status
            } for s in students]
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"查询学生失败: {str(e)}",
            "data": None
        }


def execute_update_student(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行更新学生操作"""
    from app.services.student_service import update_student
    from app.schemas.student import StudentUpdate
    
    try:
        student_id = int(params.get("student_id"))
        data = StudentUpdate(
            name=params.get("name"),
            student_no=params.get("student_no"),
            gender=int(params.get("gender")) if params.get("gender") else None,
            id_card=params.get("id_card"),
            clazz_id=int(params.get("clazz_id")) if params.get("clazz_id") else None,
            enrollment_date=params.get("enrollment_date"),
            status=int(params.get("status")) if params.get("status") else None
        )
        
        student = update_student(student_id, data, db)
        return {
            "success": True,
            "message": f"学生 {student.name} 更新成功",
            "data": {"id": student.id, "name": student.name}
        }
    except Exception as e:
        return {"success": False, "message": f"更新学生失败: {str(e)}", "data": None}


def execute_delete_student(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行删除学生操作"""
    from app.services.student_service import delete_student, get_student
    
    try:
        student_id = int(params.get("student_id"))
        student = get_student(student_id, db)
        delete_student(student_id, db)
        return {
            "success": True,
            "message": f"学生 {student.name} 删除成功",
            "data": {"id": student_id}
        }
    except Exception as e:
        return {"success": False, "message": f"删除学生失败: {str(e)}", "data": None}


def execute_create_teacher(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行创建教师操作"""
    from app.services.teacher_service import create_teacher
    from app.schemas.teacher import TeacherCreate
    from app.models.teacher import Teacher
    from app.models.user import User
    
    try:
        employee_no = params.get("employee_no")
        id_card = params.get("id_card")
        
        existing_teacher = db.query(Teacher).filter(Teacher.id_card == id_card).first()
        if existing_teacher:
            return {
                "success": False,
                "message": f"创建教师失败：身份证号已被使用",
                "data": None
            }
        
        existing_by_no = db.query(Teacher).filter(Teacher.employee_no == employee_no).first()
        if existing_by_no:
            return {
                "success": False,
                "message": f"创建教师失败：工号 {employee_no} 已被使用",
                "data": None
            }
        
        data = TeacherCreate(
            user_id=0,
            employee_no=employee_no,
            name=params.get("name"),
            gender=int(params.get("gender")),
            id_card=id_card,
            position=params.get("position"),
            title=params.get("title"),
            department_id=int(params.get("department_id")) if params.get("department_id") else None,
            entry_date=params.get("entry_date"),
            status=int(params.get("status", 1))
        )
        
        existing_user = db.query(User).filter(User.username == f"tea_{employee_no}").first()
        if existing_user:
            return {
                "success": False,
                "message": f"创建教师失败：用户名 tea_{employee_no} 已存在",
                "data": None
            }
        
        if not data.user_id:
            from app.services.user_service import create_user
            from app.schemas.user import UserCreate
            user_obj = create_user(UserCreate(
                username=f"tea_{employee_no}",
                password="123456Ab",
                real_name=data.name,
                role_code="staff"
            ), db)
            data.user_id = user_obj.id
        
        teacher = create_teacher(data, db)
        return {
            "success": True,
            "message": f"教师 {data.name} 创建成功",
            "data": {"id": teacher.id, "name": teacher.name, "employee_no": teacher.employee_no}
        }
    except Exception as e:
        return {"success": False, "message": f"创建教师失败: {str(e)}", "data": None}


def execute_query_teacher(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行查询教师操作"""
    from app.services.teacher_service import get_teacher, list_teachers
    from app.schemas.common import PageParams
    
    try:
        teacher_id = params.get("teacher_id")
        name = params.get("name")
        employee_no = params.get("employee_no")
        department_id = params.get("department_id")
        
        if teacher_id:
            teacher = get_teacher(int(teacher_id), db)
            return {
                "success": True,
                "message": "查询成功",
                "data": [{
                    "id": teacher.id,
                    "name": teacher.name,
                    "employee_no": teacher.employee_no,
                    "position": teacher.position,
                    "title": teacher.title,
                    "department_id": teacher.department_id
                }]
            }
        
        q = list_teachers(PageParams(page=1, size=20), db, department_id=department_id)
        
        if name:
            from app.models.teacher import Teacher
            q = q.filter(Teacher.name.contains(name))
        if employee_no:
            from app.models.teacher import Teacher
            q = q.filter(Teacher.employee_no.contains(employee_no))
        
        teachers = q.all()
        return {
            "success": True,
            "message": f"查询到 {len(teachers)} 条记录",
            "data": [{
                "id": t.id,
                "name": t.name,
                "employee_no": t.employee_no,
                "position": t.position,
                "title": t.title,
                "department_id": t.department_id
            } for t in teachers]
        }
    except Exception as e:
        return {"success": False, "message": f"查询教师失败: {str(e)}", "data": None}


def execute_update_teacher(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行更新教师操作"""
    from app.services.teacher_service import update_teacher
    from app.schemas.teacher import TeacherUpdate
    
    try:
        teacher_id = int(params.get("teacher_id"))
        data = TeacherUpdate(
            name=params.get("name"),
            employee_no=params.get("employee_no"),
            gender=int(params.get("gender")) if params.get("gender") else None,
            id_card=params.get("id_card"),
            position=params.get("position"),
            title=params.get("title"),
            department_id=int(params.get("department_id")) if params.get("department_id") else None,
            entry_date=params.get("entry_date"),
            status=int(params.get("status")) if params.get("status") else None
        )
        
        teacher = update_teacher(teacher_id, data, db)
        return {
            "success": True,
            "message": f"教师 {teacher.name} 更新成功",
            "data": {"id": teacher.id, "name": teacher.name}
        }
    except Exception as e:
        return {"success": False, "message": f"更新教师失败: {str(e)}", "data": None}


def execute_delete_teacher(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行删除教师操作"""
    from app.services.teacher_service import delete_teacher, get_teacher
    
    try:
        teacher_id = int(params.get("teacher_id"))
        teacher = get_teacher(teacher_id, db)
        delete_teacher(teacher_id, db)
        return {
            "success": True,
            "message": f"教师 {teacher.name} 删除成功",
            "data": {"id": teacher_id}
        }
    except Exception as e:
        return {"success": False, "message": f"删除教师失败: {str(e)}", "data": None}


def execute_create_clazz(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行创建班级操作"""
    from app.services.clazz_service import create_clazz
    from app.schemas.clazz import ClazzCreate
    from app.models.clazz import Clazz
    
    try:
        code = params.get("code")
        
        existing_clazz = db.query(Clazz).filter(Clazz.code == code).first()
        if existing_clazz:
            return {
                "success": False,
                "message": f"创建班级失败：班级编号 {code} 已被使用",
                "data": None
            }
        
        data = ClazzCreate(
            name=params.get("name"),
            code=code,
            department_id=int(params.get("department_id")),
            grade=params.get("grade"),
            counselor_id=int(params.get("counselor_id")) if params.get("counselor_id") else None,
            status=int(params.get("status", 1))
        )
        
        clazz = create_clazz(data, db)
        return {
            "success": True,
            "message": f"班级 {data.name} 创建成功",
            "data": {"id": clazz.id, "name": clazz.name, "code": clazz.code}
        }
    except Exception as e:
        return {"success": False, "message": f"创建班级失败: {str(e)}", "data": None}


def execute_query_clazz(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行查询班级操作"""
    from app.services.clazz_service import get_clazz, list_clazzes
    from app.schemas.common import PageParams
    
    try:
        clazz_id = params.get("clazz_id")
        name = params.get("name")
        code = params.get("code")
        department_id = params.get("department_id")
        
        if clazz_id:
            clazz = get_clazz(int(clazz_id), db)
            return {
                "success": True,
                "message": "查询成功",
                "data": [{
                    "id": clazz.id,
                    "name": clazz.name,
                    "code": clazz.code,
                    "department_id": clazz.department_id,
                    "grade": clazz.grade,
                    "counselor_id": clazz.counselor_id
                }]
            }
        
        q = list_clazzes(PageParams(page=1, size=20), db, department_id=department_id)
        
        if name:
            from app.models.clazz import Clazz
            q = q.filter(Clazz.name.contains(name))
        if code:
            from app.models.clazz import Clazz
            q = q.filter(Clazz.code.contains(code))
        
        clazzes = q.all()
        return {
            "success": True,
            "message": f"查询到 {len(clazzes)} 条记录",
            "data": [{
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "department_id": c.department_id,
                "grade": c.grade,
                "counselor_id": c.counselor_id
            } for c in clazzes]
        }
    except Exception as e:
        return {"success": False, "message": f"查询班级失败: {str(e)}", "data": None}


def execute_update_clazz(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行更新班级操作"""
    from app.services.clazz_service import update_clazz
    from app.schemas.clazz import ClazzUpdate
    
    try:
        clazz_id = int(params.get("clazz_id"))
        data = ClazzUpdate(
            name=params.get("name"),
            code=params.get("code"),
            department_id=int(params.get("department_id")) if params.get("department_id") else None,
            grade=params.get("grade"),
            counselor_id=int(params.get("counselor_id")) if params.get("counselor_id") else None,
            status=int(params.get("status")) if params.get("status") else None
        )
        
        clazz = update_clazz(clazz_id, data, db)
        return {
            "success": True,
            "message": f"班级 {clazz.name} 更新成功",
            "data": {"id": clazz.id, "name": clazz.name}
        }
    except Exception as e:
        return {"success": False, "message": f"更新班级失败: {str(e)}", "data": None}


def execute_delete_clazz(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行删除班级操作"""
    from app.services.clazz_service import delete_clazz, get_clazz
    
    try:
        clazz_id = int(params.get("clazz_id"))
        clazz = get_clazz(clazz_id, db)
        delete_clazz(clazz_id, db)
        return {
            "success": True,
            "message": f"班级 {clazz.name} 删除成功",
            "data": {"id": clazz_id}
        }
    except Exception as e:
        return {"success": False, "message": f"删除班级失败: {str(e)}", "data": None}


def execute_create_course(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行创建课程操作"""
    from app.services.course_service import create_course
    from app.schemas.course import CourseCreate
    from app.models.course import Course
    
    try:
        code = params.get("code")
        
        existing_course = db.query(Course).filter(Course.code == code).first()
        if existing_course:
            return {
                "success": False,
                "message": f"创建课程失败：课程编号 {code} 已被使用",
                "data": None
            }
        
        data = CourseCreate(
            name=params.get("name"),
            code=code,
            department_id=int(params.get("department_id")),
            credit=float(params.get("credit")),
            teacher_id=int(params.get("teacher_id")) if params.get("teacher_id") else None,
            status=int(params.get("status", 1))
        )
        
        course = create_course(data, db)
        return {
            "success": True,
            "message": f"课程 {data.name} 创建成功",
            "data": {"id": course.id, "name": course.name, "code": course.code}
        }
    except Exception as e:
        return {"success": False, "message": f"创建课程失败: {str(e)}", "data": None}


def execute_query_course(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行查询课程操作"""
    from app.services.course_service import get_course, list_courses
    from app.schemas.common import PageParams
    
    try:
        course_id = params.get("course_id")
        name = params.get("name")
        code = params.get("code")
        department_id = params.get("department_id")
        
        if course_id:
            course = get_course(int(course_id), db)
            return {
                "success": True,
                "message": "查询成功",
                "data": [{
                    "id": course.id,
                    "name": course.name,
                    "code": course.code,
                    "department_id": course.department_id,
                    "credit": course.credit,
                    "teacher_id": course.teacher_id
                }]
            }
        
        q = list_courses(PageParams(page=1, size=20), db, department_id=department_id)
        
        if name:
            from app.models.course import Course
            q = q.filter(Course.name.contains(name))
        if code:
            from app.models.course import Course
            q = q.filter(Course.code.contains(code))
        
        courses = q.all()
        return {
            "success": True,
            "message": f"查询到 {len(courses)} 条记录",
            "data": [{
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "department_id": c.department_id,
                "credit": c.credit,
                "teacher_id": c.teacher_id
            } for c in courses]
        }
    except Exception as e:
        return {"success": False, "message": f"查询课程失败: {str(e)}", "data": None}


def execute_update_course(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行更新课程操作"""
    from app.services.course_service import update_course
    from app.schemas.course import CourseUpdate
    
    try:
        course_id = int(params.get("course_id"))
        data = CourseUpdate(
            name=params.get("name"),
            code=params.get("code"),
            department_id=int(params.get("department_id")) if params.get("department_id") else None,
            credit=float(params.get("credit")) if params.get("credit") else None,
            teacher_id=int(params.get("teacher_id")) if params.get("teacher_id") else None,
            status=int(params.get("status")) if params.get("status") else None
        )
        
        course = update_course(course_id, data, db)
        return {
            "success": True,
            "message": f"课程 {course.name} 更新成功",
            "data": {"id": course.id, "name": course.name}
        }
    except Exception as e:
        return {"success": False, "message": f"更新课程失败: {str(e)}", "data": None}


def execute_delete_course(params: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行删除课程操作"""
    from app.services.course_service import delete_course, get_course
    
    try:
        course_id = int(params.get("course_id"))
        course = get_course(course_id, db)
        delete_course(course_id, db)
        return {
            "success": True,
            "message": f"课程 {course.name} 删除成功",
            "data": {"id": course_id}
        }
    except Exception as e:
        return {"success": False, "message": f"删除课程失败: {str(e)}", "data": None}


def execute_tool_call(tool_name: str, tool_args: Dict[str, Any], user: User, db: Session) -> Dict[str, Any]:
    """执行工具调用"""
    tool_handlers = {
        "create_student": execute_create_student,
        "query_student": execute_query_student,
        "update_student": execute_update_student,
        "delete_student": execute_delete_student,
        "create_teacher": execute_create_teacher,
        "query_teacher": execute_query_teacher,
        "update_teacher": execute_update_teacher,
        "delete_teacher": execute_delete_teacher,
        "create_clazz": execute_create_clazz,
        "query_clazz": execute_query_clazz,
        "update_clazz": execute_update_clazz,
        "delete_clazz": execute_delete_clazz,
        "create_course": execute_create_course,
        "query_course": execute_query_course,
        "update_course": execute_update_course,
        "delete_course": execute_delete_course,
    }
    
    handler = tool_handlers.get(tool_name)
    if not handler:
        return {"success": False, "message": f"工具 {tool_name} 不存在", "data": None}
    
    return handler(tool_args, user, db)


def chat(user: User, message: str, db: Session) -> Dict[str, Any]:
    """
    自然语言数据库操作主入口
    """
    if not message or not message.strip():
        return {"success": True, "reply": "请问有什么可以帮你的？", "tool_calls": [], "tool_results": [], "has_data": False}
    
    # 限流检查
    if not check_rate_limit(user.id):
        return {"success": False, "reply": "你的消息太频繁啦，稍后再试吧～", "tool_calls": [], "tool_results": [], "has_data": False}
    
    # 执行Agent
    result = run_agent(user, message.strip(), db)
    
    if not result.get("success"):
        return result
    
    # 如果有工具调用，执行它们并获取结果
    tool_results = []
    if result.get("tool_calls") and result.get("has_data"):
        for tool_call in result["tool_calls"]:
            tool_name = tool_call.get("tool")
            tool_args = tool_call.get("args", {})
            
            tool_result = execute_tool_call(tool_name, tool_args, user, db)
            tool_results.append({
                "tool": tool_name,
                "args": tool_args,
                "result": tool_result
            })
        
        # 根据工具执行结果生成友好回复
        final_reply = ""
        for tr in tool_results:
            success = tr["result"].get("success", False)
            msg = tr["result"].get("message", "")
            data = tr["result"].get("data", None)
            
            if success:
                final_reply += "操作成功！\n"
                final_reply += f"{msg}\n"
                if data:
                    final_reply += "\n新增/修改的数据：\n"
                    final_reply += "| 字段 | 值 |\n"
                    final_reply += "|------|------|\n"
                    if isinstance(data, list):
                        for item in data:
                            for key, value in item.items():
                                final_reply += f"| {key} | {value} |\n"
                    else:
                        for key, value in data.items():
                            final_reply += f"| {key} | {value} |\n"
            else:
                final_reply += "操作失败！\n"
                final_reply += f"{msg}\n"
        
        # 保存工具执行结果到对话历史
        history = get_conversation_history(user.id)
        save_conversation_history(user.id, history + [{"role": "assistant", "content": final_reply}])
        
        return {
            "success": True,
            "reply": final_reply,
            "tool_calls": result["tool_calls"],
            "tool_results": tool_results,
            "has_data": True
        }
    
    return result


def get_history(user_id: int) -> Dict[str, Any]:
    """获取用户对话历史"""
    history = get_conversation_history(user_id)
    return {
        "success": True,
        "history": history,
        "count": len(history)
    }


def clear_history(user_id: int) -> Dict[str, Any]:
    """清除用户对话历史"""
    clear_conversation(user_id)
    return {"success": True, "message": "对话历史已清空"}
