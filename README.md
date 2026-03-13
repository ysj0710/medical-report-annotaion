# 医疗影像报告标注系统

轻量版 MVP：管理端导入与分发 → 医生端标注 →（可选）复核 → 导出。

## 目录结构
```
medical-report-annotation/
  backend/        # 后端服务（FastAPI 方向，可调整）
  frontend/       # 前端（Web，角色内路由）
  docs/           # 方案与接口文档
  infra/          # 部署/基础设施（docker-compose 等）
  scripts/        # 运维/开发脚本
```

## 下一步
- 确认技术栈（前端框架、数据库、异步任务方案）。
- 生成最小可跑的后端骨架 + 前端路由骨架。
