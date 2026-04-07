# 医疗影像报告标注系统 公司 Windows 在线部署手册

这份文档对应的前提是：

- 你在公司有一台可以联网的 Windows 电脑
- 这台电脑已经安装好了 `git`、`python`、`node`、`npm`
- 你希望直接通过 Git 拉代码，然后在这台 Windows 上完整部署系统
- 不使用 Docker

本文档只基于当前项目实际依赖来写。

## 1. 部署目标

最终你会在这台公司 Windows 上跑起来这 4 部分：

1. PostgreSQL
2. Python 后端
3. 前端静态文件
4. Nginx

访问关系如下：

```text
浏览器
  -> Nginx :80
     -> /            前端 dist
     -> /api         代理到 127.0.0.1:8000
        -> FastAPI 后端
           -> PostgreSQL
```

## 2. 先确认这台公司 Windows 已经具备的环境

打开 PowerShell，执行：

```powershell
git --version
python --version
node --version
npm --version
```

建议版本基线：

- Python：3.11 x64
- Node.js：20 LTS

如果 Python 不是 3.11，后面医院离线包准备时会更麻烦。  
建议这台公司 Windows 和后面医院 Windows 都统一用 Python 3.11 x64。

## 3. 这台公司 Windows 还需要安装的软件

即使 `git/node/npm/python` 已经有了，下面这些通常还要装：

1. PostgreSQL 15 x64
2. Nginx Windows 版
3. NSSM
   可选，但强烈建议，用来注册 Windows 服务

推荐安装目录：

- PostgreSQL：默认安装目录即可
- Nginx：`C:\nginx`
- NSSM：`C:\nssm`

## 4. 拉取代码

### 4.1 创建部署目录

```powershell
New-Item -ItemType Directory -Force C:\medical-report-annotation | Out-Null
New-Item -ItemType Directory -Force C:\medical-report-annotation\logs | Out-Null
Set-Location C:\
```

### 4.2 使用 Git 克隆仓库

你可以用你在公司网络中能访问的仓库地址。

当前项目本地配置里可见的仓库地址有两个：

- GitHub: `https://github.com/ysj0710/medical-report-annotaion.git`
- GitLab: `http://gitlab.dev.jvlei.com/yuansijie/medical-report-annotation`

示例：

```powershell
git clone https://github.com/ysj0710/medical-report-annotaion.git C:\medical-report-annotation
Set-Location C:\medical-report-annotation
git checkout master
git pull origin master
```

如果你实际部署的不是 `master`，改成你的真实分支名。

### 4.3 记录本次部署代码版本

建议把当前提交号记下来，方便后面做医院离线包时保持一致：

```powershell
Set-Location C:\medical-report-annotation
git rev-parse HEAD
```

把这个 commit id 保存一下。

## 5. 安装并初始化 PostgreSQL

### 5.1 安装 PostgreSQL

安装时建议：

- 版本：15.x
- 端口：`5432`
- 超级用户：`postgres`
- 记住你设置的 `postgres` 密码

安装完成后，一般会自动注册 Windows 服务并启动。

### 5.2 创建业务数据库和业务用户

打开 PowerShell：

```powershell
& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -h 127.0.0.1 -d postgres
```

输入 `postgres` 密码后，在 `psql` 里执行：

```sql
CREATE USER meduser WITH PASSWORD '这里换成你的数据库密码';
CREATE DATABASE med_anno OWNER meduser;
\q
```

注意：

- 这个数据库密码建议只用字母、数字和常见安全字符
- 尽量不要包含 `@`、`:`、`/`、`#`、`%`
- 否则后面写 `DATABASE_URL` 时需要 URL 编码

## 6. 部署后端

### 6.1 创建虚拟环境并安装依赖

```powershell
Set-Location C:\medical-report-annotation\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 6.2 创建后端配置文件 `.env`

先生成一个随机密钥：

```powershell
$SECRET = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
$SECRET
```

然后写配置文件：

```powershell
Set-Location C:\medical-report-annotation\backend
@"
DATABASE_URL=postgresql+psycopg2://meduser:这里换成你的数据库密码@127.0.0.1:5432/med_anno
SECRET_KEY=$SECRET
ACCESS_TOKEN_EXPIRE_MINUTES=1440
"@ | Set-Content -Encoding ASCII .env
```

### 6.3 手工启动后端做第一次验证

```powershell
Set-Location C:\medical-report-annotation\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

如果启动成功，通常会看到类似：

```text
Uvicorn running on http://127.0.0.1:8000
```

不要关掉这个窗口，再新开一个 PowerShell：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health | Select-Object -ExpandProperty Content
```

正常应返回：

```json
{"ok":true}
```

如果 `/api/health` 不通，先停下来排后端问题，不要继续配前端和 Nginx。

## 7. 创建初始管理员账号

第一次部署必须手动创建管理员。

新开一个 PowerShell：

```powershell
Set-Location C:\medical-report-annotation\backend
.\.venv\Scripts\python.exe .\scripts\init_admin.py
```

按提示输入：

- 管理员用户名
- 管理员密码
- 确认密码

成功后会看到：

```text
Initial admin created successfully: 'admin'
```

## 8. 构建前端

这台公司 Windows 已经有 `node/npm`，所以直接本机构建即可。

```powershell
Set-Location C:\medical-report-annotation\frontend
npm ci
npm run build
```

验证构建结果：

```powershell
Test-Path C:\medical-report-annotation\frontend\dist\index.html
```

如果返回 `True`，说明前端构建成功。

如果 `npm ci` 因锁文件问题失败，可以临时改用：

```powershell
npm install
npm run build
```

## 9. 安装并配置 Nginx

### 9.1 解压 Nginx

把 Nginx Windows 版解压到：

```text
C:\nginx
```

### 9.2 覆盖 `nginx.conf`

把 `C:\nginx\conf\nginx.conf` 改成下面内容：

```nginx
worker_processes  1;

events {
    worker_connections  1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout  65;

    server {
        listen       80;
        server_name  _;

        client_max_body_size 100m;

        location / {
            root   C:/medical-report-annotation/frontend/dist;
            index  index.html;
            try_files $uri $uri/ /index.html;
        }

        location /api/ {
            proxy_pass http://127.0.0.1:8000/api/;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
            proxy_connect_timeout 300s;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }
    }
}
```

### 9.3 测试并启动 Nginx

```powershell
Set-Location C:\nginx
.\nginx.exe -t
.\nginx.exe
```

重载命令：

```powershell
.\nginx.exe -s reload
```

停止命令：

```powershell
.\nginx.exe -s stop
```

## 10. 第一次完整联调

现在需要同时保证：

1. 后端 `uvicorn` 窗口仍在运行
2. Nginx 已启动

浏览器访问：

```text
http://localhost/
```

正常结果：

1. 能打开登录页
2. 能使用管理员账号登录
3. 页面内 API 请求不报 502

## 11. 开放防火墙端口

如果要让同网段其他机器访问这台公司 Windows，使用管理员权限 PowerShell：

```powershell
New-NetFirewallRule -DisplayName "Medical Report Annotation HTTP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80
```

建议只开放 `80`，不要对外开放 `5432` 和 `8000`。

查看本机 IP：

```powershell
ipconfig
```

其他机器访问：

```text
http://这台公司Windows的IP/
```

## 12. 注册 Windows 服务

前面是手工启动，适合第一次调试。

一旦你确认已经跑通，建议马上注册 Windows 服务。

### 12.1 注册后端服务

假设 `nssm.exe` 位于 `C:\nssm\nssm.exe`：

```powershell
& "C:\nssm\nssm.exe" install MedicalReportBackend "C:\medical-report-annotation\backend\.venv\Scripts\python.exe"
& "C:\nssm\nssm.exe" set MedicalReportBackend AppDirectory "C:\medical-report-annotation\backend"
& "C:\nssm\nssm.exe" set MedicalReportBackend AppParameters "-m uvicorn app.main:app --host 127.0.0.1 --port 8000"
& "C:\nssm\nssm.exe" set MedicalReportBackend AppStdout "C:\medical-report-annotation\logs\backend.out.log"
& "C:\nssm\nssm.exe" set MedicalReportBackend AppStderr "C:\medical-report-annotation\logs\backend.err.log"
& "C:\nssm\nssm.exe" set MedicalReportBackend Start SERVICE_AUTO_START
& "C:\nssm\nssm.exe" start MedicalReportBackend
```

### 12.2 注册 Nginx 服务

```powershell
& "C:\nssm\nssm.exe" install MedicalReportNginx "C:\nginx\nginx.exe"
& "C:\nssm\nssm.exe" set MedicalReportNginx AppDirectory "C:\nginx"
& "C:\nssm\nssm.exe" set MedicalReportNginx AppStdout "C:\medical-report-annotation\logs\nginx.out.log"
& "C:\nssm\nssm.exe" set MedicalReportNginx AppStderr "C:\medical-report-annotation\logs\nginx.err.log"
& "C:\nssm\nssm.exe" set MedicalReportNginx Start SERVICE_AUTO_START
& "C:\nssm\nssm.exe" start MedicalReportNginx
```

### 12.3 查看服务状态

```powershell
Get-Service MedicalReportBackend
Get-Service MedicalReportNginx
```

## 13. 后续更新代码怎么做

以后你在这台公司 Windows 更新部署时，按下面顺序：

### 13.1 拉最新代码

```powershell
Set-Location C:\medical-report-annotation
git pull origin master
```

如果你部署的不是 `master`，改成实际分支。

### 13.2 更新后端依赖

```powershell
Set-Location C:\medical-report-annotation\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 13.3 重新构建前端

```powershell
Set-Location C:\medical-report-annotation\frontend
npm ci
npm run build
```

### 13.4 重启服务

```powershell
Restart-Service MedicalReportBackend
Restart-Service MedicalReportNginx
```

## 14. 最小验收清单

部署完成后，至少检查：

1. `http://127.0.0.1:8000/api/health` 返回 `{"ok":true}`
2. `http://localhost/` 能打开登录页
3. 管理员账号可以登录
4. 页面操作不报 502
5. 能创建医生账号
6. 能导入一份测试报告

## 15. 常见问题

### 15.1 登录页能打开，但登录时报 502

通常说明 Nginx 正常、前端正常，但后端没有正常启动。

排查：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health
Get-Content C:\medical-report-annotation\logs\backend.err.log -Tail 100
```

### 15.2 后端健康检查正常，但首页打不开

通常说明 Nginx 没起来，或者 Nginx 的 `root` 路径写错。

排查：

```powershell
Get-Content C:\nginx\logs\error.log -Tail 100
Test-Path C:\medical-report-annotation\frontend\dist\index.html
```

### 15.3 账号密码一直错误

优先确认：

1. 你是否执行过 `scripts\init_admin.py`
2. 你登录的是第一次初始化创建的管理员账号
3. `.env` 里的数据库是否指向了你刚创建的那个库
