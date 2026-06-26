# 请假模块开发日志

更新时间：2026-06-26 11:10:29

## 1. 模块目标

为学生和教职工增加请假功能：

- 学生、教职工可以提交请假申请。
- 一级审批即可，审批人同意后直接通过，驳回后直接结束。
- 学生请假可由班主任/辅导员、院系主任或 admin 审批。
- 教职工请假可由院系主任或 admin 审批。
- 审批人不能审批自己的请假。
- 模块要延续现有项目风格：FastAPI + SQLAlchemy model + Pydantic schema + service + API router + Vue 管理页 + 菜单权限。

## 2. 当前需求结论

### 2.1 申请人范围

请假申请人统一从 `user` 出发，兼容两类身份：

- 学生：`user -> student`
- 教职工：`user -> teacher`

请假表保留 `student_id`、`teacher_id`、`clazz_id`、`department_id` 的快照字段。

这样做的原因：

- 查询“我的请假”时用 `applicant_user_id` 最直接。
- 学生转班、教师调院系后，历史请假记录仍保留提交时的班级/院系。
- 审批范围过滤时不用反复跨多层关联。

### 2.2 审批模式

第一版只做一级审批：

```text
pending -> approved
pending -> rejected
pending -> cancelled
```

暂不支持：

- 多级审批。
- 通过后再撤销。
- 驳回后重新变更为通过。
- 审批流日志表。

后续如需审计轨迹，再新增 `leave_request_log`。

## 3. 推荐表结构

表名：`leave_request`

```text
id                    主键
applicant_user_id     申请人 user.id，必填
applicant_type        student / teacher，必填
student_id            学生ID，可空
teacher_id            教职工ID，可空
clazz_id              班级ID，可空，学生请假时保存
department_id         院系ID，可空，学生/教职工申请时保存

leave_type            请假类型
start_time            开始时间
end_time              结束时间
duration_hours        请假时长，单位小时
reason                请假原因，必填
destination           去向/地点，可空
contact_phone         请假期间联系电话，可空
emergency_contact     紧急联系人，可空
attachment_url        证明材料，可空
remark                备注，可空

status                pending / approved / rejected / cancelled
reviewer_id           审批人 user.id，可空
reviewer_role         counselor / department_admin / admin，可空
review_comment        审批意见，可空
reviewed_at           审批时间，可空

is_deleted            软删除标记
deleted_at            删除时间
created_at            创建时间
updated_at            更新时间
```

### 3.1 字段建议

`leave_type` 建议值：

```text
sick       病假
personal   事假
official   公假
funeral    丧假
marriage   婚假
maternity  产假
other      其他
```

`status` 建议值：

```text
pending    待审批
approved   已通过
rejected   已驳回
cancelled  已撤销
```

### 3.2 索引建议

建议增加索引：

```text
idx_leave_applicant_user_id
idx_leave_student_id
idx_leave_teacher_id
idx_leave_clazz_id
idx_leave_department_id
idx_leave_status
idx_leave_start_end
idx_leave_reviewer_id
```

## 4. 业务规则

### 4.1 提交请假

提交时后端负责判断申请人身份：

- 当前用户有关联 `student`：可按学生身份请假。
- 当前用户有关联 `teacher`：可按教职工身份请假。
- 如果一个账号同时有关联学生和教职工，第一版建议让前端传 `applicant_type`，否则后端优先使用学生或直接报错要求明确身份。

提交校验：

- `start_time < end_time`。
- `reason` 必填，建议最大长度 1000。
- `duration_hours` 后端根据时间自动计算，避免前端伪造。
- 同一申请人在 `pending` 或 `approved` 状态下，不允许时间段重叠。
- 已提交后状态默认为 `pending`。

### 4.2 撤销请假

申请人只能撤销自己的 `pending` 申请。

不允许撤销：

- `approved`
- `rejected`
- `cancelled`

### 4.3 审批请假

审批人只能处理 `pending` 状态。

通用规则：

- 审批人不能审批自己的申请。
- `approve` 需要 `leave:review:approve` 权限。
- `reject` 需要 `leave:review:reject` 权限。
- 驳回时建议要求填写 `review_comment`。

审批范围：

- `admin`：可审批全部。
- `department_admin`：可审批本院系学生和教职工。
- `counselor`：可审批自己负责班级的学生。
- `teacher`：默认不能审批，除非同时拥有 `counselor` 或 `department_admin` 角色。
- `student`：不能审批。

### 4.4 查询范围

我的请假：

- 所有申请人都只能查看自己的申请。

审批列表：

- `admin` 查看全部。
- `department_admin` 查看本院系待审批/已审批申请。
- `counselor` 查看自己负责班级学生的申请。

## 5. 权限设计

建议新增菜单和权限码：

```text
leave
leave:request
leave:request:list
leave:request:create
leave:request:cancel

leave:review
leave:review:list
leave:review:approve
leave:review:reject
```

角色分配：

```text
student:
  leave, leave:request, leave:request:list, leave:request:create, leave:request:cancel

teacher:
  leave, leave:request, leave:request:list, leave:request:create, leave:request:cancel

counselor:
  leave request 权限
  leave:review, leave:review:list, leave:review:approve, leave:review:reject

department_admin:
  leave request 权限
  leave:review, leave:review:list, leave:review:approve, leave:review:reject

academic_admin:
  第一版建议不给审批权限；如需要可给 leave:review:list 只读

admin:
  全部权限
```

## 6. 后端开发流程

按以下顺序开发，便于每一步单独验证。

### 6.1 数据模型

新增：

- `app/models/leave.py`

模型类：

- `LeaveRequest`

更新：

- `app/models/__init__.py` 导入 `LeaveRequest`

### 6.2 Alembic 迁移

新增迁移文件：

- `alembic/versions/<revision>_add_leave_request_table.py`

迁移内容：

- 创建 `leave_request` 表。
- 创建必要索引。
- 回滚时删除索引和表。

### 6.3 Schema

新增：

- `app/schemas/leave.py`

建议 schema：

- `LeaveRequestCreate`
- `LeaveRequestReview`
- `LeaveRequestCancel`
- `LeaveRequestQuery`
- `LeaveRequestOut`

### 6.4 Service

新增：

- `app/services/leave_service.py`

建议函数：

```text
create_leave_request(user, data, db)
list_my_leave_requests(user, query, db)
list_review_leave_requests(user, query, db)
get_leave_request(leave_id, user, db)
cancel_leave_request(leave_id, user, db)
approve_leave_request(leave_id, user, data, db)
reject_leave_request(leave_id, user, data, db)
```

service 层负责：

- 申请人身份识别。
- 快照 `clazz_id`、`department_id`。
- 时间合法性校验。
- 重叠请假校验。
- 审批范围校验。
- 状态流转校验。

### 6.5 API Router

新增：

- `app/api/v1/leave.py`

建议接口：

```text
POST   /leave/requests
GET    /leave/requests/my
GET    /leave/requests/review
GET    /leave/requests/{leave_id}
POST   /leave/requests/{leave_id}/cancel
POST   /leave/requests/{leave_id}/approve
POST   /leave/requests/{leave_id}/reject
```

更新：

- `app/api/v1/router.py` 注册 leave router。

权限依赖：

```text
POST create       leave:request:create
GET my            leave:request:list
POST cancel       leave:request:cancel
GET review        leave:review:list
POST approve      leave:review:approve
POST reject       leave:review:reject
```

### 6.6 初始化菜单权限

更新：

- `scripts/init_db.py`

新增菜单树：

```text
请假管理 leave
  我的请假 leave:request
    查看 leave:request:list
    提交 leave:request:create
    撤销 leave:request:cancel
  请假审批 leave:review
    查看 leave:review:list
    通过 leave:review:approve
    驳回 leave:review:reject
```

同步到各角色权限集合。

### 6.7 前端 API

新增：

- `frontend/src/api/leave.ts`

建议方法：

```text
createLeaveRequest
getMyLeaveRequests
getReviewLeaveRequests
getLeaveRequest
cancelLeaveRequest
approveLeaveRequest
rejectLeaveRequest
```

### 6.8 前端页面

新增页面：

- `frontend/src/views/leave/MyLeave.vue`
- `frontend/src/views/leave/LeaveReview.vue`

更新：

- `frontend/src/router/index.ts`

页面建议：

我的请假：

- 列表
- 新增请假弹窗
- 查看详情
- pending 状态撤销

请假审批：

- 待审批/已审批筛选
- 按申请人、类型、时间范围筛选
- 查看详情
- 通过/驳回

## 7. 和现有项目风格的对齐点

后端保持现有目录习惯：

```text
model -> schema -> service -> api/v1 router -> router.py 注册
```

返回格式继续使用：

- `success`
- `page_success`

分页继续使用：

- `PageParams`
- `paginate`

权限继续使用：

- `require_permission("xxx")`

软删除继续使用：

- `SoftDeleteMixin`

实体转字典可新增：

- `leave_request_to_dict`

位置：

- `app/utils/entity_mappers.py`

## 8. 开发检查清单

后端：

- [ ] 新增 `LeaveRequest` 模型。
- [ ] 新增 Alembic 迁移。
- [ ] 新增 leave schema。
- [ ] 新增 leave service。
- [ ] 新增 leave API router。
- [ ] 注册 router。
- [ ] 更新初始化菜单和角色权限。
- [ ] 增加实体 mapper。
- [ ] `python -m py_compile` 通过。

前端：

- [ ] 新增 `frontend/src/api/leave.ts`。
- [ ] 新增我的请假页面。
- [ ] 新增请假审批页面。
- [ ] 注册路由。
- [ ] 菜单权限可正常显示。
- [ ] `npm run build` 通过。

联调：

- [ ] 学生提交请假。
- [ ] 学生只能看自己的请假。
- [ ] 学生可以撤销 pending 请假。
- [ ] 辅导员只能审批本班学生请假。
- [ ] 院系主任只能审批本院系学生/教职工请假。
- [ ] admin 可以审批全部。
- [ ] 审批人不能审批自己的请假。
- [ ] 时间重叠请假被拦截。

## 9. 暂不开发但建议后续补充

后续可以增强：

- `leave_request_log` 审批/操作日志表。
- 请假附件上传接口和文件预览。
- 请假导出 Excel。
- 审批通知或站内信。
- 请假统计报表。
- 与课程/考试冲突提醒。
- 长假自动要求上传证明材料。

## 10. 当前状态

截至本日志创建时：

- 需求已讨论确定为一级审批。
- 建议支持学生和教职工都可请假。
- 表结构、权限、审批范围、开发流程已设计。
- 尚未开始实现代码。

下一步建议从 `6.1 数据模型` 开始。
## 11. 实现进度记录

更新时间：2026-06-26 11:25:00

已完成：

- 新增后端模型 `app/models/leave.py`。
- 新增迁移 `alembic/versions/b8c9d0e1f2a3_add_leave_request_table.py`。
- 新增 schema `app/schemas/leave.py`。
- 新增 service `app/services/leave_service.py`，包含提交、我的列表、审批列表、撤销、通过、驳回和审批范围控制。
- 新增 API router `app/api/v1/leave.py` 并注册到 `app/api/v1/router.py`。
- 新增 mapper `leave_request_to_dict`。
- 更新 `scripts/init_db.py`，增加请假菜单和角色权限分配。
- 新增前端 API `frontend/src/api/leave.ts`。
- 新增前端页面 `frontend/src/views/leave/MyLeave.vue` 和 `frontend/src/views/leave/LeaveReview.vue`。
- 更新前端路由 `frontend/src/router/index.ts`。

编码说明：

- 本文档已按 UTF-8 with BOM 写入，便于 Windows 工具正确识别中文。
- 如果 PowerShell 仍显示乱码，可先执行 `chcp 65001`，或使用 VS Code/记事本以 UTF-8 打开。
