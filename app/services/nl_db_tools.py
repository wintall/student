"""
自然语言数据库操作工具模块
将现有CRUD服务包装为LangChain工具，支持自然语言操作
"""
from typing import Optional, Dict, Any, List, Callable
from sqlalchemy.orm import Session
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.models.student import Student
from app.models.teacher import Teacher
from app.models.clazz import Clazz
from app.models.course import Course
from app.models.department import Department
from app.models.score import Score
from app.models.exam import Exam
from app.models.user import User
from app.schemas.student import StudentCreate, StudentUpdate
from app.schemas.teacher import TeacherCreate, TeacherUpdate
from app.schemas.clazz import ClazzCreate, ClazzUpdate
from app.schemas.course import CourseCreate, CourseUpdate
from app.services import student_service, teacher_service, clazz_service, course_service
from app.database import engine


PERMISSIONS = {
    "student:query": "查询学生",
    "student:create": "新增学生",
    "student:update": "修改学生",
    "student:delete": "删除学生",
    "teacher:query": "查询教师",
    "teacher:create": "新增教师",
    "teacher:update": "修改教师",
    "teacher:delete": "删除教师",
    "clazz:query": "查询班级",
    "clazz:create": "新增班级",
    "clazz:update": "修改班级",
    "clazz:delete": "删除班级",
    "course:query": "查询课程",
    "course:create": "新增课程",
    "course:update": "修改课程",
    "course:delete": "删除课程",
}

ROLE_PERMISSIONS = {
    "admin": [
        "student:query", "student:create", "student:update", "student:delete",
        "teacher:query", "teacher:create", "teacher:update", "teacher:delete",
        "clazz:query", "clazz:create", "clazz:update", "clazz:delete",
        "course:query", "course:create", "course:update", "course:delete",
    ],
    "staff_teacher": [
        "student:query",
        "teacher:query",
        "clazz:query",
        "course:query",
    ],
    "staff_dean": [
        "student:query", "student:create", "student:update", "student:delete",
        "teacher:query", "teacher:create", "teacher:update", "teacher:delete",
        "clazz:query", "clazz:create", "clazz:update", "clazz:delete",
        "course:query", "course:create", "course:update", "course:delete",
    ],
    "staff_counselor": [
        "student:query", "student:create", "student:update", "student:delete",
        "teacher:query",
        "clazz:query",
        "course:query",
    ],
    "staff_affairs": [
        "student:query", "student:create", "student:update", "student:delete",
        "teacher:query", "teacher:create", "teacher:update", "teacher:delete",
        "clazz:query", "clazz:create", "clazz:update", "clazz:delete",
        "course:query", "course:create", "course:update", "course:delete",
    ],
    "student": [
        "teacher:query",
        "clazz:query",
        "course:query",
    ],
}


def get_user_roles(user: User, db: Session) -> List[str]:
    """获取用户角色列表"""
    from app.models.user import UserRole, Role
    role_ids = [ur.role_id for ur in db.query(UserRole).filter(UserRole.user_id == user.id).all()]
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all() if role_ids else []
    return [r.code for r in roles]


def check_permission(user: User, db: Session, perm_code: str) -> bool:
    """检查用户是否拥有指定权限"""
    roles = get_user_roles(user, db)
    
    if "admin" in roles:
        return True
    
    for role in roles:
        if role in ROLE_PERMISSIONS and perm_code in ROLE_PERMISSIONS[role]:
            return True
    
    return False


def get_user_permission_list(user: User, db: Session) -> List[str]:
    """获取用户的所有权限列表"""
    roles = get_user_roles(user, db)
    
    if "admin" in roles:
        return list(PERMISSIONS.keys())
    
    perms = set()
    for role in roles:
        if role in ROLE_PERMISSIONS:
            perms.update(ROLE_PERMISSIONS[role])
    
    return list(perms)


def get_database_schema(db: Session) -> Dict[str, Any]:
    tables_info = {}
    table_classes = [Student, Teacher, Clazz, Course, Department, Score, Exam]
    
    for table_cls in table_classes:
        table_name = table_cls.__tablename__
        columns = []
        
        for col in table_cls.__mapper__.columns:
            col_info = {
                "name": col.name,
                "type": str(col.type),
                "nullable": col.nullable,
                "primary_key": col.primary_key,
                "comment": col.comment if hasattr(col, 'comment') else None
            }
            columns.append(col_info)
        
        tables_info[table_name] = {
            "description": table_cls.__doc__ or "",
            "columns": columns
        }
    
    return {
        "database": "student",
        "tables": tables_info,
        "description": "学生信息管理系统数据库，包含学生、教师、班级、课程、院系、成绩、考试等表"
    }


class GetSchemaToolArgs(BaseModel):
    pass


class CreateStudentToolArgs(BaseModel):
    name: str = Field(..., description="学生姓名（必填）")
    student_no: str = Field(..., description="学号（必填，唯一）")
    gender: int = Field(..., description="性别（必填，1=男，2=女）")
    id_card: str = Field(..., description="身份证号（必填，唯一）")
    clazz_id: int = Field(..., description="所属班级ID（必填）")
    user_id: Optional[int] = Field(default=None, description="关联用户ID（可选）")
    enrollment_date: Optional[str] = Field(default=None, description="入学日期（格式：YYYY-MM-DD）")
    status: int = Field(default=1, description="状态（1=在读，2=休学，3=毕业，0=退学）")


class UpdateStudentToolArgs(BaseModel):
    student_id: int = Field(..., description="学生ID（必填）")
    name: Optional[str] = Field(default=None, description="姓名")
    student_no: Optional[str] = Field(default=None, description="学号")
    gender: Optional[int] = Field(default=None, description="性别（1=男，2=女）")
    id_card: Optional[str] = Field(default=None, description="身份证号")
    clazz_id: Optional[int] = Field(default=None, description="班级ID")
    enrollment_date: Optional[str] = Field(default=None, description="入学日期")
    status: Optional[int] = Field(default=None, description="状态")


class DeleteStudentToolArgs(BaseModel):
    student_id: int = Field(..., description="学生ID（必填）")


class QueryStudentToolArgs(BaseModel):
    student_id: Optional[int] = Field(default=None, description="学生ID（精确匹配）")
    name: Optional[str] = Field(default=None, description="姓名（模糊匹配）")
    student_no: Optional[str] = Field(default=None, description="学号（模糊匹配）")
    clazz_id: Optional[int] = Field(default=None, description="班级ID（精确匹配）")


class CreateTeacherToolArgs(BaseModel):
    name: str = Field(..., description="姓名（必填）")
    employee_no: str = Field(..., description="工号（必填，唯一）")
    gender: int = Field(..., description="性别（必填，1=男，2=女）")
    id_card: str = Field(..., description="身份证号（必填，唯一）")
    position: str = Field(..., description="岗位（必填）")
    user_id: Optional[int] = Field(default=None, description="关联用户ID（可选）")
    title: Optional[str] = Field(default=None, description="职称")
    department_id: Optional[int] = Field(default=None, description="所属院系ID")
    entry_date: Optional[str] = Field(default=None, description="入职日期")
    status: int = Field(default=1, description="状态")


class UpdateTeacherToolArgs(BaseModel):
    teacher_id: int = Field(..., description="教职工ID（必填）")
    name: Optional[str] = Field(default=None, description="姓名")
    employee_no: Optional[str] = Field(default=None, description="工号")
    gender: Optional[int] = Field(default=None, description="性别")
    id_card: Optional[str] = Field(default=None, description="身份证号")
    position: Optional[str] = Field(default=None, description="岗位")
    title: Optional[str] = Field(default=None, description="职称")
    department_id: Optional[int] = Field(default=None, description="院系ID")
    entry_date: Optional[str] = Field(default=None, description="入职日期")
    status: Optional[int] = Field(default=None, description="状态")


class DeleteTeacherToolArgs(BaseModel):
    teacher_id: int = Field(..., description="教职工ID（必填）")


class QueryTeacherToolArgs(BaseModel):
    teacher_id: Optional[int] = Field(default=None, description="教职工ID")
    name: Optional[str] = Field(default=None, description="姓名（模糊匹配）")
    employee_no: Optional[str] = Field(default=None, description="工号（模糊匹配）")
    department_id: Optional[int] = Field(default=None, description="院系ID")


class CreateClazzToolArgs(BaseModel):
    name: str = Field(..., description="班级名称（必填）")
    code: str = Field(..., description="班级代码（必填，唯一）")
    department_id: int = Field(..., description="所属院系ID（必填）")
    grade: str = Field(..., description="年级（必填）")
    counselor_id: Optional[int] = Field(default=None, description="辅导员ID")
    status: int = Field(default=1, description="状态")


class UpdateClazzToolArgs(BaseModel):
    clazz_id: int = Field(..., description="班级ID（必填）")
    name: Optional[str] = Field(default=None, description="班级名称")
    code: Optional[str] = Field(default=None, description="班级代码")
    department_id: Optional[int] = Field(default=None, description="院系ID")
    grade: Optional[str] = Field(default=None, description="年级")
    counselor_id: Optional[int] = Field(default=None, description="辅导员ID")
    status: Optional[int] = Field(default=None, description="状态")


class DeleteClazzToolArgs(BaseModel):
    clazz_id: int = Field(..., description="班级ID（必填）")


class QueryClazzToolArgs(BaseModel):
    clazz_id: Optional[int] = Field(default=None, description="班级ID")
    name: Optional[str] = Field(default=None, description="班级名称（模糊匹配）")
    code: Optional[str] = Field(default=None, description="班级代码（模糊匹配）")
    department_id: Optional[int] = Field(default=None, description="院系ID")


class CreateCourseToolArgs(BaseModel):
    name: str = Field(..., description="课程名称（必填）")
    code: str = Field(..., description="课程代码（必填，唯一）")
    department_id: int = Field(..., description="所属院系ID（必填）")
    credit: float = Field(..., description="学分（必填）")
    teacher_id: Optional[int] = Field(default=None, description="授课教师ID")
    status: int = Field(default=1, description="状态")


class UpdateCourseToolArgs(BaseModel):
    course_id: int = Field(..., description="课程ID（必填）")
    name: Optional[str] = Field(default=None, description="课程名称")
    code: Optional[str] = Field(default=None, description="课程代码")
    department_id: Optional[int] = Field(default=None, description="院系ID")
    credit: Optional[float] = Field(default=None, description="学分")
    teacher_id: Optional[int] = Field(default=None, description="教师ID")
    status: Optional[int] = Field(default=None, description="状态")


class DeleteCourseToolArgs(BaseModel):
    course_id: int = Field(..., description="课程ID（必填）")


class QueryCourseToolArgs(BaseModel):
    course_id: Optional[int] = Field(default=None, description="课程ID")
    name: Optional[str] = Field(default=None, description="课程名称（模糊匹配）")
    code: Optional[str] = Field(default=None, description="课程代码（模糊匹配）")
    department_id: Optional[int] = Field(default=None, description="院系ID")


def create_student_func(db: Session, user: User):
    def func(
        name: str,
        student_no: str,
        gender: int,
        id_card: str,
        clazz_id: int,
        user_id: Optional[int] = None,
        enrollment_date: Optional[str] = None,
        status: int = 1,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "student:create"):
                return {
                    "success": False,
                    "message": "您没有权限创建学生",
                    "data": None
                }
            
            data = StudentCreate(
                user_id=user_id or 0,
                student_no=student_no,
                name=name,
                gender=gender,
                id_card=id_card,
                clazz_id=clazz_id,
                enrollment_date=enrollment_date,
                status=status
            )
            
            if not user_id:
                from app.services.user_service import create_user
                from app.schemas.user import UserCreate
                user_obj = create_user(UserCreate(
                    username=f"stu_{student_no}",
                    password="123456Ab",
                    real_name=name,
                    role_code="student"
                ), db)
                data.user_id = user_obj.id
            
            student = student_service.create_student(data, db)
            return {
                "success": True,
                "message": f"学生 {name} 创建成功",
                "data": {
                    "id": student.id,
                    "name": student.name,
                    "student_no": student.student_no,
                    "clazz_id": student.clazz_id,
                    "status": student.status
                }
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"创建学生失败: {str(e)}",
                "data": None
            }
    return func


def update_student_func(db: Session, user: User):
    def func(
        student_id: int,
        name: Optional[str] = None,
        student_no: Optional[str] = None,
        gender: Optional[int] = None,
        id_card: Optional[str] = None,
        clazz_id: Optional[int] = None,
        enrollment_date: Optional[str] = None,
        status: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "student:update"):
                return {
                    "success": False,
                    "message": "您没有权限修改学生",
                    "data": None
                }
            
            data = StudentUpdate(
                name=name,
                student_no=student_no,
                gender=gender,
                id_card=id_card,
                clazz_id=clazz_id,
                enrollment_date=enrollment_date,
                status=status
            )
            
            student = student_service.update_student(student_id, data, db)
            return {
                "success": True,
                "message": f"学生 {student.name} 更新成功",
                "data": {"id": student.id, "name": student.name}
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"更新学生失败: {str(e)}",
                "data": None
            }
    return func


def delete_student_func(db: Session, user: User):
    def func(student_id: int) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "student:delete"):
                return {
                    "success": False,
                    "message": "您没有权限删除学生",
                    "data": None
                }
            
            student = student_service.get_student(student_id, db)
            student_service.delete_student(student_id, db)
            return {
                "success": True,
                "message": f"学生 {student.name} 删除成功",
                "data": {"id": student_id}
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"删除学生失败: {str(e)}",
                "data": None
            }
    return func


def query_student_func(db: Session, user: User):
    def func(
        student_id: Optional[int] = None,
        name: Optional[str] = None,
        student_no: Optional[str] = None,
        clazz_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "student:query"):
                return {
                    "success": False,
                    "message": "您没有权限查询学生",
                    "data": None
                }
            
            if student_id:
                student = student_service.get_student(student_id, db)
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
            
            from app.schemas.common import PageParams
            q = student_service.list_students(PageParams(page=1, size=20), db, clazz_id=clazz_id)
            
            if name:
                q = q.filter(Student.name.contains(name))
            if student_no:
                q = q.filter(Student.student_no.contains(student_no))
            
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
    return func


def create_teacher_func(db: Session, user: User):
    def func(
        name: str,
        employee_no: str,
        gender: int,
        id_card: str,
        position: str,
        user_id: Optional[int] = None,
        title: Optional[str] = None,
        department_id: Optional[int] = None,
        entry_date: Optional[str] = None,
        status: int = 1,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "teacher:create"):
                return {
                    "success": False,
                    "message": "您没有权限创建教职工",
                    "data": None
                }
            
            data = TeacherCreate(
                user_id=user_id or 0,
                employee_no=employee_no,
                name=name,
                gender=gender,
                id_card=id_card,
                position=position,
                title=title,
                department_id=department_id,
                entry_date=entry_date,
                status=status
            )
            
            if not user_id:
                from app.services.user_service import create_user
                from app.schemas.user import UserCreate
                user_obj = create_user(UserCreate(
                    username=f"tea_{employee_no}",
                    password="123456Ab",
                    real_name=name,
                    role_code="staff"
                ), db)
                data.user_id = user_obj.id
            
            teacher = teacher_service.create_teacher(data, db)
            return {
                "success": True,
                "message": f"教职工 {name} 创建成功",
                "data": {"id": teacher.id, "name": teacher.name, "employee_no": teacher.employee_no}
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"创建教职工失败: {str(e)}",
                "data": None
            }
    return func


def update_teacher_func(db: Session, user: User):
    def func(
        teacher_id: int,
        name: Optional[str] = None,
        employee_no: Optional[str] = None,
        gender: Optional[int] = None,
        id_card: Optional[str] = None,
        position: Optional[str] = None,
        title: Optional[str] = None,
        department_id: Optional[int] = None,
        entry_date: Optional[str] = None,
        status: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "teacher:update"):
                return {
                    "success": False,
                    "message": "您没有权限修改教职工",
                    "data": None
                }
            
            data = TeacherUpdate(
                name=name,
                employee_no=employee_no,
                gender=gender,
                id_card=id_card,
                position=position,
                title=title,
                department_id=department_id,
                entry_date=entry_date,
                status=status
            )
            
            teacher = teacher_service.update_teacher(teacher_id, data, db)
            return {
                "success": True,
                "message": f"教职工 {teacher.name} 更新成功",
                "data": {"id": teacher.id, "name": teacher.name}
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"更新教职工失败: {str(e)}",
                "data": None
            }
    return func


def delete_teacher_func(db: Session, user: User):
    def func(teacher_id: int) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "teacher:delete"):
                return {
                    "success": False,
                    "message": "您没有权限删除教职工",
                    "data": None
                }
            
            teacher = teacher_service.get_teacher(teacher_id, db)
            teacher_service.delete_teacher(teacher_id, db)
            return {
                "success": True,
                "message": f"教职工 {teacher.name} 删除成功",
                "data": {"id": teacher_id}
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"删除教职工失败: {str(e)}",
                "data": None
            }
    return func


def query_teacher_func(db: Session, user: User):
    def func(
        teacher_id: Optional[int] = None,
        name: Optional[str] = None,
        employee_no: Optional[str] = None,
        department_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "teacher:query"):
                return {
                    "success": False,
                    "message": "您没有权限查询教职工",
                    "data": None
                }
            
            if teacher_id:
                teacher = teacher_service.get_teacher(teacher_id, db)
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
            
            from app.schemas.common import PageParams
            q = teacher_service.list_teachers(PageParams(page=1, size=20), db, department_id=department_id)
            
            if name:
                q = q.filter(Teacher.name.contains(name))
            if employee_no:
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
            return {
                "success": False,
                "message": f"查询教职工失败: {str(e)}",
                "data": None
            }
    return func


def create_clazz_func(db: Session, user: User):
    def func(
        name: str,
        code: str,
        department_id: int,
        grade: str,
        counselor_id: Optional[int] = None,
        status: int = 1,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "clazz:create"):
                return {
                    "success": False,
                    "message": "您没有权限创建班级",
                    "data": None
                }
            
            data = ClazzCreate(
                name=name,
                code=code,
                department_id=department_id,
                grade=grade,
                counselor_id=counselor_id,
                status=status
            )
            
            clazz = clazz_service.create_clazz(data, db)
            return {
                "success": True,
                "message": f"班级 {name} 创建成功",
                "data": {"id": clazz.id, "name": clazz.name, "code": clazz.code}
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"创建班级失败: {str(e)}",
                "data": None
            }
    return func


def update_clazz_func(db: Session, user: User):
    def func(
        clazz_id: int,
        name: Optional[str] = None,
        code: Optional[str] = None,
        department_id: Optional[int] = None,
        grade: Optional[str] = None,
        counselor_id: Optional[int] = None,
        status: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "clazz:update"):
                return {
                    "success": False,
                    "message": "您没有权限修改班级",
                    "data": None
                }
            
            data = ClazzUpdate(
                name=name,
                code=code,
                department_id=department_id,
                grade=grade,
                counselor_id=counselor_id,
                status=status
            )
            
            clazz = clazz_service.update_clazz(clazz_id, data, db)
            return {
                "success": True,
                "message": f"班级 {clazz.name} 更新成功",
                "data": {"id": clazz.id, "name": clazz.name}
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"更新班级失败: {str(e)}",
                "data": None
            }
    return func


def delete_clazz_func(db: Session, user: User):
    def func(clazz_id: int) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "clazz:delete"):
                return {
                    "success": False,
                    "message": "您没有权限删除班级",
                    "data": None
                }
            
            clazz = clazz_service.get_clazz(clazz_id, db)
            clazz_service.delete_clazz(clazz_id, db)
            return {
                "success": True,
                "message": f"班级 {clazz.name} 删除成功",
                "data": {"id": clazz_id}
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"删除班级失败: {str(e)}",
                "data": None
            }
    return func


def query_clazz_func(db: Session, user: User):
    def func(
        clazz_id: Optional[int] = None,
        name: Optional[str] = None,
        code: Optional[str] = None,
        department_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "clazz:query"):
                return {
                    "success": False,
                    "message": "您没有权限查询班级",
                    "data": None
                }
            
            if clazz_id:
                clazz = clazz_service.get_clazz(clazz_id, db)
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
            
            from app.schemas.common import PageParams
            q = clazz_service.list_clazzes(PageParams(page=1, size=20), db, department_id=department_id)
            
            if name:
                q = q.filter(Clazz.name.contains(name))
            if code:
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
            return {
                "success": False,
                "message": f"查询班级失败: {str(e)}",
                "data": None
            }
    return func


def create_course_func(db: Session, user: User):
    def func(
        name: str,
        code: str,
        department_id: int,
        credit: float,
        teacher_id: Optional[int] = None,
        status: int = 1,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "course:create"):
                return {
                    "success": False,
                    "message": "您没有权限创建课程",
                    "data": None
                }
            
            data = CourseCreate(
                name=name,
                code=code,
                department_id=department_id,
                credit=credit,
                teacher_id=teacher_id,
                status=status
            )
            
            course = course_service.create_course(data, db)
            return {
                "success": True,
                "message": f"课程 {name} 创建成功",
                "data": {"id": course.id, "name": course.name, "code": course.code}
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"创建课程失败: {str(e)}",
                "data": None
            }
    return func


def update_course_func(db: Session, user: User):
    def func(
        course_id: int,
        name: Optional[str] = None,
        code: Optional[str] = None,
        department_id: Optional[int] = None,
        credit: Optional[float] = None,
        teacher_id: Optional[int] = None,
        status: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "course:update"):
                return {
                    "success": False,
                    "message": "您没有权限修改课程",
                    "data": None
                }
            
            data = CourseUpdate(
                name=name,
                code=code,
                department_id=department_id,
                credit=credit,
                teacher_id=teacher_id,
                status=status
            )
            
            course = course_service.update_course(course_id, data, db)
            return {
                "success": True,
                "message": f"课程 {course.name} 更新成功",
                "data": {"id": course.id, "name": course.name}
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"更新课程失败: {str(e)}",
                "data": None
            }
    return func


def delete_course_func(db: Session, user: User):
    def func(course_id: int) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "course:delete"):
                return {
                    "success": False,
                    "message": "您没有权限删除课程",
                    "data": None
                }
            
            course = course_service.get_course(course_id, db)
            course_service.delete_course(course_id, db)
            return {
                "success": True,
                "message": f"课程 {course.name} 删除成功",
                "data": {"id": course_id}
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"删除课程失败: {str(e)}",
                "data": None
            }
    return func


def query_course_func(db: Session, user: User):
    def func(
        course_id: Optional[int] = None,
        name: Optional[str] = None,
        code: Optional[str] = None,
        department_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            if not check_permission(user, db, "course:query"):
                return {
                    "success": False,
                    "message": "您没有权限查询课程",
                    "data": None
                }
            
            if course_id:
                course = course_service.get_course(course_id, db)
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
            
            from app.schemas.common import PageParams
            q = course_service.list_courses(PageParams(page=1, size=20), db, department_id=department_id)
            
            if name:
                q = q.filter(Course.name.contains(name))
            if code:
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
            return {
                "success": False,
                "message": f"查询课程失败: {str(e)}",
                "data": None
            }
    return func


def get_tools_for_user(user: User, db: Session) -> List[StructuredTool]:
    """根据用户权限获取可用工具列表"""
    user_perms = get_user_permission_list(user, db)
    
    tools = []
    
    tools.append(StructuredTool(
        name="get_database_schema",
        func=lambda: get_database_schema(db),
        args_schema=GetSchemaToolArgs,
        description="获取数据库表结构信息，包括所有表的字段、类型、约束等。"
    ))
    
    perm_mapping = {
        "create_student": ("student:create", create_student_func, CreateStudentToolArgs, "创建新的学生记录。需要提供姓名、学号、性别、身份证号、班级ID等必填参数。"),
        "update_student": ("student:update", update_student_func, UpdateStudentToolArgs, "更新已有学生记录。需要提供学生ID，其他参数可选。"),
        "delete_student": ("student:delete", delete_student_func, DeleteStudentToolArgs, "删除学生记录（软删除）。需要提供学生ID。"),
        "query_student": ("student:query", query_student_func, QueryStudentToolArgs, "查询学生记录。可以按ID精确查询，或按姓名、学号模糊查询。"),
        "create_teacher": ("teacher:create", create_teacher_func, CreateTeacherToolArgs, "创建新的教职工记录。需要提供姓名、工号、性别、身份证号、岗位等必填参数。"),
        "update_teacher": ("teacher:update", update_teacher_func, UpdateTeacherToolArgs, "更新已有教职工记录。需要提供教职工ID，其他参数可选。"),
        "delete_teacher": ("teacher:delete", delete_teacher_func, DeleteTeacherToolArgs, "删除教职工记录（软删除）。需要提供教职工ID。"),
        "query_teacher": ("teacher:query", query_teacher_func, QueryTeacherToolArgs, "查询教职工记录。可以按ID精确查询，或按姓名、工号模糊查询。"),
        "create_clazz": ("clazz:create", create_clazz_func, CreateClazzToolArgs, "创建新的班级记录。需要提供班级名称、代码、院系ID、年级等必填参数。"),
        "update_clazz": ("clazz:update", update_clazz_func, UpdateClazzToolArgs, "更新已有班级记录。需要提供班级ID，其他参数可选。"),
        "delete_clazz": ("clazz:delete", delete_clazz_func, DeleteClazzToolArgs, "删除班级记录（软删除）。需要提供班级ID。"),
        "query_clazz": ("clazz:query", query_clazz_func, QueryClazzToolArgs, "查询班级记录。可以按ID精确查询，或按名称、代码模糊查询。"),
        "create_course": ("course:create", create_course_func, CreateCourseToolArgs, "创建新的课程记录。需要提供课程名称、代码、院系ID、学分等必填参数。"),
        "update_course": ("course:update", update_course_func, UpdateCourseToolArgs, "更新已有课程记录。需要提供课程ID，其他参数可选。"),
        "delete_course": ("course:delete", delete_course_func, DeleteCourseToolArgs, "删除课程记录（软删除）。需要提供课程ID。"),
        "query_course": ("course:query", query_course_func, QueryCourseToolArgs, "查询课程记录。可以按ID精确查询，或按名称、代码模糊查询。"),
    }
    
    for tool_name, (perm_code, func_factory, args_schema, description) in perm_mapping.items():
        if perm_code in user_perms:
            tools.append(StructuredTool(
                name=tool_name,
                func=func_factory(db, user),
                args_schema=args_schema,
                description=description
            ))
    
    return tools