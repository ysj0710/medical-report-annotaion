# 医疗影像报告标注系统（轻量版）需求文档 PRD v0.2

> 目标：以最小功能闭环实现“管理端导入与分发 → 医生端错误项标注 →（可选）复核 → 导出”，不做影像阅片与复杂组织体系。

## 1. 背景与目标

### 1.1 背景
医疗影像报告在质控/教学/科研等场景中常需要人工检查并标注报告中的错误项。为提升分发效率与标注可追踪性，需要一套轻量化系统支撑导入、分发、标注与导出。

### 1.2 建设目标（MVP）
- 管理端/医生端分离，权限隔离清晰。
- 管理端支持本地导入报告文件（Excel/CSV，中文表头）。
- 管理端将报告分发给**唯一指定医生**（单报告单医生）。
- 医生端在“我的报告”列表中对分发报告进行**错误项标注**：草稿/提交。
- 导出标注结果（CSV/JSON）。
- （可选）复核流程：复核通过/驳回（驳回返工）。

### 1.3 非目标（明确不做）
- DICOM/影像在线阅片、测量工具。
- 科室/职称/多租户组织体系。
- AI 自动标注/辅助诊断。
- 复杂权限模型（仅角色级 RBAC）。

## 2. 角色与权限

### 2.1 角色
- **管理员（Admin）**：导入报告、管理报告池、分发、查看进度与结果、导出；管理医生账号。
- **医生（Doctor）**：查看分配给自己的报告、错误项标注（草稿/提交）。
- **复核人（Reviewer，可选）**：对已提交标注进行通过/驳回。

### 2.2 权限规则（MVP）
- 医生仅可访问分发给自己的报告与自己的标注记录。
- 管理员可访问所有报告、分发信息、标注结果；对医生提交后的标注默认只读。
- 复核人仅可访问分配给自己复核的记录（如启用复核）。

## 3. 核心业务流程

### 3.1 管理端导入
1. 管理员上传 Excel/CSV 文件创建导入任务。
2. 系统异步解析文件并入库报告记录。
3. 导入完成：展示成功/失败/警告统计；失败行提供下载明细。

### 3.2 管理端分发
1. 管理员在报告池选择报告（单条或批量）。
2. 选择目标医生（每条报告只能选择 1 名医生）。
3. 确认分发，生成分发信息，报告进入“待标注”。

### 3.3 医生端标注
1. 医生进入“我的报告”列表（待标注/标注中/已提交/被驳回）。
2. 打开报告详情页，查看报告全文并添加错误项。
3. 可保存草稿（多次）。
4. 提交完成后进入“已提交/待复核（若启用）”。

### 3.4 复核流程（可选）
- 医生提交 → 进入待复核。
- 复核人：
  - 通过：标注完成，报告状态变为已完成。
  - 驳回：需填写原因，报告状态变为已驳回，医生可修改并重新提交。

## 4. 功能需求（模块）

## 4.1 账号与登录（MVP）
- 登录：`username + password`。
- 角色：`admin / doctor / reviewer(可选)`。
- 管理员可创建/禁用账号、重置密码。

## 4.2 管理端（Admin）

### 4.2.1 报告导入（核心，异步）
- 支持文件：`.xlsx`、`.csv`。
- 支持中文表头（见 6.1 表头映射）。
- 必填列：**报告全文**。
- 单次量级：几千条（需异步任务）。
- 导入结果：
  - 成功条数、失败条数、警告条数。
  - 失败明细：写入文件并提供下载。
  - 重复 external_id：允许导入，仅产生 warning（不合并、不更新）。

### 4.2.2 报告池列表
- 筛选：状态、关键词（external_id/报告全文关键字）、导入时间范围。
- 列表字段建议：内部ID、external_id、状态、分发医生、分发时间、提交时间、导入时间。
- 操作：查看详情、分发（单条/批量）。

### 4.2.3 分发（核心）

#### 页面：创建任务-分派任务（参考UI：管理员分发报告页）

> 说明：你提供的 UI 以“任务向导（1创建任务→2标注样本→3分派任务）”的形式组织。
> 为保持系统轻量，本 PRD 允许两种落地方式：
> - **方式A（推荐轻量）**：直接在“报告池”中勾选报告 → 选择医生 → 分发（单页完成）。
> - **方式B（按UI落地）**：保留向导式“创建任务/抽样/分派”，最终仍落到“将一批报告分发给医生”的动作。
>
> 由于你要求“核心功能”，本章节按 **方式B（按UI落地）**描述页面与交互，同时保留方式A作为实现简化选项。

##### 页面目标
- 管理员将一批报告任务分派给医生（专家）。
- 控制分配规则（均分/每人上限），并提交生成分发结果。

##### 信息架构（UI区域）
1. 顶部导航：工作站 / 任务管理 / 统计分析 / 系统设置
2. 步骤条：
   - 1 创建任务
   - 2 标注样本
   - 3 分派任务（当前页）
3. 任务摘要区（只读）：
   - 任务类型：报告标注
   - 抽样数量：如 300（来自上一步选择/抽样结果）
4. 标注专家选择区（Transfer 穿梭框）：
   - 左侧：可选专家列表（支持角色筛选、搜索、全选）
   - 中间：左右移动按钮
   - 右侧：已选择专家列表（支持搜索、勾选移除）
   - **MVP约束**：由于“单报告唯一医生”，如果使用任务均分模式，可选择多医生；若采用“指定医生”模式，则最终每条报告仍只会落到一个医生。
5. 分配规则区：
   - 均分工作量
   - 每人分配上限（可不填）
6. 底部操作：上一步 / 提交任务

##### 专家选择规则（MVP）
- 数据来源：系统医生账号（role=doctor），复核人不在此列表中。
- 支持：
  - 关键字搜索（按姓名/账号）
  - 勾选多选
  - 全选
- “选择角色”筛选：
  - 轻量系统不维护职称/角色层级时，可隐藏该筛选；
  - 若 UI 必须保留，可作为**前端纯筛选项**（不落库），或后端给固定枚举。

##### 分配规则（按你的业务约束落地）
你已确认：**一条报告只分发给唯一指定医生**。
因此需要把“UI中的均分”解释为“批量任务层面的均分”，最终落到 report 仍是单医生：
- 当选择 N 名医生时：
  - 系统按轮询/平均切分，将本任务中的报告逐条分配给其中 1 名医生。
  - 每条报告最终只写入 `assigned_doctor_id = 某一个医生`。
- 每人分配上限：
  - 若填写 `limit`，则单个医生在本次任务中最多分得 limit 份。
  - 若报告数 > N*limit：
    - 提交时提示“容量不足”，要求增加医生或提高上限。

##### 提交任务（核心动作）
- 点击“提交任务”后：
  - 生成一条“分派任务记录”（可选，见数据模型扩展）
  - 对任务范围内的报告执行分配：写入 `assigned_doctor_id`、`assigned_at`、状态→ASSIGNED
  - 记录审计日志（ASSIGN）

##### 方式A（简化实现选项）
若不实现向导任务：
- 管理端报告池页提供“批量分发”：选择报告 + 选择医生（单选）→ 分发。
- 不提供均分与上限；或提供“自动均分（选多医生）”作为高级选项。

#### 分发能力（后端视角，MVP）
- 支持单条/批量分发。
- 规则：每条报告仅能分发给 1 名医生。
- 可选：在医生未提交前支持“回收/改派”。

##### 分派任务记录（可选表，便于追踪批量分派）
若采用方式B，建议新增表 `dispatch_tasks`：
- id, created_by, created_at
- total_reports
- doctor_ids[]（jsonb）
- rule: {"mode":"balanced","limit_per_doctor":10}
- status: CREATED/RUNNING/DONE/FAILED

> 该表非强制；也可仅靠 audit_logs + reports.assigned_doctor_id 追踪。

### 4.2.4 标注结果查看与导出
- 管理端可查看每条报告的标注结果（只读）。
- 导出标注数据（CSV/JSON）。

### 4.2.5 医生账号管理
- 创建医生账号（username、初始密码）。
- 禁用/启用。
- 重置密码。

## 4.3 医生端（Doctor）

### 4.3.1 标注任务工作台列表页（参考UI：医生端报告列表详情页面，核心）

> 对应你提供的原生 HTML：顶部标签（未标注/已标注/报告无误）+ 条件筛选（报告时间、报告单号）+ 表格列表 + 分页。

#### 页面目标
- 医生快速定位自己被分发的报告任务。
- 按状态与条件筛选，进入“查看/标注/复核返工”等后续动作。

#### 信息架构（UI区域）
1. 顶部 Tab：
   - **未标注**：展示待处理任务（ASSIGNED/IN_PROGRESS）
   - **已标注**：展示已提交（SUBMITTED/REVIEW_PENDING/DONE）
   - **报告无误**：展示医生标记“无错误”的报告（等同于提交，但错误项为空或类型=无误）
2. 筛选区：
   - 报告时间：开始日期 - 结束日期
   - 报告单号：文本输入（模糊匹配 external_id 或检查单号字段）
   - 操作按钮：查询、重置
3. 表格区：字段与交互（见下）
4. 分页区：页码、上一页/下一页、结果总数

#### 列表字段（对照你的UI表头，MVP建议字段）
> 注：为了与“轻量、不做复杂组织”一致，**患者姓名/性别/来源科室**建议在真实系统中做脱敏或配置开关；如必须展示，可在导入模板中作为可选字段。

- 序号（前端序号即可）
- 报告时间（report_time，可选字段；缺失则显示“—”）
- 患者ID（patient_id，可选/脱敏）
- 姓名（patient_name，可选/脱敏）
- 检查单号（accession_no，可选）
- 报告编号/报告单号（external_id）
- 性别（sex，可选）
- 检查项目（modality 或 exam_item，可选）
- 来源科室（source_dept，可选，建议不作为权限字段）
- 标注时间（annotation.submitted_at / draft_saved_at）
- 标注人（doctor.username）
- 标识情况（统计摘要，见下）
- 操作：查看、撤销（撤销的含义需定义，见下）

#### “标识情况”字段定义（建议统一口径）
UI中展示：`数量: X, 准确条数: Y, 新增: Z`，建议解释为：
- **数量**：错误项总数（error_items.length）
- **准确条数**：被复核“通过”的错误项数量（若未启用复核，默认=数量）
- **新增**：本次提交相较上次版本新增的错误项数量（MVP若不做版本，可暂显示 0 或隐藏该字段）

> 轻量MVP建议：
> - 不做“准确条数/新增”的复杂统计，先显示 `错误项数量`，其余字段可隐藏或显示 `—`。

#### 操作按钮与规则（MVP）
- **查看**：进入报告详情页（只读）或标注页（可编辑，取决于状态）
  - 未标注/标注中/被驳回：进入“可编辑标注页”
  - 已提交/待复核/已完成：进入“只读详情页”（如需返工必须由复核驳回）
- **撤销**：建议仅在“标注中（草稿）”允许，含义为“清空草稿/重置为未标注”
  - 后端动作：删除 annotation 草稿或将 status 回退为 ASSIGNED
  - 注意：已提交不可撤销

#### 筛选与分页逻辑（接口建议）
- `GET /api/doctor/reports?tab=unannotated|annotated|no_error&date_from=&date_to=&q=&page=&page_size=`

---

### 4.3.2 我的报告列表（核心，后端状态视角）
- 分组/筛选：
  - 待标注（ASSIGNED）
  - 标注中（IN_PROGRESS）
  - 已提交（SUBMITTED/REVIEW_PENDING）
  - 被驳回（REJECTED，若启用复核）
- 列表字段建议：external_id、分发时间、状态、最后保存时间。

### 4.3.2 标注工作站（报告详情 + 标注，参考UI：三栏集成版，核心）

> 对应你提供的原生 HTML：**左侧任务列表** + **中间原始报告文本** + **右侧纠错建议/错误项卡片**，顶部提供“暂存/完成标注/自动进入下一个”。

#### 页面目标
- 医生在同一页面完成：浏览报告全文 → 发现错误点 → 形成结构化错误项 → 暂存或提交。
- 支持高效率“连续标注”（完成后自动进入下一条）。

#### 页面布局（3栏）
1. **左侧栏：任务列表**
   - Tab：全部 / 未标注 / 已标注
   - 列表项最小信息：报告编号（external_id）、检查项目摘要（可选）
   - 选中态高亮
2. **中间栏：原始报告文本（Original）**
   - 展示 report_text（排版为“报告单样式”）
   - 支持字号/缩放（放大/缩小）
   - 支持高亮锚点：当某条错误项与文本位置关联时，在文本中标记（如 UI 中 marker-pos-1/2/3）
3. **右侧栏：纠错建议/错误项卡片**
   - 标题显示数量：纠错建议（N）
   - 每个卡片包含：编号、错误类型、证据片段（原文片段）、建议修正、说明、操作按钮
   - 底部提供“报告无误，直接提交”
4. **顶部操作区**
   - 当前报告信息：报告类型、报告编号
   - 勾选：完成后自动进入下一个
   - 按钮：暂存、完成标注

#### 核心交互与规则（MVP）
1. **暂存（草稿）**
   - 点击“暂存”保存当前错误项列表（annotations.status=DRAFT）
   - reports.status 置为 IN_PROGRESS
2. **完成标注（提交）**
   - 点击“完成标注”提交当前错误项列表（annotations.status=SUBMITTED）
   - 若启用复核：reports.status=REVIEW_PENDING；否则 reports.status=DONE 或 SUBMITTED（按产品口径二选一，建议 DONE）
   - 若勾选“完成后自动进入下一个”：
     - 后端返回 next_report_id（同一列表过滤条件下的下一条）
     - 前端自动切换
3. **忽略 / 修改保存（单条卡片操作）**
   - 忽略：将该建议标记为 ignored（仅影响本报告，不再提示；仍可在“已忽略”查看可选）
   - 修改/保存：将该建议转为一个错误项（或更新已有错误项），并保存到草稿数据
   - 轻量MVP可不做“建议生成”，直接把右侧卡片当作“人工添加的错误项列表”展示
4. **报告无误，直接提交**
   - 提交一个 `error_items=[]` 的标注
   - 状态进入 DONE/REVIEW_PENDING
   - 医生端列表页的“报告无误”Tab依据该标志展示

#### 错误项数据结构（结合UI扩展，建议）
在原有 error_items 基础上，增加两个可选字段以支持“文本锚点/证据片段”：
- `evidence_text`：证据原文片段（如“心中”“2-4m”“CT平扫结果显示”）
- `anchor`：锚点信息（可选）
  - 简版：`anchor_id`（如 marker-pos-1）
  - 完整版：`start_offset/end_offset`（按 report_text 字符偏移定位）

建议结构：
```json
{
  "no_error": false,
  "error_items": [
    {
      "id": "uuid-or-local",
      "error_type": "术语规范性",
      "severity": "中",
      "location": "检查所见",
      "evidence_text": "心中",
      "description": "非标准术语，建议替换为解剖学术语",
      "suggestion": "心脏",
      "anchor": {"anchor_id": "marker-pos-1"}
    }
  ],
  "ignored_items": [
    {"evidence_text": "...", "reason": "可选"}
  ],
  "note": "补充说明（可选）"
}
```

#### 校验规则（MVP）
- 若点击“完成标注”：
  - 当 `no_error=false` 时：`error_items` 可以为空（表示未发现错误但未选择“无误”），建议前端提示确认。
  - 当 `no_error=true` 时：必须保证 `error_items` 为空或忽略（保持一致性）。
- 每条错误项：`error_type`、`description` 建议必填（最小可用）。

#### 接口建议（贴合页面）
- 获取左侧列表（同医生权限）：`GET /api/doctor/reports?status=&q=&page=&page_size=`
- 获取报告详情 + 当前草稿：`GET /api/doctor/reports/{id}`
- 暂存：`POST /api/doctor/reports/{id}/annotation/draft`
- 提交：`POST /api/doctor/reports/{id}/annotation/submit`
  - resp 可包含：`{"next_report_id": "..."}`（用于自动下一条）
- （可选）忽略建议：`POST /api/doctor/reports/{id}/annotation/ignore` body: `{evidence_text, reason?}`

> 注：右侧“纠错建议”如果未来要由规则引擎/模型生成，可新增 `suggestions` 概念；本期轻量版可全部由医生手动新增。

## 4.4 复核端（Reviewer，可选）
- 待复核列表：展示 external_id、医生、提交时间。
- 复核详情：查看报告全文 + 标注结果。
- 操作：通过 / 驳回（驳回原因必填）。

## 5. 状态机

### 5.1 ReportStatus
- `IMPORTED`：已导入未分发
- `ASSIGNED`：已分发待标注
- `IN_PROGRESS`：标注中（已有草稿）
- `SUBMITTED`：已提交（若不启用复核可视为完成）
- `REVIEW_PENDING`：待复核（启用复核时）
- `REJECTED`：已驳回（启用复核时）
- `DONE`：已完成（复核通过或不启用复核时提交即完成）

### 5.2 关键流转
- IMPORTED → ASSIGNED（分发）
- ASSIGNED → IN_PROGRESS（保存草稿）
- IN_PROGRESS/ASSIGNED → SUBMITTED 或 REVIEW_PENDING（提交）
- REVIEW_PENDING → DONE（复核通过）
- REVIEW_PENDING → REJECTED（复核驳回）
- REJECTED → REVIEW_PENDING（医生修改后重新提交）

## 6. 导入规格（Excel/CSV + 中文表头）

### 6.1 表头映射（示例，可扩展）
内部字段 → 可接受表头：
- `report_text`：报告全文 / 报告内容 / 报告文本 / 报告 / report_text / text
- `external_id`：报告ID / 报告编号 / 检查号 / 单号 / external_id / report_id
- `report_time`：报告时间 / 出报告时间 / report_time
- `study_time`：检查时间 / 拍片时间 / study_time
- `modality`：检查类型 / 影像类型 / 模态 / modality

#### 6.1.1 固定导入表头（前端字段映射，xlsx/csv）
说明：导入时需要识别表头字段，并在前端提供“字段映射”能力。

固定表头 → 中文展示/内部语义：
- `RIS_NO` → 检查号（必选/必须识别映射）
- `MODALITY` → 检查类型（必选/必须识别映射）
- `PATIENT_SEX` → 性别（必选/必须识别映射）
- `PATIENT_AGE` → 年龄（必选/必须识别映射）
- `EXAM_ITEM` → 检查项目（必选/必须识别映射）
- `EXAM_MODE` → 检查模式（可选：允许不识别/不映射）
- `EXAM_GROUP` → 检查组（可选：允许不识别/不映射）
- `DESCRIPTION` → 检查所见/报告描述（必选/必须识别映射）
- `IMPRESSION` → 诊断意见/印象（必选/必须识别映射）

约束：除 `EXAM_MODE`、`EXAM_GROUP` 外，其余字段缺失或无法识别时，导入流程应提示并阻止进入“完成映射/开始导入”。

### 6.2 Excel 约定
- 读取第 1 个 sheet。
- 第 1 行表头。

### 6.3 CSV 约定
- UTF-8 编码（允许 BOM）。
- 第 1 行表头。

### 6.4 校验规则（MVP）
- `report_text` 必填。
- 行级失败不影响整体导入。
- `external_id` 允许重复：
  - 重复不阻塞导入
  - 产生 warning（可在任务详情中展示/下载）

### 6.5 错误明细文件（B 方案）
- 失败行写入 `import_errors_{task_id}.jsonl`（JSONL 格式）。
- 每行结构：`row, external_id, reason, raw`。

## 7. 数据模型（建议）

### 7.1 users
- id, username, password_hash, role, enabled, created_at, updated_at

### 7.2 reports
- id, external_id, report_text, imported_by, imported_at, status,
  assigned_doctor_id, assigned_at, submitted_at

### 7.3 annotations
- id, report_id(unique), doctor_id, data(jsonb), status(DRAFT/SUBMITTED),
  draft_saved_at, submitted_at, updated_at

### 7.4 reviews（可选）
- id, report_id, annotation_id, reviewer_id, decision(APPROVED/REJECTED), reason, reviewed_at

### 7.5 import_tasks（异步导入）
- id, status(PENDING/RUNNING/SUCCESS/FAILED), file_name, file_path,
  total_rows, success_rows, failed_rows, error_report_path,
  created_by, created_at, started_at, finished_at, message

### 7.6 audit_logs（建议）
- actor_id, action, target_type, target_id, meta(jsonb), created_at

## 8. API 清单（MVP）

> 仅列核心接口，最终以 OpenAPI 文档为准。

### 8.1 Auth
- `POST /api/auth/login`
- `GET /api/auth/me`

### 8.2 Users（admin）
- `POST /api/users`
- `GET /api/users?role=doctor`
- `PATCH /api/users/{id}`

### 8.3 Reports（admin）
- `POST /api/reports/import` → 返回 `{task_id}`
- `GET /api/reports?status=&q=&page=&page_size=`
- `GET /api/reports/{id}`
- `POST /api/reports/assign` body: `{report_ids:[], doctor_id:""}`

### 8.4 Import Tasks（admin）
- `GET /api/import-tasks/{task_id}`
- `GET /api/import-tasks/{task_id}/errors`

### 8.5 Doctor
- `GET /api/doctor/reports?status=`
- `GET /api/doctor/reports/{id}`
- `POST /api/doctor/reports/{id}/annotation/draft`
- `POST /api/doctor/reports/{id}/annotation/submit`

### 8.6 Reviewer（可选）
- `GET /api/reviewer/reports?status=REVIEW_PENDING`
- `POST /api/reviewer/reports/{id}/approve`
- `POST /api/reviewer/reports/{id}/reject`

### 8.7 Export（admin）
- `GET /api/export/annotations?status=`

## 9. 非功能需求
- 权限隔离：医生只可访问自己的报告。
- 脱敏：导入/展示时需提醒避免敏感信息；如包含敏感字段可做基础脱敏策略（后续增强）。
- 性能：单次导入几千条，采用异步任务 + 批量入库（每 500~1000 行一批）。
- 可用性：标注页防误退出提示；草稿提示。
- 审计：导入、分发、提交、复核等关键操作需写 audit log。

## 10. 页面清单、路由与权限矩阵（接近交付版）

> 说明：以下以 Web 前后端分离为前提，前端可按路由划分模块。若采用单页应用（SPA），可直接用该路由表。

### 10.1 路由清单（建议）

#### 公共
- `/login` 登录页

#### 管理端（Admin）
- `/admin/reports` 报告池列表（导入入口、筛选、批量分发入口）
- `/admin/reports/:id` 报告详情（只读报告文本 + 标注结果查看）
- `/admin/import-tasks/:id` 导入任务详情（进度、统计、失败明细下载）
- `/admin/users` 医生账号管理
- `/admin/dispatch` 分派任务向导（可选，按UI方式B）
- `/admin/export` 导出中心（可选：提供导出按钮与导出记录）

#### 医生端（Doctor）
- `/doctor/workbench` 标注任务工作台列表页（参考UI：未标注/已标注/报告无误 + 筛选）
- `/doctor/annotate/:id` 标注工作站（三栏集成）

#### 复核端（Reviewer，可选）
- `/reviewer/tasks` 待复核列表
- `/reviewer/review/:reportId` 复核详情（只读报告 + 标注 + 通过/驳回）

### 10.2 权限矩阵（RBAC）
- 管理端路由：仅 `admin`
- 医生端路由：仅 `doctor`
- 复核端路由：仅 `reviewer`（若启用）

## 11. 字段字典与数据口径（接近交付版）

### 11.1 导入模板字段（Excel/CSV）
> 轻量系统建议仅强制 `报告全文`；其余字段按你UI是否展示决定。

| 内部字段 | 推荐中文表头 | 必填 | 说明 |
|---|---|---:|---|
| report_text | 报告全文 | 是 | 报告原文全文，用于展示与标注 |
| external_id | 报告编号/报告ID/报告单号 | 否 | 允许重复；用于检索与定位 |
| report_time | 报告时间 | 否 | 日期或日期时间 |
| study_time | 检查时间 | 否 | 日期或日期时间 |
| modality | 检查类型/检查项目 | 否 | 如 CT/MR/DR/US；或“CT 胸部平扫” |
| patient_id | 患者ID | 否 | 建议脱敏ID |
| patient_name | 姓名 | 否 | 建议脱敏/开关展示 |
| sex | 性别 | 否 | 男/女/未知 |
| accession_no | 检查单号 | 否 | 对应 UI 的“检查单号” |
| source_dept | 来源科室 | 否 | 仅展示用，不作为权限字段 |

> 注：以上可选字段未提供时，UI显示“—”。

### 11.2 Reports 字段口径
- `reports.id`：系统内部唯一ID
- `reports.external_id`：外部报告编号（可重复）
- `reports.status`：状态机（见第5章）
- `reports.assigned_doctor_id`：该报告唯一医生
- `reports.submitted_at`：医生提交时间（无复核时可视为完成时间）

### 11.3 Annotations 字段口径
- `annotations.data.no_error`：是否“报告无误”
  - 若 true：要求 `error_items` 为空（或忽略项不计入错误）
- `annotations.data.error_items[]`：错误项数组
  - 最小必填：`error_type`、`description`
  - 推荐：`severity`、`location`、`evidence_text`、`suggestion`、`anchor`

### 11.4 医生端列表页“标识情况”口径（建议简化）
- MVP建议显示：`错误项数量 = len(error_items)`
- 若后续启用版本/复核：
  - 准确条数：复核通过的错误项数量
  - 新增：本次提交相对上一版本新增的错误项数量

## 12. 接口契约（关键接口请求/响应示例）

> 注：接口以 `/api` 为前缀，采用 JWT Bearer Token。

### 12.1 登录
**POST** `/api/auth/login`

Request:
```json
{ "username": "admin", "password": "***" }
```
Response:
```json
{ "access_token": "jwt...", "role": "admin" }
```

### 12.2 导入报告（异步任务）
**POST** `/api/reports/import`（admin）
- `multipart/form-data`：`file`

Response:
```json
{ "task_id": "0f8a...", "status": "PENDING" }
```

### 12.3 查询导入任务
**GET** `/api/import-tasks/{task_id}`（admin）

Response:
```json
{
  "task_id": "0f8a...",
  "status": "RUNNING",
  "file_name": "报告导入.xlsx",
  "total_rows": 3200,
  "success_rows": 2800,
  "failed_rows": 12,
  "warnings_count": 8,
  "message": null,
  "error_report_url": "/api/import-tasks/0f8a.../errors"
}
```

### 12.4 下载导入失败明细
**GET** `/api/import-tasks/{task_id}/errors`（admin）
- 返回 JSONL 文件（每行一个失败记录）

### 12.5 报告池列表
**GET** `/api/reports?status=&q=&page=&page_size=`（admin）

Response（示意）:
```json
{
  "items": [
    {
      "id": "...",
      "external_id": "XR-20231024-0892",
      "report_time": "2023-10-25 09:12:00",
      "status": "IMPORTED",
      "assigned_doctor_name": null
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 145
}
```

### 12.6 分发（简化方式A：指定医生）
**POST** `/api/reports/assign`（admin）

Request:
```json
{ "report_ids": ["...","..."], "doctor_id": "..." }
```
Response:
```json
{ "assigned": 2 }
```

### 12.7 医生端列表
**GET** `/api/doctor/reports?tab=unannotated|annotated|no_error&date_from=&date_to=&q=&page=&page_size=`

### 12.8 获取报告详情（医生）
**GET** `/api/doctor/reports/{id}`

Response（示意）:
```json
{
  "id": "...",
  "external_id": "XR-20231024-0892",
  "report_text": "...",
  "status": "IN_PROGRESS",
  "annotation": {
    "status": "DRAFT",
    "data": { "no_error": false, "error_items": [] }
  }
}
```

### 12.9 暂存（草稿）
**POST** `/api/doctor/reports/{id}/annotation/draft`

Request:
```json
{ "data": { "no_error": false, "error_items": [/*...*/], "note": "" } }
```
Response:
```json
{ "ok": true, "saved_at": "2026-03-11T03:20:00Z" }
```

### 12.10 提交（完成标注）
**POST** `/api/doctor/reports/{id}/annotation/submit`

Request:
```json
{ "data": { "no_error": true, "error_items": [] } }
```
Response:
```json
{ "ok": true, "submitted_at": "2026-03-11T03:22:00Z", "next_report_id": "..." }
```

## 13. 验收标准（MVP，更新版）
1. 管理员可上传 Excel/CSV（中文表头），创建导入任务；任务可查询进度、成功/失败统计。
2. 导入完成后报告出现在报告池；失败行可下载完整错误明细文件（JSONL/CSV）。
3. 管理员可分发报告：
   - 简化方式A：批量勾选报告→指定医生→分发成功；
   - 或方式B：按向导提交任务后完成均分分配。
4. 分发规则满足：单报告唯一医生；医生仅可看到分配给自己的报告。
5. 医生端工作台列表支持：未标注/已标注/报告无误 Tab；按报告时间、报告单号查询；分页展示。
6. 医生端三栏标注页支持：暂存草稿、完成标注提交、（可选）自动进入下一条；“报告无误直接提交”。
7. 管理端能查看标注结果并按条件导出（CSV/JSON）。
8. 若启用复核：复核人可通过/驳回；驳回原因必填；医生可返工后重新提交。

---

## 附录A：实现建议（非需求）
- 后端：FastAPI + PostgreSQL + Redis + RQ（异步导入任务）
- 标注数据：使用 `jsonb` 存 `annotations.data`，便于后续扩展 `anchor/evidence_text/ignored_items`。
- 导入：批量入库（每 500~1000 行一批），失败行写 JSONL 文件。
