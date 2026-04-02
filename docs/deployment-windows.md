# 医疗影像报告标注系统 - Windows 环境部署文档

## 一、概述

本文档描述如何在 **Windows 电脑** 上部署医疗影像报告标注系统，**不使用 Docker**，适合测试环境或个人远程电脑部署。

### 1.1 部署环境
- **操作系统**: Windows 10/11 或 Windows Server
- **后端**: FastAPI + SQLAlchemy + PostgreSQL
- **前端**: Vue 3 + Vite
- **部署方式**: 手动安装 + 服务运行

### 1.2 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Windows 远程电脑                          │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                    浏览器访问                          │   │
│   │              http://localhost:80 或 IP               │   │
│   └───────────────────────┬─────────────────────────────┘   │
│                           │                                  │
│   ┌───────────────────────▼─────────────────────────────┐   │
│   │   Nginx (Windows版)                                  │   │
│   │   - 监听 80 端口                                      │   │
│   │   - 提供前端静态文件                                  │   │
│   │   - 代理 API 请求到后端                               │   │
│   └───────────────────────┬─────────────────────────────┘   │
│                           │                                  │
│           ┌───────────────┴───────────────┐                 │
│           │                               │                 │
│   ┌───────▼───────┐              ┌────────▼────────┐       │
│   │  前端静态文件  │              │  Python FastAPI │       │
│   │  (dist目录)   │              │   (8000端口)    │       │
│   │               │              │                 │       │
│   └───────────────┘              └────────┬────────┘       │
│                                            │                │
│                               ┌────────────▼────────┐       │
│                               │   PostgreSQL        │       │
│                               │   (5432端口)        │       │
│                               └─────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、准备工作（开发机）

在开发机上准备好部署包：

### 2.1 打包后端代码

```bash
# 进入项目目录
cd /path/to/medical-report-annotation

# 打包后端（排除 venv）
tar -czf backend.tar.gz --exclude=backend/venv backend/
```

### 2.2 构建前端

```bash
cd frontend
npm install
npm run build

# 打包前端
tar -czf frontend-dist.tar.gz dist/
```

### 2.3 上传到 Windows 远程电脑

使用文件传输工具（如 WinSCP、Xshell、或共享文件夹）将以下文件上传到远程电脑：
- `backend.tar.gz`
- `frontend-dist.tar.gz`

上传到任意目录，例如 `C:\medical-annotation\`

---

## 三、Windows 环境部署步骤

### 第一步：安装基础软件

#### 1.1 安装 PostgreSQL

1. 下载 PostgreSQL for Windows:
   - 官网: https://www.postgresql.org/download/windows/
   - 下载安装包: **PostgreSQL 15.x** (64-bit)

2. 运行安装程序，按向导安装:
   - **安装目录**: 默认 `C:\Program Files\PostgreSQL\15`
   - **数据目录**: 默认 `C:\Program Files\PostgreSQL\15\data`
   - **密码**: 设置一个强密码，记录下来（例如: `YourPGPassword123!`）
   - **端口**: 默认 `5432`
   - **Locale**: 默认或选择 `Chinese (Simplified)`

3. 安装完成后，确认服务已启动:
   - 打开 **服务管理器** (services.msc)
   - 找到 `postgresql-x64-15`，状态应为 **正在运行**

#### 1.2 安装 Python

1. 下载 Python:
   - 官网: https://www.python.org/downloads/
   - 下载: **Python 3.11.x** (64-bit)

2. 运行安装程序:
   - ✅ **必须勾选** "Add Python to PATH"
   - 点击 **"Install Now"**

3. 验证安装:
   ```cmd
   python --version
   pip --version
   ```

#### 1.3 安装 Nginx for Windows

1. 下载 Nginx:
   - 官网: http://nginx.org/en/download.html
   - 下载: **Stable version** (如 nginx-1.24.0)

2. 解压到 `C:\nginx`:
   ```
   C:\nginx\
       ├─ conf\
       ├─ html\
       ├─ logs\
       └─ nginx.exe
   ```

3. 测试运行:
   ```cmd
   cd C:\nginx
   start nginx
   ```
   打开浏览器访问 `http://localhost`，看到 "Welcome to nginx!" 表示成功。

---

### 第二步：创建数据库

#### 2.1 使用 pgAdmin 创建数据库（图形界面）

1. 打开 **pgAdmin 4**（开始菜单中找到）

2. 连接到服务器:
   - 双击 "Servers" → "PostgreSQL 15"
   - 输入安装时设置的密码

3. 创建数据库:
   - 右键点击 "Databases" → "Create" → "Database"
   - **Database**: `med_anno`
   - 点击 "Save"

4. 创建用户:
   - 右键点击 "Login/Group Roles" → "Create" → "Login/Group Role"
   - **General** 标签页:
     - Name: `meduser`
   - **Definition** 标签页:
     - Password: `YourStrongPassword123!`
     - Confirm password: 再输一遍
   - **Privileges** 标签页:
     - ✅ Can login? = Yes
   - 点击 "Save"

5. 授权:
   - 右键点击 `med_anno` 数据库 → "Properties"
   - "Security" 标签页:
   - 点击 "+" 添加权限:
     - Grantee: `meduser`
     - Privileges: 勾选 ALL
   - 点击 "Save"

#### 2.2 或使用命令行创建

打开 **SQL Shell (psql)**（开始菜单中找到）:

```sql
-- 输入密码后执行以下命令
CREATE DATABASE med_anno;
CREATE USER meduser WITH PASSWORD 'YourStrongPassword123!';
GRANT ALL PRIVILEGES ON DATABASE med_anno TO meduser;
\q
```

---

### 第三步：部署后端服务

#### 3.1 解压后端代码

```cmd
# 创建目录
mkdir C:\medical-annotation
cd C:\medical-annotation

# 解压（使用 7-Zip 或 Windows 自带 tar）
tar -xzf C:\Users\YourName\Downloads\backend.tar.gz
```

#### 3.2 创建 Python 虚拟环境

```cmd
cd C:\medical-annotation\backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate

# 虚拟环境激活后，提示符前面会有 (venv)
```

#### 3.3 安装依赖

```cmd
# 确保在虚拟环境中
pip install --upgrade pip
pip install -r requirements.txt

# 安装 Windows 下运行需要的额外依赖
pip install waitress
```

#### 3.4 配置环境变量

创建 `.env` 文件:

```cmd
cd C:\medical-annotation\backend

# 使用 PowerShell 生成随机密钥
powershell -Command "-join ((1..32) | ForEach-Object { '{0:X2}' -f (Get-Random -Max 256) })"
# 复制生成的 64 位十六进制字符串

# 创建 .env 文件
notepad .env
```

在记事本中输入以下内容（替换密码）:
```env
DATABASE_URL=postgresql+psycopg2://meduser:YourStrongPassword123!@localhost:5432/med_anno
SECRET_KEY=你生成的64位十六进制密钥
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

保存并关闭。

#### 3.5 创建 Windows 启动脚本

创建文件 `C:\medical-annotation\backend\start_server.bat`:

```batch
@echo off
cd /d C:\medical-annotation\backend
call venv\Scripts\activate

:: 使用 waitress 作为 WSGI 服务器（Windows 友好）
waitress-serve --host=127.0.0.1 --port=8000 app.main:app
```

测试启动:
```cmd
cd C:\medical-annotation\backend
start_server.bat
```

看到类似输出表示成功:
```
INFO:waitress:Serving on http://127.0.0.1:8000
```

按 `Ctrl+C` 停止，继续下一步。

---

### 第四步：初始化管理员账号 ⚠️ 关键步骤

**重要说明：**
- 系统启动后**不会自动创建**管理员账号
- 必须先执行此步骤，否则无法登录
- 只能创建**一个**初始管理员

#### 4.1 执行初始化脚本

```cmd
cd C:\medical-annotation\backend
venv\Scripts\activate

# 运行初始化脚本（交互式）
python scripts\init_admin.py
```

#### 4.2 交互式输入

脚本会提示输入：

```
Admin username: admin
Admin password:
Confirm password:
Initial admin created successfully: 'admin'
```

**注意事项：**
- `Admin password`: 输入密码时**不显示任何字符**，正常输入后按回车
- 两次密码必须一致

#### 4.3 命令行参数方式（可选）

```cmd
cd C:\medical-annotation\backend
venv\Scripts\activate
python scripts\init_admin.py --username admin --password "YourSecurePassword123!"
```

#### 4.4 脚本安全特性

- ✅ 检查用户名是否已存在
- ✅ 检查是否已有活跃管理员（防止重复创建）
- ✅ 密码使用 bcrypt 加密存储
- ✅ 创建的管理员自动拥有 `can_view_all=True`

---

### 第五步：部署前端

#### 5.1 解压前端文件

```cmd
cd C:\medical-annotation

# 解压前端
tar -xzf C:\Users\YourName\Downloads\frontend-dist.tar.gz

# 确认目录结构
dir dist
# 应该包含 index.html 和 assets 文件夹
```

#### 5.2 验证前端文件

```cmd
dir C:\medical-annotation\dist
```

输出应包含:
```
index.html
assets\
```

---

### 第六步：配置 Nginx

#### 6.1 编辑 Nginx 配置

打开 `C:\nginx\conf\nginx.conf`，找到 `server` 段落，修改为:

```nginx
server {
    listen       80;
    server_name  localhost;

    # 日志
    access_log  logs/host.access.log;
    error_log   logs/error.log;

    # 前端静态文件
    location / {
        root   C:/medical-annotation/dist;
        index  index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # 上传文件大小限制
    client_max_body_size 100M;
}
```

**注意**: Windows 路径使用斜杠 `/` 或双反斜杠 `\\`，不要用单反斜杠。

#### 6.2 启动 Nginx

```cmd
cd C:\nginx

# 启动 nginx
start nginx

# 或者使用
nginx.exe
```

#### 6.3 验证 Nginx 配置

```cmd
cd C:\nginx
nginx -t
```

看到 `successful` 表示配置正确。

---

### 第七步：创建 Windows 服务（可选但推荐）

为了让后端和 Nginx 随 Windows 启动自动运行，使用 NSSM 创建服务。

#### 7.1 安装 NSSM

1. 下载 NSSM: https://nssm.cc/download
2. 解压 `nssm.exe` 到 `C:\Windows\System32\` (64位系统) 或 `C:\Windows\SysWOW64\` (32位系统)

#### 7.2 创建后端服务

```cmd
nssm install MedicalAnnotationAPI
```

在弹出的窗口中填写:
- **Path**: `C:\medical-annotation\backend\venv\Scripts\waitress-serve.exe`
- **Startup directory**: `C:\medical-annotation\backend`
- **Arguments**: `--host=127.0.0.1 --port=8000 app.main:app`

点击 "Install service"

启动服务:
```cmd
nssm start MedicalAnnotationAPI
```

#### 7.3 创建 Nginx 服务

```cmd
nssm install MedicalAnnotationNginx
```

填写:
- **Path**: `C:\nginx\nginx.exe`
- **Startup directory**: `C:\nginx`

点击 "Install service"

启动服务:
```cmd
nssm start MedicalAnnotationNginx
```

#### 7.4 设置开机自启

```cmd
nssm set MedicalAnnotationAPI Start SERVICE_AUTO_START
nssm set MedicalAnnotationNginx Start SERVICE_AUTO_START
```

---

### 第八步：配置 Windows 防火墙

#### 8.1 开放 80 端口

**方式一：图形界面**
1. 打开 "Windows Defender 防火墙"
2. 点击 "高级设置"
3. 点击 "入站规则" → "新建规则"
4. 选择 "端口" → "下一步"
5. 选择 "TCP"，输入 "80" → "下一步"
6. 选择 "允许连接" → "下一步"
7. 勾选 "域"、"专用"、"公用" → "下一步"
8. 名称: "Medical Annotation HTTP" → "完成"

**方式二：命令行（管理员权限）**

```cmd
netsh advfirewall firewall add rule name="Medical Annotation HTTP" dir=in action=allow protocol=TCP localport=80
```

#### 8.2 验证端口

```cmd
netstat -an | findstr :80
```

应看到 `0.0.0.0:80` 或 `:::80` 处于 `LISTENING` 状态。

---

### 第九步：验证部署

#### 9.1 本地访问测试

在远程电脑上打开浏览器:
```
http://localhost/
```

#### 9.2 局域网访问测试

获取远程电脑的 IP:
```cmd
ipconfig
```

在其他电脑上访问:
```
http://<远程电脑IP>/
```

#### 9.3 功能验证清单

| 验证项 | 操作 | 预期结果 |
|-------|------|---------|
| 登录 | 输入第四步创建的管理员账号密码 | 成功进入管理后台 |
| 创建医生 | 用户管理 → 创建医生账号 | 医生账号创建成功 |
| 导入报告 | 报告管理 → 导入 Excel | 报告成功导入 |
| 分发报告 | 选择报告 → 分发给医生 | 医生能看到分配的报告 |
| 医生标注 | 医生账号登录 → 标注报告 | 标注成功保存 |
| 导出结果 | 管理端 → 导出标注结果 | 能下载 CSV/JSON |

---

## 四、日常管理

### 4.1 启动/停止服务

**手动方式（无 NSSM 服务）:**
```cmd
:: 启动后端
cd C:\medical-annotation\backend
start_server.bat

:: 启动 Nginx
cd C:\nginx
start nginx

:: 停止 Nginx
nginx -s stop

:: 停止后端
:: 在运行 start_server.bat 的窗口按 Ctrl+C
```

**使用 NSSM 服务:**
```cmd
:: 启动
nssm start MedicalAnnotationAPI
nssm start MedicalAnnotationNginx

:: 停止
nssm stop MedicalAnnotationAPI
nssm stop MedicalAnnotationNginx

:: 重启
nssm restart MedicalAnnotationAPI
nssm restart MedicalAnnotationNginx

:: 查看状态
nssm status MedicalAnnotationAPI
```

### 4.2 查看日志

- **后端日志**: `C:\medical-annotation\backend\` 下控制台输出
- **Nginx 访问日志**: `C:\nginx\logs\access.log`
- **Nginx 错误日志**: `C:\nginx\logs\error.log`
- **PostgreSQL 日志**: `C:\Program Files\PostgreSQL\15\data\log\`

---

## 五、备份策略

### 5.1 数据库备份脚本

创建 `C:\medical-annotation\backup.bat`:

```batch
@echo off
set BACKUP_DIR=C:\medical-annotation\backups
set DATE=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set DATE=%DATE: =0%

if not exist %BACKUP_DIR% mkdir %BACKUP_DIR%

"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe" -h localhost -U meduser -d med_anno > %BACKUP_DIR%\med_anno_%DATE%.sql

echo Backup completed: %BACKUP_DIR%\med_anno_%DATE%.sql
```

**注意**: 首次运行前需要设置环境变量 `PGPASSWORD` 或使用 `.pgpass` 文件避免输入密码。

### 5.2 设置定时任务

1. 打开 "任务计划程序"
2. 点击 "创建基本任务"
3. 名称: "Medical Annotation Backup"
4. 触发器: "每天"，时间: 凌晨 2:00
5. 操作: "启动程序"
6. 程序: `C:\medical-annotation\backup.bat`
7. 点击 "完成"

---

## 六、常见问题排查

### 6.1 PostgreSQL 连接失败

```cmd
:: 检查 PostgreSQL 服务状态
sc query postgresql-x64-15

:: 如果未运行，启动服务
net start postgresql-x64-15
```

### 6.2 后端无法启动

```cmd
:: 检查依赖是否安装
cd C:\medical-annotation\backend
venv\Scripts\activate
pip list | findstr fastapi

:: 手动测试启动
python -c "from app.main import app; print('Import OK')"
```

### 6.3 Nginx 403 错误

检查前端文件路径是否正确:
```cmd
dir C:\medical-annotation\dist\index.html
```

检查 Nginx 配置文件中的路径是否使用正斜杠 `/`。

### 6.4 无法从其他电脑访问

1. 检查防火墙是否开放 80 端口
2. 检查远程电脑的 IP 是否正确
3. 检查 Nginx 是否监听所有接口（配置中使用 `listen 80` 不带 IP）

### 6.5 端口被占用

```cmd
:: 查看 80 端口占用
netstat -ano | findstr :80

:: 查看 8000 端口占用
netstat -ano | findstr :8000

:: 结束占用进程（将 <PID> 替换为实际进程ID）
taskkill /PID <PID> /F
```

---

## 七、安全建议

1. **管理员密码**: 使用强密码（12位以上，包含大小写字母、数字、符号）
2. **数据库密码**: 定期更换，避免使用默认密码
3. **Windows 防火墙**: 仅开放必要的端口（80）
4. **网络隔离**: 如果是测试环境，确保不在公网暴露
5. **定期备份**: 建议每天自动备份数据库
6. **更新维护**: 定期更新 PostgreSQL、Python、Nginx 到最新版本

---

## 八、完全卸载

如需卸载系统:

1. 停止并删除 NSSM 服务:
   ```cmd
   nssm stop MedicalAnnotationAPI
   nssm stop MedicalAnnotationNginx
   nssm remove MedicalAnnotationAPI confirm
   nssm remove MedicalAnnotationNginx confirm
   ```

2. 删除文件夹:
   - `C:\medical-annotation\`
   - `C:\nginx\`（如果不再需要）

3. 卸载软件:
   - PostgreSQL（通过控制面板的 "程序和功能"）
   - Python（可选）

---

**文档版本**: v1.0  
**适用系统**: Windows 10/11/Server  
**最后更新**: 2026-04-02
