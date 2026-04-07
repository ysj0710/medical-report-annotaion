# 医疗影像报告标注系统 - 医院离线部署文档

> 适用场景：医院内网环境，无互联网，使用公司部署好的环境打包离线安装

---

## 一、在医院部署前的准备工作（在公司电脑完成）

### 1.1 确认公司电脑已完成部署

确保已按照《公司 Windows 部署文档》完成以下步骤：
- ✅ PostgreSQL 安装并运行
- ✅ 后端依赖已安装（venv 中有所有包）
- ✅ 前端已构建（dist 文件夹存在）
- ✅ 管理员账号已创建
- ✅ 系统可以正常运行

### 1.2 下载离线依赖包（wheel 文件）

由于你的电脑是 macOS，无法直接下载 Windows 的 wheel 文件，需要在公司 Windows 电脑上执行：

#### 1.2.1 在公司 Windows 电脑打开 CMD

```cmd
cd C:\projects\medical-report-annotation\backend
venv\Scripts\activate
```

#### 1.2.2 下载所有依赖的 wheel 文件

```cmd
mkdir C:\hospital-deploy\wheels
pip download -r requirements.txt -d C:\hospital-deploy\wheels --platform win_amd64 --only-binary=:all:
```

**注意**：如果某些包没有 Windows 二进制版本，会报错。这时需要去掉 `--only-binary=:all:`：

```cmd
pip download -r requirements.txt -d C:\hospital-deploy\wheels --platform win_amd64
```

#### 1.2.3 额外下载必要的包

```cmd
pip download uvicorn -d C:\hospital-deploy\wheels --platform win_amd64
```

### 1.3 打包后端代码

在公司 Windows 电脑上：

```cmd
cd C:\projects
tar -czf C:\hospital-deploy\backend.tar.gz medical-report-annotation\backend\app medical-report-annotation\backend\scripts medical-report-annotation\backend\requirements.txt
```

或者使用 7-Zip：
1. 右键点击 `C:\projects\medical-report-annotation\backend` 文件夹
2. 选择 "7-Zip" → "添加到压缩包"
3. 压缩包名称：`backend`
4. 压缩格式：`tar`
5. 压缩等级：`仅存储`（速度最快）

### 1.4 打包前端文件

前端已经构建好了，直接打包 dist 文件夹：

```cmd
cd C:\projects\medical-report-annotation\frontend
tar -czf C:\hospital-deploy\frontend-dist.tar.gz dist
```

或者使用 7-Zip 压缩 `dist` 文件夹。

### 1.5 准备 PostgreSQL 安装包

从官网下载以下文件，放到 `C:\hospital-deploy\`：

1. PostgreSQL 安装包：
   - 下载地址：https://www.postgresql.org/download/windows/
   - 文件名类似：`postgresql-15.4-1-windows-x64.exe`

2. Python 安装包：
   - 下载地址：https://www.python.org/downloads/
   - 文件名类似：`python-3.11.5-amd64.exe`

### 1.6 准备部署脚本

在公司 Windows 电脑上创建以下文件：

#### 文件 1：创建数据库.sql

在 `C:\hospital-deploy\` 下创建文件 `init-database.sql`，内容：

```sql
-- 创建数据库
CREATE DATABASE med_anno;

-- 创建用户
CREATE USER meduser WITH PASSWORD 'meduser123';

-- 授权
GRANT ALL PRIVILEGES ON DATABASE med_anno TO meduser;
```

#### 文件 2：后端配置文件 .env

在 `C:\hospital-deploy\` 下创建文件 `.env`，内容：

```env
DATABASE_URL=postgresql+psycopg2://meduser:meduser123@localhost:5432/med_anno
SECRET_KEY=hospital-deployment-secret-key-change-this
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

#### 文件 3：启动脚本 start-backend.bat

在 `C:\hospital-deploy\` 下创建文件 `start-backend.bat`，内容：

```batch
@echo off
cd /d C:\medical-annotation\backend
call venv\Scripts\activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
echo.
echo Backend stopped. Press any key to exit...
pause > nul
```

#### 文件 4：启动脚本 start-frontend.bat

在 `C:\hospital-deploy\` 下创建文件 `start-frontend.bat`，内容：

```batch
@echo off
cd /d C:\medical-annotation\frontend\dist
python -m http.server 80
echo.
echo Frontend stopped. Press any key to exit...
pause > nul
```

#### 文件 5：创建管理员脚本 create-admin.bat

在 `C:\hospital-deploy\` 下创建文件 `create-admin.bat`，内容：

```batch
@echo off
cd /d C:\medical-annotation\backend
call venv\Scripts\activate
echo.
echo ========================================
echo  创建初始管理员账号
echo ========================================
echo.
python scripts\init_admin.py
echo.
pause
```

### 1.7 准备安装说明文档

在 `C:\hospital-deploy\` 下创建文件 `安装说明.txt`，内容如下：

```
医疗影像报告标注系统 - 离线安装说明
=====================================

第一步：安装 PostgreSQL
----------------------
1. 双击 postgresql-15.4-1-windows-x64.exe
2. 安装过程中：
   - 密码设置为：postgres123
   - 其他保持默认
3. 安装完成后确认服务正在运行

第二步：安装 Python
------------------
1. 双击 python-3.11.5-amd64.exe
2. 勾选 "Add Python to PATH"
3. 点击 Install Now

第三步：创建数据库
-----------------
方法一（推荐）：使用 pgAdmin
1. 开始菜单打开 pgAdmin 4
2. 连接到 PostgreSQL 15
3. 密码：postgres123
4. 打开 Query Tool
5. 打开 init-database.sql 文件
6. 点击执行

方法二：使用命令行
1. 打开 SQL Shell (psql)
2. 输入密码 postgres123
3. 粘贴 init-database.sql 的内容执行

第四步：解压后端代码
-------------------
1. 将 backend.tar.gz 解压到 C:\medical-annotation\
2. 目录结构应该是：
   C:\medical-annotation\backend\
       ├─ app\
       ├─ scripts\
       └─ requirements.txt

第五步：安装后端依赖
-------------------
1. 打开 CMD
2. cd C:\medical-annotation\backend
3. python -m venv venv
4. venv\Scripts\activate
5. pip install --no-index --find-links=C:\hospital-deploy\wheels -r requirements.txt
6. pip install --no-index --find-links=C:\hospital-deploy\wheels uvicorn

第六步：配置文件
--------------
将 .env 文件复制到 C:\medical-annotation\backend\

第七步：创建管理员账号
--------------------
双击运行 create-admin.bat
按提示输入管理员用户名和密码

第八步：解压前端
--------------
将 frontend-dist.tar.gz 解压到 C:\medical-annotation\
目录结构：C:\medical-annotation\dist\

第九步：启动系统
--------------
1. 双击 start-backend.bat（保持运行）
2. 双击 start-frontend.bat（保持运行）
3. 浏览器访问 http://localhost/

日常启动
--------
每次使用前同时运行：
- start-backend.bat
- start-frontend.bat
```

### 1.8 整理部署包

将以下文件整理到 U 盘或移动硬盘：

```
U:\hospital-deploy\
    ├─ postgresql-15.4-1-windows-x64.exe    <- PostgreSQL 安装包
    ├─ python-3.11.5-amd64.exe              <- Python 安装包
    ├─ backend.tar.gz                       <- 后端代码
    ├─ frontend-dist.tar.gz                 <- 前端文件
    ├─ wheels\                              <- 依赖包目录
    │   ├─ xxx.whl
    │   └─ ...
    ├─ init-database.sql                    <- 数据库初始化脚本
    ├─ .env                                 <- 后端配置文件
    ├─ start-backend.bat                    <- 后端启动脚本
    ├─ start-frontend.bat                   <- 前端启动脚本
    ├─ create-admin.bat                     <- 管理员创建脚本
    └─ 安装说明.txt                          <- 安装说明文档
```

---

## 二、医院现场部署步骤

将 U 盘插入医院电脑，按以下步骤操作。

### 2.1 安装 PostgreSQL

1. 双击运行 `postgresql-15.4-1-windows-x64.exe`
2. 点击 "Next"
3. 安装目录：保持默认
4. 选择组件：保持默认（全部勾选）
5. 数据目录：保持默认
6. **密码**：输入 `postgres123`
7. 端口：保持默认 5432
8. 一路 Next，等待安装完成
9. 取消勾选 "Launch Stack Builder"，点击 "Finish"

### 2.2 验证 PostgreSQL 服务

1. 按 `Win + R`，输入 `services.msc`，回车
2. 找到 `postgresql-x64-15`
3. 确认状态是 "正在运行"

### 2.3 安装 Python

1. 双击运行 `python-3.11.5-amd64.exe`
2. **重要**：勾选 "Add Python to PATH"（底部复选框）
3. 点击 "Install Now"
4. 等待安装完成，点击 "Close"

### 2.4 验证 Python 安装

打开 CMD：
```cmd
python --version
```

显示 `Python 3.11.5` 表示安装成功。

### 2.5 创建数据库

#### 方式一：使用 pgAdmin（推荐）

1. 开始菜单搜索 "pgAdmin 4"，打开
2. 点击 "Servers" → "PostgreSQL 15"
3. 输入密码 `postgres123`
4. 点击上方工具栏的 "Query Tool"（查询工具）图标
5. 点击 "打开文件" 图标，选择 `init-database.sql`
6. 点击 "执行" 按钮（闪电图标）

#### 方式二：使用 SQL Shell

1. 开始菜单搜索 "SQL Shell (psql)"，打开
2. 一路回车，直到提示密码
3. 输入密码 `postgres123`
4. 复制粘贴 `init-database.sql` 的内容
5. 输入 `\q` 退出

### 2.6 解压后端代码

将 `backend.tar.gz` 解压到 `C:\medical-annotation\`：

**使用 7-Zip**：
1. 右键点击 `backend.tar.gz`
2. 选择 "7-Zip" → "提取文件..."
3. 提取到：`C:\medical-annotation\`

**或使用 Windows 自带 tar**：
```cmd
cd C:\
tar -xzf U:\hospital-deploy\backend.tar.gz
```

目录结构应该为：
```
C:\medical-annotation\backend\
    ├─ app\
    ├─ scripts\
    └─ requirements.txt
```

### 2.7 创建虚拟环境并安装依赖

打开 CMD：

```cmd
cd C:\medical-annotation\backend

:: 创建虚拟环境
python -m venv venv

:: 激活虚拟环境
venv\Scripts\activate
```

安装依赖（离线安装）：

```cmd
:: 安装 requirements.txt 中的依赖
pip install --no-index --find-links=U:\hospital-deploy\wheels -r requirements.txt

:: 安装 uvicorn
pip install --no-index --find-links=U:\hospital-deploy\wheels uvicorn
```

**说明**：`--no-index` 表示不从网络下载，`--find-links` 指定本地 wheel 文件位置。

### 2.8 复制配置文件

将 U 盘中的 `.env` 文件复制到后端目录：

```cmd
copy U:\hospital-deploy\.env C:\medical-annotation\backend\
```

### 2.9 创建管理员账号

双击运行 U 盘中的 `create-admin.bat`：

```
Admin username: admin
Admin password: （输入密码，不显示）
Confirm password: （再次输入）
```

看到 `Initial admin created successfully` 表示成功。

**记住这个密码！**

### 2.10 解压前端文件

将 `frontend-dist.tar.gz` 解压到 `C:\medical-annotation\`：

使用 7-Zip 或命令行：
```cmd
cd C:\medical-annotation
tar -xzf U:\hospital-deploy\frontend-dist.tar.gz
```

目录结构：
```
C:\medical-annotation\dist\
    ├─ index.html
    └─ assets\
```

### 2.11 启动系统

#### 启动后端

双击运行 U 盘中的 `start-backend.bat`

或者手动打开 CMD：
```cmd
cd C:\medical-annotation\backend
venv\Scripts\activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

保持窗口运行。

#### 启动前端

双击运行 U 盘中的 `start-frontend.bat`

或者手动打开 CMD：
```cmd
cd C:\medical-annotation\dist
python -m http.server 80
```

保持窗口运行。

#### 访问系统

打开浏览器，访问：
```
http://localhost/
```

使用创建的管理员账号登录。

---

## 三、配置防火墙（让医生可以访问）

如果医生需要通过局域网访问：

### 3.1 开放端口

以管理员身份运行 CMD：

```cmd
netsh advfirewall firewall add rule name="Medical Annotation HTTP" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="Medical Annotation API" dir=in action=allow protocol=TCP localport=8000
```

### 3.2 获取服务器 IP

```cmd
ipconfig
```

找到 "IPv4 地址"，如 `192.168.1.100`。

### 3.3 医生访问

医生在浏览器输入：
```
http://192.168.1.100/
```

---

## 四、日常使用

### 4.1 启动系统

每天使用前，需要启动两个服务：

1. 双击 `C:\medical-annotation\start-backend.bat`
2. 双击 `C:\medical-annotation\start-frontend.bat`

保持两个窗口运行，不要关闭。

### 4.2 停止系统

直接关闭两个 CMD 窗口。

### 4.3 数据备份

#### 使用 pgAdmin 备份

1. 打开 pgAdmin 4
2. 右键点击 `med_anno` 数据库 → "Backup..."
3. 选择保存位置，文件名如 `backup_20240101`
4. Format: "Custom"
5. 点击 "Backup"

#### 使用命令行备份

```cmd
"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe" -h localhost -U meduser -d med_anno -F c -f "C:\backup\med_anno_backup.dump"
```

密码：`meduser123`

---

## 五、常见问题

### Q1: pip 安装提示 "找不到满足的版本"

**原因**：wheel 文件不完整

**解决**：
1. 回到公司电脑
2. 重新执行 `pip download`，确保所有依赖都下载了
3. 特别注意检查 `psycopg2-binary` 是否下载成功

### Q2: 提示 "不是有效的 Win32 应用程序"

**原因**：下载的 wheel 文件架构不匹配（可能是 Linux 或 macOS 版本）

**解决**：
1. 确保使用 `--platform win_amd64` 参数下载
2. 重新下载 wheel 文件

### Q3: 数据库连接失败

**检查**：
1. PostgreSQL 服务是否运行（services.msc）
2. `.env` 文件中的密码是否正确
3. 数据库 `med_anno` 和用户 `meduser` 是否创建

### Q4: 无法从其他电脑访问

**检查**：
1. 防火墙是否开放 80 和 8000 端口
2. 后端启动时是否使用了 `--host 127.0.0.1`（改为 `--host 0.0.0.0` 允许外部访问）
3. IP 地址是否正确

修改后端启动命令（允许局域网访问）：
```cmd
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 六、部署清单

部署前确认 U 盘中有：

- [ ] postgresql-15.4-1-windows-x64.exe
- [ ] python-3.11.5-amd64.exe
- [ ] backend.tar.gz
- [ ] frontend-dist.tar.gz
- [ ] wheels/ 文件夹（包含所有依赖）
- [ ] init-database.sql
- [ ] .env
- [ ] start-backend.bat
- [ ] start-frontend.bat
- [ ] create-admin.bat
- [ ] 安装说明.txt

部署后确认：

- [ ] PostgreSQL 服务运行正常
- [ ] 数据库 `med_anno` 已创建
- [ ] 用户 `meduser` 已创建并有权限
- [ ] 后端依赖安装完成
- [ ] 管理员账号已创建
- [ ] 前端文件已解压
- [ ] 系统可以正常访问
- [ ] 医生可以正常登录和标注

---

**文档版本**: v1.0  
**适用场景**: 医院内网离线部署  
**最后更新**: 2026-04-02
