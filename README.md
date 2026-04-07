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

## 压测（k6）
- 脚本位置：`scripts/k6/admin_read_load.js`
- 使用说明：`scripts/k6/README.md`

## 管理员初始化
- 服务启动时不再自动创建默认管理员账号。
- 首次部署后，请进入 `backend/` 目录执行 `python scripts/init_admin.py`。
- 脚本会交互式提示输入管理员用户名和密码。

## 本机开发（macOS + Miniconda）
- Miniconda 已安装但当前 shell 找不到 `conda` 时，可先执行 `source /opt/miniconda3/bin/activate`。
- 后端可直接使用 [`backend/environment.yml`](/Users/enjoy0710/Desktop/medical-report-annotation/backend/environment.yml) 创建环境：
  `cd backend && conda env create -f environment.yml || conda env update -f environment.yml --prune`
- 激活后端环境后，按需创建 [`backend/.env`](/Users/enjoy0710/Desktop/medical-report-annotation/backend/.env)：
  `DATABASE_URL=postgresql+psycopg2://<你的本机数据库用户名>@127.0.0.1:5432/med_anno`
- 当前仓库前端开发代理默认转发到 `http://127.0.0.1:8088`，也可以通过 [`frontend/.env.example`](/Users/enjoy0710/Desktop/medical-report-annotation/frontend/.env.example) 对应的 `VITE_API_PROXY_TARGET` 覆盖。
- 推荐本机开发启动顺序：
  1. `brew services start postgresql@15`
  2. `cd backend && conda activate medanno && uvicorn app.main:app --host 127.0.0.1 --port 8088 --reload`
  3. `cd frontend && npm install && npm run dev`
  4. 首次部署执行 `cd backend && python scripts/init_admin.py`
