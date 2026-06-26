# 学期、教室、课表模块开发日志

更新时间：2026-06-26

## 1. 模块目标

按照 `docs/module_development_roadmap.md` 的第一阶段规划，先完成教学基础闭环：

- 学期管理：维护学年学期、起止日期、教学周数、当前学期。
- 教室管理：维护教室、楼栋、校区、容量、类型、状态。
- 课表管理：维护学期内课程、班级、教师、教室、星期、周次、节次。
- 我的课表：学生查看自己班级课表，教师查看自己的授课课表。

## 2. 本阶段边界

第一版做：

- 学期 CRUD。
- 教室 CRUD。
- 课表 CRUD。
- 教师、班级、教室时间冲突校验。
- 角色菜单权限。
- 前端管理页和我的课表页。

第一版暂不做：

- 自动排课算法。
- 调课审批流程。
- Excel 导入导出。
- 教学日历事件页面。
- 考勤和请假自动联动。

## 3. 表结构

### 3.1 term

```text
id
name
academic_year
semester
start_date
end_date
week_count
is_current
status
remark
is_deleted
deleted_at
created_at
updated_at
```

约束：

```text
uq_term_year_semester: academic_year + semester
```

### 3.2 term_event

预留教学日历事件表，本阶段先建表，不做页面。

```text
id
term_id
event_type
title
start_date
end_date
is_teaching_day
description
is_deleted
deleted_at
created_at
updated_at
```

### 3.3 classroom

```text
id
name
building
room_no
campus
capacity
room_type
status
remark
is_deleted
deleted_at
created_at
updated_at
```

### 3.4 course_schedule

```text
id
term_id
course_id
clazz_id
teacher_id
classroom_id
weekday
start_section
end_section
start_week
end_week
week_type
schedule_type
status
remark
is_deleted
deleted_at
created_at
updated_at
```

## 4. 权限规划

兼容新旧角色编码：

| 业务角色 | 兼容编码 |
| --- | --- |
| 学生 | `student` |
| 任课教师 | `teacher`, `staff_teacher` |
| 辅导员 | `counselor`, `staff_counselor` |
| 院系主任 | `department_admin`, `staff_dean` |
| 教务管理员 | `academic_admin`, `staff_affairs` |
| 普通教职工 | `staff` |
| 超级管理员 | `admin` |

菜单权限：

```text
academic-calendar
academic-calendar:term
academic-calendar:term:list
academic-calendar:term:create
academic-calendar:term:update
academic-calendar:term:delete

schedule
schedule:classroom
schedule:classroom:list
schedule:classroom:create
schedule:classroom:update
schedule:classroom:delete
schedule:timetable
schedule:timetable:list
schedule:timetable:create
schedule:timetable:update
schedule:timetable:delete
schedule:my
schedule:my:list
```

权限分配：

- 学生：查看学期、我的课表。
- 任课教师：查看学期、我的课表。
- 辅导员：查看学期、我的课表、查看课表管理。
- 院系主任：查看学期、我的课表、管理课表。
- 教务管理员：管理学期、管理教室、管理课表、我的课表。
- admin：全部。

## 5. 冲突校验规则

新增或编辑课表时校验：

- `start_section <= end_section`
- `start_week <= end_week`
- `end_week <= term.week_count`
- `week_type` 只能是 `all/odd/even`
- `schedule_type` 只能是 `normal/makeup/temporary`
- 同一学期、星期、周次范围、节次范围：
  - 教师不能冲突。
  - 班级不能冲突。
  - 教室不能冲突。
- `all` 与任意单双周冲突。
- `odd` 只与 `all/odd` 冲突。
- `even` 只与 `all/even` 冲突。

## 6. 已新增文件

后端：

```text
app/models/schedule.py
app/schemas/schedule.py
app/services/schedule_service.py
app/api/v1/schedule.py
alembic/versions/c1d2e3f4a5b6_add_schedule_tables.py
scripts/sync_schedule_menu.py
```

已修改：

```text
app/models/__init__.py
app/models/course.py
app/models/clazz.py
app/models/teacher.py
app/api/v1/router.py
app/utils/entity_mappers.py
```

前端计划：

```text
frontend/src/api/schedule.ts
frontend/src/views/schedule/TermManage.vue
frontend/src/views/schedule/ClassroomManage.vue
frontend/src/views/schedule/TimetableManage.vue
frontend/src/views/schedule/MySchedule.vue
frontend/src/router/index.ts
```

## 7. 验证流程

开发完成后执行：

```powershell
alembic upgrade c1d2e3f4a5b6
python scripts\sync_schedule_menu.py
python -m compileall app\models\schedule.py app\schemas\schedule.py app\services\schedule_service.py app\api\v1\schedule.py scripts\sync_schedule_menu.py
cd frontend
npm run build
```

后端如已运行，需要重启：

```powershell
python main.py
```

## 8. 后续接续点

- 补教学日历事件页面。
- 课表支持按周视图展示。
- 课表支持复制上一学期。
- 课表稳定后开发考勤模块。
- 考勤稳定后做请假联动。

