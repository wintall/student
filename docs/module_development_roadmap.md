# 校园管理系统模块开发规划

更新时间：2026-06-26

## 1. 文档目标

本文件用于指导后续模块扩展，避免一次性堆功能导致表结构、权限、菜单、接口和前端入口混乱。

当前项目已有能力：

- 用户、角色、菜单权限。
- 院系、班级、学生、教职工。
- 课程、考试、成绩。
- 公告、邮件。
- 人脸识别、AI 问答、智能数据助手。
- 请假模块。

后续扩展应围绕两个方向：

- 教务闭环：学期、教室、课表、考勤、请假联动、成绩分析。
- 校园服务：收费奖助、图书馆、待办中心、审计日志。

不建议在同一阶段同时开发过多模块。每个阶段都要做到：表结构稳定、权限明确、菜单可见、接口可测、前端可用。

## 2. 总体开发原则

### 2.1 先做主链路，再做增强

推荐顺序：

1. 学期与教学日历。
2. 教室与课表。
3. 考勤。
4. 请假与考勤联动。
5. 首页待办与统计。
6. 学生缴费与奖助学金。
7. 图书馆。
8. 教师薪酬轻量记录。

原因：

- 学期是时间主线。
- 课表是课程、教师、班级、教室的连接点。
- 考勤依赖课表。
- 请假联动依赖课表和考勤。
- 财务、图书馆属于扩展模块，不应影响教务核心稳定性。

### 2.2 每个模块按固定流程开发

每个模块都按以下步骤推进：

1. 需求边界确认。
2. 角色权限确认。
3. 表结构设计。
4. Alembic 迁移。
5. SQLAlchemy model。
6. Pydantic schema。
7. service 业务逻辑。
8. API router。
9. 菜单和按钮权限同步脚本。
10. 前端 API 文件。
11. 前端页面。
12. 数据初始化或演示数据。
13. 后端接口验证。
14. 前端构建验证。
15. 开发日志更新。

### 2.3 角色编码统一策略

当前项目存在两套角色编码：

旧角色：

```text
staff_teacher      任课教师
staff_dean         院系主任
staff_counselor    辅导员
staff_affairs      教务管理员
```

新角色：

```text
teacher            任课教师
department_admin   院系主任/院系管理员
counselor          辅导员
academic_admin     教务管理员
```

后续建议：

- 业务代码中兼容两套编码。
- 初始化脚本中逐步向新角色靠拢。
- 菜单权限同步脚本必须同时分配旧角色和新角色。
- 文档里写权限时统一写成“业务角色”，再列出兼容编码。

角色兼容表：

| 业务角色 | 兼容编码 |
| --- | --- |
| 超级管理员 | `admin` |
| 学生 | `student` |
| 任课教师 | `teacher`, `staff_teacher` |
| 辅导员 | `counselor`, `staff_counselor` |
| 院系主任 | `department_admin`, `staff_dean` |
| 教务管理员 | `academic_admin`, `staff_affairs` |
| 普通教职工 | `staff` |
| 图书管理员 | `library_admin`，后续新增 |
| 财务管理员 | `finance_admin`，后续新增 |

## 3. 第一阶段：学期与教学日历

### 3.1 模块价值

学期是后续课表、考试、成绩、考勤、缴费的共同时间维度。如果没有学期，很多数据只能靠日期散落查询，后期统计会很难。

### 3.2 建议菜单

```text
academic-calendar              教学日历
academic-calendar:term         学期管理
academic-calendar:event        日历事件
```

### 3.3 表结构设计

表名：`term`

```text
id                 主键
name               学期名称，如 2025-2026 学年第一学期
academic_year      学年，如 2025-2026
semester           学期序号，1/2/3
start_date         开始日期
end_date           结束日期
week_count         教学周数
is_current         是否当前学期
status             1 启用，0 停用
remark             备注
created_at
updated_at
```

建议约束：

```text
唯一约束：academic_year + semester
同一时间只允许一个 is_current = true
```

表名：`term_event`

```text
id                 主键
term_id            学期ID
event_type         holiday/exam/weekend_adjust/notice/other
title              事件标题
start_date         开始日期
end_date           结束日期
is_teaching_day    是否教学日
description        描述
created_at
updated_at
```

### 3.4 权限建议

| 功能 | 学生 | 任课教师 | 辅导员 | 院系主任 | 教务管理员 | admin |
| --- | --- | --- | --- | --- | --- | --- |
| 查看学期 | 是 | 是 | 是 | 是 | 是 | 是 |
| 管理学期 | 否 | 否 | 否 | 否 | 是 | 是 |
| 查看日历 | 是 | 是 | 是 | 是 | 是 | 是 |
| 管理日历事件 | 否 | 否 | 否 | 否 | 是 | 是 |

### 3.5 第一版边界

第一版只做学期和日历事件维护，不做复杂调休算法。

## 4. 第二阶段：教室与课表

### 4.1 模块价值

课表是课程、教师、班级、教室、学期的核心连接点。考勤、请假联动、教师课时统计都要依赖它。

### 4.2 建议菜单

```text
schedule                         排课管理
schedule:classroom               教室管理
schedule:timetable               课表管理
schedule:my                      我的课表
```

### 4.3 表结构设计

表名：`classroom`

```text
id                 主键
name               教室名称，如 逸夫楼 A101
building           楼栋
room_no            房间号
campus             校区
capacity           容量
room_type          normal/lab/computer/multimedia/other
status             1 可用，0 停用，2 维修
remark
created_at
updated_at
```

表名：`course_schedule`

```text
id                 主键
term_id            学期ID
course_id          课程ID
clazz_id           班级ID
teacher_id         授课教师ID
classroom_id       教室ID，可空
weekday            星期，1-7
start_section      开始节次
end_section        结束节次
start_week         开始周
end_week           结束周
week_type          all/odd/even
schedule_type      normal/makeup/temporary
status             1 正常，0 停用
remark
created_at
updated_at
```

建议索引：

```text
idx_schedule_term
idx_schedule_course
idx_schedule_clazz
idx_schedule_teacher
idx_schedule_classroom
idx_schedule_time(term_id, weekday, start_section, end_section, start_week, end_week)
```

### 4.4 冲突规则

新增或编辑课表时必须校验：

- 同一学期、同一星期、同一周次范围、同一节次范围，教师不能冲突。
- 同一学期、同一星期、同一周次范围、同一节次范围，班级不能冲突。
- 同一学期、同一星期、同一周次范围、同一节次范围，教室不能冲突。
- `start_section <= end_section`。
- `start_week <= end_week`。
- 教室容量小于班级人数时给出警告，第一版可不强拦截。

### 4.5 权限建议

| 功能 | 学生 | 任课教师 | 辅导员 | 院系主任 | 教务管理员 | admin |
| --- | --- | --- | --- | --- | --- | --- |
| 查看自己课表 | 是 | 是 | 是 | 是 | 是 | 是 |
| 查看班级课表 | 否 | 可看授课班级 | 是 | 本院系 | 是 | 是 |
| 管理教室 | 否 | 否 | 否 | 否 | 是 | 是 |
| 排课 | 否 | 否 | 否 | 本院系建议可编辑 | 是 | 是 |
| 删除课表 | 否 | 否 | 否 | 谨慎开放 | 是 | 是 |

### 4.6 第一版边界

第一版建议做：

- 教室 CRUD。
- 课表 CRUD。
- 我的课表。
- 冲突校验。

第一版不建议做：

- 自动排课算法。
- 复杂调课流程。
- 批量 Excel 导入导出。

## 5. 第三阶段：考勤

### 5.1 模块价值

考勤是课表的自然延伸，也能和请假模块形成闭环。

### 5.2 建议菜单

```text
attendance                         考勤管理
attendance:session                 考勤任务
attendance:record                  考勤记录
attendance:statistics              考勤统计
```

### 5.3 表结构设计

表名：`attendance_session`

```text
id                 主键
term_id            学期ID
schedule_id        课表ID
course_id          课程ID，冗余快照
clazz_id           班级ID，冗余快照
teacher_id         教师ID，冗余快照
attendance_date    考勤日期
weekday            星期
start_section      开始节次
end_section        结束节次
status             pending/open/closed/cancelled
opened_at          开始点名时间
closed_at          结束点名时间
created_by         创建人 user.id
remark
created_at
updated_at
```

表名：`attendance_record`

```text
id                 主键
session_id         考勤任务ID
student_id         学生ID
user_id            学生 user.id
status             present/late/early_leave/absent/leave
leave_request_id   关联请假ID，可空
checkin_time       签到时间，可空
source             manual/leave/face/import
remark
created_at
updated_at
```

建议约束：

```text
唯一约束：session_id + student_id
```

### 5.4 考勤状态建议

```text
present       正常
late          迟到
early_leave   早退
absent        缺勤
leave         请假
```

### 5.5 权限建议

| 功能 | 学生 | 任课教师 | 辅导员 | 院系主任 | 教务管理员 | admin |
| --- | --- | --- | --- | --- | --- | --- |
| 查看本人考勤 | 是 | 不适用 | 不适用 | 不适用 | 是 | 是 |
| 创建考勤任务 | 否 | 授课课程 | 否 | 否 | 是 | 是 |
| 录入考勤 | 否 | 授课课程 | 可辅助本班 | 本院系查看 | 是 | 是 |
| 修改考勤 | 否 | 授课课程未关闭 | 可辅助本班 | 谨慎开放 | 是 | 是 |
| 查看统计 | 本人 | 授课课程 | 所管班级 | 本院系 | 是 | 是 |

### 5.6 与请假联动

建议分两步实现：

第一步：考勤独立可用。

第二步：请假通过后联动。

联动规则：

- 请假状态为 `approved`。
- 请假时间覆盖某个考勤任务的上课时间。
- 申请人为该考勤任务班级学生。
- 自动把考勤记录标记为 `leave`，并写入 `leave_request_id`。
- 如果教师已经手工标记为 `present`，第一版建议不自动覆盖，只提示存在冲突。

## 6. 第四阶段：首页待办与统计

### 6.1 模块价值

首页不是单纯展示数字，而应该告诉用户“现在该处理什么”。

### 6.2 建议功能

学生：

- 今日课表。
- 我的待审批请假。
- 我的考勤异常。
- 未读公告。
- 未读邮件。
- 最近成绩。

任课教师：

- 今日授课。
- 待点名课程。
- 待录入成绩。
- 未读公告。

辅导员：

- 待审批请假。
- 班级考勤异常。
- 学生请假趋势。

院系主任：

- 本院系待审批请假。
- 本院系课程/考勤概览。
- 本院系成绩概览。

admin/教务：

- 全局待办。
- 数据概览。
- 最近操作日志。

### 6.3 是否需要新表

第一版不建议建 `todo` 表。待办可以从业务表实时聚合：

- 请假：`leave_request.status = pending`
- 邮件：未读邮件
- 公告：未读公告
- 考勤：未关闭考勤任务或异常记录
- 成绩：未录入成绩

如果后续要做“可指派、可延期、可关闭”的通用待办，再新增 `todo_item`。

## 7. 第五阶段：学生缴费与奖助学金

### 7.1 模块定位

不建议一开始叫“完整财务模块”。更合理的名称是“收费与奖助”。

教师工资暂不优先开发。学生缴费、奖学金、助学金更贴合学生管理系统。

### 7.2 建议菜单

```text
finance                         收费与奖助
finance:fee-item                收费项目
finance:student-bill            学生账单
finance:payment                 缴费记录
finance:scholarship             奖助项目
finance:scholarship-apply       奖助申请
finance:scholarship-review      奖助审核
```

### 7.3 表结构设计

表名：`fee_item`

```text
id                 主键
name               收费项目名称
code               项目编码
fee_type           tuition/accommodation/book/insurance/other
amount             默认金额
term_id            学期ID，可空
status             1 启用，0 停用
remark
created_at
updated_at
```

表名：`student_bill`

```text
id                 主键
student_id         学生ID
user_id            学生 user.id
term_id            学期ID
fee_item_id        收费项目ID
amount_due         应缴金额
amount_paid        已缴金额
amount_discount    减免金额
status             unpaid/partial/paid/refunded/cancelled
due_date           截止日期
remark
created_at
updated_at
```

表名：`payment_record`

```text
id                 主键
bill_id            账单ID
student_id         学生ID
amount             缴费金额
pay_method         cash/card/wechat/alipay/bank/other
pay_time           缴费时间
transaction_no     交易号
operator_id        经办人 user.id
receipt_no         票据号
remark
created_at
updated_at
```

表名：`scholarship_project`

```text
id                 主键
name               奖助项目名称
project_type       scholarship/grant/subsidy/other
term_id            学期ID
amount             金额
quota              名额，可空
apply_start        申请开始时间
apply_end          申请结束时间
status             draft/open/closed
description
created_at
updated_at
```

表名：`scholarship_application`

```text
id                 主键
project_id         奖助项目ID
student_id         学生ID
user_id            学生 user.id
reason             申请理由
attachment_url     附件
status             pending/approved/rejected/cancelled/paid
reviewer_id        审核人 user.id
review_comment     审核意见
reviewed_at        审核时间
paid_at            发放时间
remark
created_at
updated_at
```

### 7.4 权限建议

| 功能 | 学生 | 辅导员 | 院系主任 | 财务管理员 | admin |
| --- | --- | --- | --- | --- | --- |
| 查看本人账单 | 是 | 否 | 否 | 是 | 是 |
| 管理收费项目 | 否 | 否 | 否 | 是 | 是 |
| 生成学生账单 | 否 | 否 | 可建议不开放 | 是 | 是 |
| 录入缴费 | 否 | 否 | 否 | 是 | 是 |
| 申请奖助 | 是 | 否 | 否 | 否 | 是 |
| 奖助初审 | 否 | 是 | 否 | 否 | 是 |
| 奖助终审 | 否 | 否 | 是 | 否 | 是 |
| 发放记录 | 否 | 否 | 否 | 是 | 是 |

### 7.5 第一版边界

第一版建议：

- 收费项目维护。
- 学生账单生成。
- 缴费记录。
- 奖助项目。
- 奖助申请和一级审核。

第一版不建议：

- 自动对接微信/支付宝真实支付。
- 真实发票。
- 个税、工资、复杂财务凭证。

## 8. 第六阶段：图书馆

### 8.1 模块定位

图书馆是合理的校园服务扩展，但不是教务核心模块。建议轻量开发，不做完整图书馆系统。

### 8.2 建议菜单

```text
library                         图书馆
library:book                    图书档案
library:borrow                  借阅管理
library:reservation             预约管理
library:rule                    借阅规则
library:my                      我的借阅
```

### 8.3 表结构设计

表名：`library_book`

```text
id                 主键
isbn               ISBN
title              书名
author             作者
publisher          出版社
publish_date       出版日期
category           分类
location           馆藏位置
total_count        馆藏总数
available_count    可借数量
status             available/disabled/lost
description
created_at
updated_at
```

表名：`library_borrow`

```text
id                 主键
book_id            图书ID
borrower_user_id   借阅人 user.id
borrower_type      student/teacher/staff
borrowed_at        借出时间
due_at             应还时间
returned_at        归还时间
renew_count        续借次数
status             borrowed/returned/overdue/lost
operator_id        经办人 user.id
remark
created_at
updated_at
```

表名：`library_reservation`

```text
id                 主键
book_id            图书ID
user_id            预约人 user.id
status             pending/notified/cancelled/expired/fulfilled
reserved_at        预约时间
notified_at        通知时间
expired_at         过期时间
remark
created_at
updated_at
```

表名：`library_rule`

```text
id                 主键
role_code          角色编码，如 student/staff_teacher
max_borrow_count   最大借阅数量
borrow_days        借阅天数
max_renew_count    最大续借次数
renew_days         每次续借天数
status             1 启用，0 停用
created_at
updated_at
```

### 8.4 权限建议

| 功能 | 学生 | 教职工 | 图书管理员 | admin |
| --- | --- | --- | --- | --- |
| 查书 | 是 | 是 | 是 | 是 |
| 查看本人借阅 | 是 | 是 | 是 | 是 |
| 预约图书 | 是 | 是 | 是 | 是 |
| 图书入库 | 否 | 否 | 是 | 是 |
| 办理借还 | 否 | 否 | 是 | 是 |
| 处理逾期 | 否 | 否 | 是 | 是 |
| 管理规则 | 否 | 否 | 是 | 是 |

### 8.5 第一版边界

第一版建议：

- 图书档案。
- 借书、还书、续借。
- 我的借阅。
- 简单逾期状态。

第一版不建议：

- 条码枪集成。
- 复杂罚金结算。
- 馆际互借。

## 9. 教师薪酬模块建议

### 9.1 是否开发

不建议优先开发教师工资。原因：

- 真实工资涉及岗位工资、绩效、课时费、社保、公积金、个税、补贴、扣款。
- 如果做得太简单，显得不真实。
- 如果做得真实，工作量会大幅超过学生管理系统边界。

### 9.2 如果必须开发

建议命名为“薪酬记录”，而不是完整工资系统。

表名：`teacher_salary_record`

```text
id                 主键
teacher_id         教师ID
user_id            教师 user.id
year_month         工资月份，如 2026-06
base_salary        基本工资
performance_pay    绩效
class_hour_pay     课时费
allowance          补贴
deduction          扣款
gross_amount       应发金额
tax_amount         税费
net_amount         实发金额
status             draft/confirmed/paid
paid_at            发放时间
operator_id        经办人 user.id
remark
created_at
updated_at
```

权限建议：

- 教师只能查看自己的薪酬记录。
- 财务管理员可维护。
- admin 全部权限。

第一版不建议做薪酬计算公式，只做记录和查询。

## 10. 操作日志与审计

### 10.1 模块价值

系统已有 `operation_log` 表，建议后续补前端页面。这个模块对管理系统很重要，也适合答辩展示。

### 10.2 建议菜单

```text
system:operation-log              操作日志
```

### 10.3 功能建议

- 按操作人查询。
- 按模块查询。
- 按操作类型查询。
- 按时间范围查询。
- 查看请求 IP、操作内容、结果。

### 10.4 权限建议

- admin 可查看全部。
- 其他角色默认不可见。

## 11. 菜单权限落库规范

每个模块都应该有目录、页面菜单、按钮权限三级结构。

示例：

```text
schedule                         目录：排课管理
schedule:classroom               页面：教室管理
schedule:classroom:list          按钮/接口：查看
schedule:classroom:create        按钮/接口：新增
schedule:classroom:update        按钮/接口：编辑
schedule:classroom:delete        按钮/接口：删除
schedule:timetable               页面：课表管理
schedule:timetable:list
schedule:timetable:create
schedule:timetable:update
schedule:timetable:delete
schedule:my                      页面：我的课表
schedule:my:list
```

开发时必须同步：

- `scripts/init_db.py`
- 单独的轻量同步脚本，如 `scripts/sync_schedule_menu.py`
- 路由依赖 `require_permission(...)`
- 前端菜单路径和路由路径一致

## 12. API 设计规范

建议保持现有风格：

```text
GET    /api/v1/terms
POST   /api/v1/terms
GET    /api/v1/terms/{id}
PUT    /api/v1/terms/{id}
DELETE /api/v1/terms/{id}
```

分页参数统一：

```text
page
page_size
keyword
```

返回结构继续使用现有：

```text
success(...)
page_success(...)
```

业务逻辑放 service，不要写在 router 里。

## 13. 前端页面规范

后台管理类页面建议统一：

- 顶部搜索区。
- 表格区。
- 分页。
- 新增/编辑弹窗。
- 删除确认。
- 状态标签。
- 操作按钮受权限控制。

课表和考勤可以额外做日历/周视图，但第一版不要过度复杂。

## 14. 风险清单

### 14.1 角色不统一

风险：菜单权限写给新角色，但数据库里用户还是旧角色。

处理：

- 所有新模块同步脚本兼容旧/新角色。
- 业务判断也兼容旧/新角色。

### 14.2 表结构过早复杂化

风险：一开始设计过多状态和流程，导致开发缓慢。

处理：

- 第一版只做核心字段。
- 审批流、日志流、自动化流后续补。

### 14.3 模块联动过早

风险：课表、考勤、请假、财务互相依赖，调试困难。

处理：

- 先让每个模块独立可用。
- 再做联动。

### 14.4 财务边界失控

风险：从学生缴费扩展到完整财务系统，工作量失控。

处理：

- 第一版只做收费与奖助。
- 不接真实支付。
- 不做工资自动计算。

### 14.5 图书馆范围过大

风险：做成完整图书馆系统后偏离主线。

处理：

- 第一版只做书目、借还、我的借阅。
- 预约、罚金、条码集成后续再做。

## 15. 推荐里程碑

### Milestone 1：教学基础闭环

包含：

- 学期。
- 教室。
- 课表。

验收标准：

- admin/教务可以维护学期、教室、课表。
- 学生可以查看自己班级课表。
- 任课教师可以查看自己的授课课表。
- 排课时能校验教师、班级、教室冲突。

### Milestone 2：考勤闭环

包含：

- 考勤任务。
- 考勤记录。
- 考勤统计。

验收标准：

- 教师可基于课表创建/打开/关闭考勤。
- 教师可登记学生考勤状态。
- 学生可查看本人考勤。
- 辅导员可查看所管班级考勤异常。

### Milestone 3：请假联动

包含：

- 请假审批通过后影响考勤。
- 考勤记录可追溯到请假申请。

验收标准：

- 学生请假通过后，对应课程考勤显示请假。
- 手工考勤和请假联动冲突有明确提示。

### Milestone 4：运营增强

包含：

- 首页待办。
- 成绩分析。
- 操作日志页面。

验收标准：

- 不同角色首页看到不同待办。
- 管理员能查看系统关键操作日志。

### Milestone 5：校园服务扩展

包含：

- 收费与奖助。
- 图书馆。
- 薪酬记录可选。

验收标准：

- 学生能查看账单、申请奖助、查看借阅。
- 财务/图书管理员能处理对应业务。
- 模块之间不影响教务主流程。

## 16. 资深建议

### 16.1 不要追求“大而全”，要追求“闭环”

一个完整可用的课表 + 考勤 + 请假联动，比五个只能增删改查的模块更有价值。

### 16.2 每次只开发一个业务闭环

推荐节奏：

```text
设计 -> 建表 -> 后端 -> 权限 -> 前端 -> 验证 -> 文档
```

完成一个闭环后再进入下一个模块。

### 16.3 模块边界要清楚

收费与奖助是学生管理系统的合理延伸。

教师工资、真实支付、复杂图书馆属于更大的校务系统，应该后置。

### 16.4 每个模块都要有演示数据

没有演示数据，功能很难验证。建议每个模块都准备：

- 1 个 admin 场景。
- 1 个学生场景。
- 1 个教师场景。
- 1 个辅导员/院系主任场景。

### 16.5 权限要先设计再开发

不要页面写完再补权限。这个项目已经证明：菜单、接口、角色编码只要有一个不同步，用户就看不到功能。

### 16.6 财务和图书馆要轻量

财务第一版做收费与奖助。

图书馆第一版做图书、借还、我的借阅。

不要一开始做真实支付、工资公式、罚金结算、条码设备。

### 16.7 文档必须随开发更新

建议每个模块单独维护开发日志：

```text
docs/term_schedule_module_dev_log.md
docs/attendance_module_dev_log.md
docs/finance_aid_module_dev_log.md
docs/library_module_dev_log.md
```

每个日志记录：

- 需求结论。
- 表结构。
- 权限矩阵。
- 已完成文件。
- 验证命令。
- 遗留问题。

