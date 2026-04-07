# 医疗影像报告标注系统 医院 Windows 纯离线部署手册

这份文档建立在一个明确前提上：

- 你已经在公司 Windows 上按在线方式把系统部署成功
- 公司 Windows 可以联网，也已经装好 `git/node/npm/python`
- 医院 Windows 不能访问 GitHub / GitLab
- 医院 Windows 大概率也不能访问 PyPI / npm
- 你要利用“公司 Windows 的已部署环境”来产出完整离线包

所以本文分成两大部分：

1. 在公司 Windows 上准备离线部署包
2. 把离线包带到医院 Windows 上纯离线部署

## 第一部分：在公司 Windows 上准备离线部署包

## 1. 先确认公司 Windows 上的代码状态

建议先把公司 Windows 上的项目更新到你要给医院部署的最终版本。

```powershell
Set-Location C:\medical-report-annotation
git status
git pull origin master
git rev-parse HEAD
```

如果你不是用 `master`，改成实际分支。

把 `git rev-parse HEAD` 输出的 commit id 记下来，后面医院现场排查问题会很有用。

## 2. 在公司 Windows 上创建离线包目录

建议统一用这个目录：

```text
C:\medical-report-annotation-offline-kit
```

另建一个临时打包目录：

```text
C:\medical-report-annotation-offline-stage
```

执行：

```powershell
$KIT = "C:\medical-report-annotation-offline-kit"
$STAGE = "C:\medical-report-annotation-offline-stage"

Remove-Item $STAGE -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $KIT | Out-Null
New-Item -ItemType Directory -Force "$KIT\installers" | Out-Null
New-Item -ItemType Directory -Force "$KIT\app" | Out-Null
New-Item -ItemType Directory -Force "$KIT\python-wheels" | Out-Null
New-Item -ItemType Directory -Force "$KIT\templates" | Out-Null
New-Item -ItemType Directory -Force "$KIT\notes" | Out-Null
New-Item -ItemType Directory -Force $STAGE | Out-Null
```

## 3. 把医院机器需要的安装包准备好

医院机器离线部署时，建议带上这些安装包或压缩包：

1. Python 3.11 x64 安装包
2. PostgreSQL 15 x64 安装包
3. Nginx Windows zip 包
4. NSSM zip 包

把它们手动下载后放进：

```text
C:\medical-report-annotation-offline-kit\installers
```

建议文件结构类似：

```text
C:\medical-report-annotation-offline-kit\installers\python-3.11.x-amd64.exe
C:\medical-report-annotation-offline-kit\installers\postgresql-15.x-windows-x64.exe
C:\medical-report-annotation-offline-kit\installers\nginx-1.xx.x.zip
C:\medical-report-annotation-offline-kit\installers\nssm-2.24.zip
```

注意：

- 医院机器不需要 Git
- 医院机器不需要 Node.js
- 所以前面两者不用打进离线包

## 4. 用公司 Windows 重新构建前端

为了确保离线包和当前代码完全一致，先在公司 Windows 上重新构建一次前端：

```powershell
Set-Location C:\medical-report-annotation\frontend
npm ci
npm run build
```

验证构建结果：

```powershell
Test-Path C:\medical-report-annotation\frontend\dist\index.html
```

如果返回 `True`，继续下一步。

## 5. 用公司 Windows 下载医院离线安装要用的 Python wheel

这一步是整份离线流程里最关键的一步。  
因为你之前用 macOS 下载 Windows 依赖会失败，所以这里直接利用公司 Windows 来准备 wheel。

### 5.1 下载项目运行依赖

```powershell
Set-Location C:\medical-report-annotation
python -m pip download -r .\backend\requirements.txt -d "$KIT\python-wheels"
```

### 5.2 额外下载 `pip/setuptools/wheel`

这样医院机器在离线状态下也能升级或补齐基础打包工具：

```powershell
python -m pip download pip setuptools wheel -d "$KIT\python-wheels"
```

### 5.3 检查 wheel 目录

```powershell
Get-ChildItem "$KIT\python-wheels"
```

你应该能看到很多 `.whl` 文件。

重要说明：

- 因为这一步是在 Windows 上执行，所以拿到的是 Windows 可安装依赖
- 为了保证完全兼容，医院机器也请安装 Python 3.11 x64

## 6. 打包后端源码

医院机器不需要：

- `.git`
- `.venv`
- 本地缓存
- 日志

所以不要直接整仓库打包，而是只打后端运行所需内容。

### 6.1 复制后端到临时打包目录

```powershell
robocopy C:\medical-report-annotation\backend "$STAGE\backend" /E /XD .venv venv __pycache__ .pytest_cache
if ($LASTEXITCODE -gt 7) { throw "robocopy failed with code $LASTEXITCODE" }
```

### 6.2 压缩成 `backend.zip`

```powershell
Compress-Archive -Path "$STAGE\backend" -DestinationPath "$KIT\app\backend.zip" -Force
```

## 7. 打包前端构建产物

这里只打构建后的 `dist`，不给医院机器带前端源码。

```powershell
Compress-Archive -Path "C:\medical-report-annotation\frontend\dist\*" -DestinationPath "$KIT\app\frontend-dist.zip" -Force
```

## 8. 生成 Nginx 配置模板

在公司 Windows 上直接生成模板文件，后面医院机器直接复制使用：

```powershell
@"
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
            root   C:/medical-report-annotation/frontend-dist;
            index  index.html;
            try_files `$uri `$uri/ /index.html;
        }

        location /api/ {
            proxy_pass http://127.0.0.1:8000/api/;
            proxy_http_version 1.1;
            proxy_set_header Upgrade `$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host `$host;
            proxy_set_header X-Real-IP `$remote_addr;
            proxy_set_header X-Forwarded-For `$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto `$scheme;
            proxy_cache_bypass `$http_upgrade;
            proxy_connect_timeout 300s;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }
    }
}
"@ | Set-Content -Encoding ASCII "$KIT\templates\nginx.conf"
```

注意这里 PowerShell 里用了反引号转义 `$`，这是为了让生成出来的 `nginx.conf` 内容正确。

## 9. 记录版本信息

建议把本次离线包对应的代码版本写进文件：

```powershell
Set-Location C:\medical-report-annotation
git rev-parse HEAD | Set-Content -Encoding ASCII "$KIT\notes\commit.txt"
```

你也可以额外写一个说明文件，比如：

```powershell
@"
Project: medical-report-annotation
Build machine: company windows
Python target: 3.11 x64
Database target: PostgreSQL 15
"@ | Set-Content -Encoding ASCII "$KIT\notes\readme.txt"
```

## 10. 最后检查公司 Windows 产出的离线包

至少确认这些内容都存在：

```text
C:\medical-report-annotation-offline-kit\installers\
C:\medical-report-annotation-offline-kit\app\backend.zip
C:\medical-report-annotation-offline-kit\app\frontend-dist.zip
C:\medical-report-annotation-offline-kit\python-wheels\
C:\medical-report-annotation-offline-kit\templates\nginx.conf
C:\medical-report-annotation-offline-kit\notes\commit.txt
```

然后把整个：

```text
C:\medical-report-annotation-offline-kit
```

通过 U 盘、移动硬盘、内网文件摆渡等方式带到医院。

第二部分：在医院 Windows 上纯离线部署

## 11. 把离线包放到医院 Windows

假设你把整个离线包复制到了：

```text
C:\deploy-kit
```

后面文档都以这个目录为准。

## 12. 在医院 Windows 上安装基础软件

### 12.1 安装 Python

运行：

```text
C:\deploy-kit\installers\python-3.11.x-amd64.exe
```

安装时一定要：

1. 勾选 `Add python.exe to PATH`
2. 选择 Python 3.11 x64

安装后重新打开 PowerShell：

```powershell
python --version
```

### 12.2 安装 PostgreSQL

运行：

```text
C:\deploy-kit\installers\postgresql-15.x-windows-x64.exe
```

安装建议：

- 端口：`5432`
- 超级用户：`postgres`
- 记住你设置的 `postgres` 密码

### 12.3 解压 Nginx

把：

```text
C:\deploy-kit\installers\nginx-*.zip
```

解压到：

```text
C:\nginx
```

### 12.4 解压 NSSM

把：

```text
C:\deploy-kit\installers\nssm-*.zip
```

解压到：

```text
C:\nssm
```

确保存在：

```text
C:\nssm\nssm.exe
```

## 13. 解压应用文件

### 13.1 创建部署目录

```powershell
New-Item -ItemType Directory -Force C:\medical-report-annotation | Out-Null
New-Item -ItemType Directory -Force C:\medical-report-annotation\logs | Out-Null
```

### 13.2 解压后端和前端

```powershell
Expand-Archive -Path C:\deploy-kit\app\backend.zip -DestinationPath C:\medical-report-annotation -Force
Expand-Archive -Path C:\deploy-kit\app\frontend-dist.zip -DestinationPath C:\medical-report-annotation\frontend-dist -Force
```

最终要确认这两个路径存在：

```text
C:\medical-report-annotation\backend\requirements.txt
C:\medical-report-annotation\frontend-dist\index.html
```

如果你的解压结果多包了一层目录，请手工整理到这个结构。

## 14. 创建医院本地数据库

打开 PowerShell：

```powershell
& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -h 127.0.0.1 -d postgres
```

进入 `psql` 后执行：

```sql
CREATE USER meduser WITH PASSWORD '这里换成医院环境数据库密码';
CREATE DATABASE med_anno OWNER meduser;
\q
```

不要直接复制公司环境数据库密码，医院环境请单独设置。

## 15. 离线安装后端依赖

### 15.1 创建虚拟环境

```powershell
Set-Location C:\medical-report-annotation\backend
python -m venv .venv
```

### 15.2 先离线安装基础打包工具

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links C:\deploy-kit\python-wheels pip setuptools wheel
```

### 15.3 再离线安装项目依赖

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links C:\deploy-kit\python-wheels -r requirements.txt
```

如果这一步失败，优先检查：

1. 医院机器 Python 是否为 3.11 x64
2. `C:\deploy-kit\python-wheels` 是否完整
3. wheel 是否来自公司 Windows，而不是旧的 macOS 包

## 16. 创建医院环境的 `.env`

先生成医院环境专用的密钥：

```powershell
$SECRET = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
$SECRET
```

然后写 `.env`：

```powershell
Set-Location C:\medical-report-annotation\backend
@"
DATABASE_URL=postgresql+psycopg2://meduser:这里换成医院环境数据库密码@127.0.0.1:5432/med_anno
SECRET_KEY=$SECRET
ACCESS_TOKEN_EXPIRE_MINUTES=1440
"@ | Set-Content -Encoding ASCII .env
```

## 17. 手工启动后端验证

```powershell
Set-Location C:\medical-report-annotation\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

再开一个新 PowerShell：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health | Select-Object -ExpandProperty Content
```

正常应返回：

```json
{"ok":true}
```

## 18. 创建医院环境的初始管理员

新开一个 PowerShell：

```powershell
Set-Location C:\medical-report-annotation\backend
.\.venv\Scripts\python.exe .\scripts\init_admin.py
```

按提示输入医院环境管理员账号和密码。

## 19. 配置并启动 Nginx

```powershell
Copy-Item C:\deploy-kit\templates\nginx.conf C:\nginx\conf\nginx.conf -Force
Set-Location C:\nginx
.\nginx.exe -t
.\nginx.exe
```

## 20. 浏览器验证

此时确保：

1. 后端 `uvicorn` 窗口仍在运行
2. Nginx 已启动

浏览器访问：

```text
http://localhost/
```

正常应当：

1. 能打开登录页
2. 能用医院环境管理员账号登录

## 21. 开放防火墙端口

如果医院内网里其他终端需要访问，使用管理员权限 PowerShell：

```powershell
New-NetFirewallRule -DisplayName "Medical Report Annotation HTTP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80
```

建议只开放 `80`，不要开放 `5432` 和 `8000`。

## 22. 注册 Windows 服务

### 22.1 注册后端服务

```powershell
& "C:\nssm\nssm.exe" install MedicalReportBackend "C:\medical-report-annotation\backend\.venv\Scripts\python.exe"
& "C:\nssm\nssm.exe" set MedicalReportBackend AppDirectory "C:\medical-report-annotation\backend"
& "C:\nssm\nssm.exe" set MedicalReportBackend AppParameters "-m uvicorn app.main:app --host 127.0.0.1 --port 8000"
& "C:\nssm\nssm.exe" set MedicalReportBackend AppStdout "C:\medical-report-annotation\logs\backend.out.log"
& "C:\nssm\nssm.exe" set MedicalReportBackend AppStderr "C:\medical-report-annotation\logs\backend.err.log"
& "C:\nssm\nssm.exe" set MedicalReportBackend Start SERVICE_AUTO_START
& "C:\nssm\nssm.exe" start MedicalReportBackend
```

### 22.2 注册 Nginx 服务

```powershell
& "C:\nssm\nssm.exe" install MedicalReportNginx "C:\nginx\nginx.exe"
& "C:\nssm\nssm.exe" set MedicalReportNginx AppDirectory "C:\nginx"
& "C:\nssm\nssm.exe" set MedicalReportNginx AppStdout "C:\medical-report-annotation\logs\nginx.out.log"
& "C:\nssm\nssm.exe" set MedicalReportNginx AppStderr "C:\medical-report-annotation\logs\nginx.err.log"
& "C:\nssm\nssm.exe" set MedicalReportNginx Start SERVICE_AUTO_START
& "C:\nssm\nssm.exe" start MedicalReportNginx
```

### 22.3 查看服务状态

```powershell
Get-Service MedicalReportBackend
Get-Service MedicalReportNginx
```

## 23. 医院离线更新流程

后面如果要更新医院系统，推荐仍然沿用同样的离线方式：

1. 在公司 Windows `git pull`
2. 重新构建前端
3. 如有依赖变化，重新下载 wheel
4. 重新打 `backend.zip`
5. 重新打 `frontend-dist.zip`
6. 把新的离线包带到医院
7. 医院 Windows 停服务、覆盖文件、重启服务

医院机器上常用命令：

```powershell
Stop-Service MedicalReportBackend
Stop-Service MedicalReportNginx
```

替换完成后：

```powershell
Start-Service MedicalReportBackend
Start-Service MedicalReportNginx
```

## 24. 最小验收清单

医院离线部署完成后，至少检查：

1. `http://127.0.0.1:8000/api/health` 返回 `{"ok":true}`
2. `http://localhost/` 能打开登录页
3. 医院管理员账号能登录
4. 页面不报 502
5. 能创建医生账号
6. 能导入测试报告

## 25. 常见离线问题

### 25.1 离线安装依赖时报 wheel 不兼容

通常原因是：

1. wheel 不是在公司 Windows 上下载的
2. 医院机器 Python 版本和公司机器不一致

解决：

- 统一使用 Python 3.11 x64
- 重新在公司 Windows 上执行 `pip download`

### 25.2 首页能打开，但登录报 502

通常说明 Nginx 已经起来了，但后端没起来。

排查：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health
Get-Content C:\medical-report-annotation\logs\backend.err.log -Tail 100
```

### 25.3 后端健康检查正常，但首页打不开

通常是：

1. Nginx 没启动
2. `nginx.conf` 中 `root` 路径不对
3. `frontend-dist\index.html` 不存在

排查：

```powershell
Get-Content C:\nginx\logs\error.log -Tail 100
Test-Path C:\medical-report-annotation\frontend-dist\index.html
```

### 25.4 公司环境和医院环境密码能不能共用

不建议。

建议公司和医院：

1. 数据库密码分开
2. `.env` 分开
3. 管理员账号密码分开
