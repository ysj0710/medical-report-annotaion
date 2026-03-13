# Architecture

MVP 结构：
- 后端：REST API（导入、分发、标注、导出）
- 前端：管理端 + 医生端 + 复核端（角色路由）
- 异步：导入任务（后续选 RQ/Celery/Arq）
