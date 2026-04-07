# 医疗影像报告标注系统 - 公司 Windows 部署文档

> 适用场景：在公司 Windows 电脑上部署测试，电脑已联网，已安装基础软件

---

## 一、前置条件确认

在开始部署前，请确认以下软件已安装：

| 软件 | 验证命令 | 如果未安装 |
|-----|---------|-----------|
| Git | `git --version` | https://git-scm.com/download/win |
| Python 3.11+ | `python --version` | https://www.python.org/downloads/ |
| Node.js 18+ | `node --version` | https://nodejs.org/ |
| npm | `npm --version` | 随 Node.js 安装 |

验证方法：按 `Win + R`，输入 `cmd` 回车，然后输入上表中的验证命令。

---

## 二、克隆代码

### 2.1 创建项目目录

```cmd
mkdir C:\projects
cd C:\projects
```

### 2.2 克隆代码仓库

```cmd
git clone https://github.com/your-username/medical-report-annotation.git
```

**注意**：将 `your-username` 替换为实际的 GitHub 用户名或仓库地址。

如果仓库是私有的，会提示输入用户名和密码（或 Token）。

### 2.3 进入项目目录

```cmd
cd medical-report-annotation
```

目录结构应该如下：
```
C:\projects\medical-report-annotation\
    ├─ backend\
    ├─ frontend\
    ├─ docs\
    └─ README.md
```

---

## 三、安装和配置 PostgreSQL

### 3.1 下载 PostgreSQL

1. 打开浏览器访问：https://www.postgresql.org/download/windows/
2. 点击 "Download the installer"
3. 下载 **PostgreSQL 15.4**（64-bit）

### 3.2 安装 PostgreSQL

1. 双击下载的安装包（如 `postgresql-15.4-1-windows-x64.exe`）
2. 点击 "Next"
3. 安装目录：保持默认 `C:\Program Files\PostgreSQL\15`，点击 "Next"
4. 选择组件：保持默认（全部勾选），点击 "Next"
5. 数据目录：保持默认，点击 "Next"
6. **密码设置**：输入 `postgres123`（记住这个密码，后续会用到）
7. 端口：保持默认 `5432`，点击 "Next"
8. 高级选项：保持默认，点击 "Next"
9. 预安装摘要：点击 "Next"
10. 等待安装完成
11. 完成时，取消勾选 "Launch Stack Builder at exit"，点击 "Finish"

### 3.3 验证 PostgreSQL 服务

1. 按 `Win + R`，输入 `services.msc`，回车
2. 在服务列表中找到 `postgresql-x64-15`
3. 确认 "状态" 列显示 "正在运行"
4. 确认 "启动类型" 为 "自动"

如果未运行，右键点击该服务，选择 "启动"。

### 3.4 创建数据库

使用 pgAdmin（PostgreSQL 自带的图形管理工具）：

1. 在开始菜单搜索 "pgAdmin 4"，点击打开
2. 在左侧树形菜单，点击 "Servers" 展开
3. 双击 "PostgreSQL 15"
4. 弹出密码框，输入安装时设置的密码 `postgres123`，勾选 "Save Password"，点击 "OK"

#### 创建数据库

1. 右键点击 "Databases" → "Create" → "Database..."
2. 在弹出的对话框中：
   - Database: 输入 `med_anno`
3. 点击 "Save"

#### 创建用户

1. 右键点击 "Login/Group Roles" → "Create" → "Login/Group Role..."
2. 在 "General" 标签页：
   - Name: 输入 `meduser`
3. 切换到 "Definition" 标签页：
   - Password: 输入 `meduser123`
   - Confirm password: 再次输入 `meduser123`
4. 切换到 "Privileges" 标签页：
   - 开启 "Can login?" 开关
5. 点击 "Save"

#### 授权

1. 在左侧找到并右键点击 `med_anno` 数据库
2. 选择 "Properties"
3. 切换到 "Security" 标签页
4. 点击 "+" 按钮（Privileges 右侧）
5. 在弹出的对话框中：
   - Grantee: 选择 `meduser`
   - Privileges: 勾选所有选项（或至少勾选 CONNECT、TEMPORARY、CREATE）
6. 点击 "Save"
7. 再次点击 "Save" 关闭属性窗口

---

## 四、后端部署

### 4.1 进入后端目录

```cmd
cd C:\projects\medical-report-annotation\backend
```

### 4.2 创建 Python 虚拟环境

```cmd
python -m venv venv
```

等待命令执行完成，会创建一个 `venv` 文件夹。

### 4.3 激活虚拟环境

```cmd
venv\Scripts\activate
```

**成功标志**：命令行前面出现 `(venv)`，例如：
```
(venv) C:\projects\medical-report-annotation\backend>
```

### 4.4 安装依赖

确保虚拟环境已激活（有 `(venv)` 前缀）：

```cmd
pip install --upgrade pip
pip install -r requirements.txt
```

等待安装完成，这可能需要几分钟。

### 4.5 创建环境变量文件

在 `C:\projects\medical-report-annotation\backend` 目录下创建 `.env` 文件：

**方法一：使用记事本**
1. 打开记事本
2. 输入以下内容：
```env
DATABASE_URL=postgresql+psycopg2://meduser:meduser123@localhost:5432/med_anno
SECRET_KEY=your-secret-key-change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```
3. 点击 "文件" → "另存为"
4. 文件名输入：`.env`（注意前面有个点）
5. 保存类型选择："所有文件 (*.*)"
6. 编码选择："UTF-8"
7. 点击 "保存"

**方法二：使用命令行**
```cmd
(
echo DATABASE_URL=postgresql+psycopg2://meduser:meduser123@localhost:5432/med_anno
echo SECRET_KEY=your-secret-key-change-this-in-production
echo ACCESS_TOKEN_EXPIRE_MINUTES=1440
) > .env
```

### 4.6 测试后端启动

在虚拟环境中执行：

```cmd
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**成功标志**：
```
INFO:     Will watch for changes in these directories: ['C:\\projects\\medical-report-annotation\\backend']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**验证**：打开浏览器访问 http://127.0.0.1:8000/docs，应该能看到 API 文档（Swagger UI）。

按 `Ctrl + C` 停止服务，继续下一步。

---

## 五、初始化管理员账号

**重要**：必须先创建管理员账号，否则无法登录系统！

### 5.1 执行初始化脚本

确保在虚拟环境中（有 `(venv)` 前缀）：

```cmd
cd C:\projects\medical-report-annotation\backend
python scripts\init_admin.py
```

### 5.2 输入管理员信息

脚本会提示输入：

```
Admin username: admin
Admin password:
Confirm password:
```

操作步骤：
1. 输入用户名：`admin`，按回车
2. 输入密码：`admin123`（输入时不会显示任何字符），按回车
3. 确认密码：再次输入 `admin123`（同样不会显示），按回车

**成功标志**：
```
Initial admin created successfully: 'admin'
```

**请牢记这个账号和密码！**

### 5.3 脚本安全特性说明

- 检查用户名是否已存在
- 检查是否已有活跃管理员（防止重复创建）
- 密码使用 bcrypt 加密存储
- 创建的管理员自动拥有 `can_view_all=True`（可查看所有报告）

---

## 六、前端部署

### 6.1 进入前端目录

打开一个新的 CMD 窗口（不要关闭后端的窗口）：

```cmd
cd C:\projects\medical-report-annotation\frontend
```

### 6.2 安装前端依赖

```cmd
npm install
```

等待安装完成，这可能需要几分钟。

### 6.3 构建前端

```cmd
npm run build
```

**成功标志**：
```
dist/                     0.05 kB │ gzip: 0.07 kB
dist/assets/...           x.x kB │ gzip: x.x kB
✓ built in x.xxs
```

构建完成后，会在 `frontend` 目录下生成 `dist` 文件夹。

### 6.4 验证构建结果

```cmd
dir dist
```

应该包含：
- `index.html`
- `assets/` 文件夹

---

## 七、启动完整系统

### 7.1 启动后端服务

在第一个 CMD 窗口（虚拟环境）：

```cmd
cd C:\projects\medical-report-annotation\backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

保持窗口运行。

### 7.2 启动前端服务

在第二个 CMD 窗口：

```cmd
cd C:\projects\medical-report-annotation\frontend
cd dist
python -m http.server 80
```

或者使用 npx serve：
```cmd
npx serve dist -l 80
```

保持窗口运行。

### 7.3 访问系统

打开浏览器：

- **本机访问**：http://localhost/
- **API 文档**：http://127.0.0.1:8000/docs

### 7.4 登录测试

1. 在浏览器打开 http://localhost/
2. 输入用户名：`admin`
3. 输入密码：`admin123`（第五步设置的密码）
4. 点击登录

---

## 八、配置防火墙（局域网访问）

如果其他电脑需要访问，需要开放 80 端口：

### 8.1 图形界面方式

1. 打开 "控制面板" → "系统和安全" → "Windows Defender 防火墙"
2. 点击左侧 "高级设置"
3. 点击左侧 "入站规则"，右侧点击 "新建规则"
4. 选择 "端口"，点击 "下一步"
5. 选择 "TCP"，输入 `80`，点击 "下一步"
6. 选择 "允许连接"，点击 "下一步"
7. 勾选 "域"、"专用"、"公用"，点击 "下一步"
8. 名称输入 `Medical Annotation HTTP`，点击 "完成"

重复上述步骤，再添加 8000 端口（后端 API 端口）。

### 8.2 命令行方式（管理员权限）

以管理员身份运行 CMD：

```cmd
netsh advfirewall firewall add rule name="Medical Annotation HTTP" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="Medical Annotation API" dir=in action=allow protocol=TCP localport=8000
```

### 8.3 获取本机 IP

```cmd
ipconfig
```

找到 "IPv4 地址"，例如 `192.168.1.100`。

其他电脑可以通过 http://192.168.1.100/ 访问。

---

## 九、日常使用

### 9.1 启动系统

每次使用前，需要启动两个服务：

**窗口 1 - 后端：**
```cmd
cd C:\projects\medical-report-annotation\backend
venv\Scripts\activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**窗口 2 - 前端：**
```cmd
cd C:\projects\medical-report-annotation\frontend\dist
python -m http.server 80
```

### 9.2 停止系统

直接关闭两个 CMD 窗口，或者在窗口中按 `Ctrl + C`。

### 9.3 开发模式（热重载）

如果需要修改代码：

**后端开发模式**：
```cmd
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**前端开发模式**：
```cmd
cd C:\projects\medical-report-annotation\frontend
npm run dev
```

---

## 十、数据库备份

### 10.1 使用 pgAdmin 备份

1. 打开 pgAdmin 4
2. 右键点击 `med_anno` 数据库 → "Backup..."
3. Filename: 选择保存位置，输入文件名如 `backup_20240101`
4. Format: 选择 "Custom"
5. 点击 "Backup"

### 10.2 使用命令行备份

```cmd
"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe" -h localhost -U meduser -d med_anno -F c -f "C:\backup\med_anno_backup.dump"
```

会提示输入密码：`meduser123`

### 10.3 恢复备份

```cmd
"C:\Program Files\PostgreSQL\15\bin\pg_restore.exe" -h localhost -U meduser -d med_anno "C:\backup\med_anno_backup.dump"
```

---

## 十一、常见问题

### Q1: 提示 "pg_config executable not found"

**原因**：PostgreSQL 开发工具未安装

**解决**：
1. 重新运行 PostgreSQL 安装程序
2. 选择 "Modify"
3. 确保勾选 "Command Line Tools"
4. 完成安装

### Q2: 提示 "数据库连接失败"

**检查步骤**：
1. 确认 PostgreSQL 服务正在运行（services.msc）
2. 确认 `.env` 文件中的密码正确
3. 确认数据库 `med_anno` 和用户 `meduser` 已创建

### Q3: 提示 "端口 80 被占用"

**原因**：IIS 或其他程序占用了 80 端口

**解决**：改用其他端口
```cmd
cd C:\projects\medical-report-annotation\frontend\dist
python -m http.server 8080
```
然后访问 http://localhost:8080/

### Q4: 前端页面空白

**检查**：
1. 确认 `frontend/dist` 目录下有 `index.html`
2. 确认前端服务已启动
3. 清除浏览器缓存后刷新

### Q5: 无法登录，提示账号不存在

**解决**：重新执行管理员创建脚本
```cmd
cd C:\projects\medical-report-annotation\backend
venv\Scripts\activate
python scripts\init_admin.py
```

---

## 十二、下一步

完成本部署后，请参考第二份文档《医院离线部署文档》，将环境打包用于医院离线部署。

---

**文档版本**: v1.0  
**适用系统**: Windows 10/11  
**最后更新**: 2026-04-02
