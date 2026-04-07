# 医疗影像报告标注系统 - 公司 Windows 部署文档（Miniconda 版）

> 适用场景：在公司 Windows 电脑上部署测试，使用 Miniconda 管理 Python 环境

---

## 一、前置条件确认

在开始部署前，请确认以下软件已安装：

| 软件 | 验证命令 | 如果未安装 |
|-----|---------|-----------|
| Git | `git --version` | https://git-scm.com/download/win |
| Node.js 18+ | `node --version` | https://nodejs.org/ |
| npm | `npm --version` | 随 Node.js 安装 |
| Miniconda | `conda --version` | https://docs.conda.io/en/latest/miniconda.html |

**注意**：本文档使用 Miniconda 替代原生 Python，避免依赖安装问题。

---

## 二、安装 Miniconda

### 2.1 下载 Miniconda

1. 打开浏览器访问：https://docs.conda.io/en/latest/miniconda.html
2. 下载 **Miniconda3 Windows 64-bit**（或最新版本）
   - 文件名类似：`Miniconda3-latest-Windows-x86_64.exe`

### 2.2 安装 Miniconda

1. 双击下载的安装包
2. 点击 "Next"
3. 许可协议：点击 "I Agree"
4. 安装类型：选择 **"Just Me (recommended)"**，点击 "Next"
5. 安装位置：保持默认（`C:\Users\你的用户名\miniconda3`），点击 "Next"
6. **重要选项**：
   - ✅ **勾选** "Add Miniconda3 to my PATH environment variable"
   - ✅ **勾选** "Register Miniconda3 as my default Python 3.x"
7. 点击 "Install"
8. 等待安装完成，点击 "Next"
9. 点击 "Finish"

### 2.3 验证安装

打开一个新的 CMD 窗口（注意：必须新开窗口才能读取环境变量）：

```cmd
conda --version
python --version
```

显示版本号表示安装成功。

### 2.4 配置 conda 镜像（推荐）

加速依赖下载：

```cmd
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free
conda config --set show_channel_urls yes
```

---

## 三、克隆代码

### 3.1 创建项目目录

```cmd
mkdir C:\projects
cd C:\projects
```

### 3.2 克隆代码仓库

```cmd
git clone https://github.com/your-username/medical-report-annotation.git
```

**注意**：将 `your-username` 替换为实际的 GitHub 用户名或仓库地址。

如果仓库是私有的，会提示输入用户名和密码（或 Token）。

### 3.3 进入项目目录

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

## 四、安装和配置 PostgreSQL

### 4.1 下载 PostgreSQL

1. 打开浏览器访问：https://www.postgresql.org/download/windows/
2. 点击 "Download the installer"
3. 下载 **PostgreSQL 15.x**（64-bit）

### 4.2 安装 PostgreSQL

1. 双击下载的安装包（如 `postgresql-15.4-1-windows-x64.exe`）
2. 点击 "Next"
3. 安装目录：保持默认（`C:\Program Files\PostgreSQL\15`），点击 "Next"
4. 选择组件：保持默认（全部勾选），点击 "Next"
5. 数据目录：保持默认，点击 "Next"
6. **密码设置**：输入 `postgres123`（记住这个密码，后续会用到）
7. 端口：保持默认 `5432`，点击 "Next"
8. 高级选项：保持默认，点击 "Next"
9. 预安装摘要：点击 "Next"
10. 等待安装完成
11. 完成时，取消勾选 "Launch Stack Builder at exit"，点击 "Finish"

### 4.3 验证 PostgreSQL 服务

1. 按 `Win + R`，输入 `services.msc`，回车
2. 在服务列表中找到 `postgresql-x64-15`
3. 确认 "状态" 列显示 "正在运行"
4. 确认 "启动类型" 为 "自动"

如果未运行，右键点击该服务，选择 "启动"。

### 4.4 创建数据库

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

## 五、后端部署（使用 Miniconda）

### 5.1 进入后端目录

```cmd
cd C:\projects\medical-report-annotation\backend
```

### 5.2 创建 Conda 环境

```cmd
conda create -n medanno python=3.11
```

等待创建完成，输入 `y` 确认安装。

### 5.3 激活 Conda 环境

```cmd
conda activate medanno
```

**成功标志**：命令行前面出现 `(medanno)`，例如：
```
(medanno) C:\projects\medical-report-annotation\backend>
```

### 5.4 安装依赖

确保环境已激活（有 `(medanno)` 前缀）：

**方式一：使用 conda 安装主要依赖（推荐）**

```cmd
conda install fastapi uvicorn sqlalchemy pydantic-settings -c conda-forge
conda install psycopg2 bcrypt -c conda-forge
```

**方式二：如果 conda 找不到某些包，使用 pip**

```cmd
pip install -r requirements.txt
```

或者混合安装（conda 优先，pip 补充）：
```cmd
conda install fastapi uvicorn sqlalchemy pydantic-settings python-jose passlib python-multipart -c conda-forge
conda install psycopg2 bcrypt pandas openpyxl -c conda-forge
pip install reportlab
```

### 5.5 验证安装

```cmd
python -c "import fastapi; import sqlalchemy; import psycopg2; print('All packages installed successfully!')"
```

没有报错表示安装成功。

### 5.6 创建环境变量文件

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

### 5.7 测试后端启动

在 conda 环境中执行：

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

## 六、初始化管理员账号

**重要**：必须先创建管理员账号，否则无法登录系统！

### 6.1 执行初始化脚本

确保在 conda 环境中（有 `(medanno)` 前缀）：

```cmd
cd C:\projects\medical-report-annotation\backend
python scripts\init_admin.py
```

### 6.2 输入管理员信息

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

---

## 七、前端部署

### 7.1 进入前端目录

打开一个新的 CMD 窗口（不要关闭后端的窗口）：

```cmd
cd C:\projects\medical-report-annotation\frontend
```

### 7.2 安装前端依赖

```cmd
npm install
```

等待安装完成，这可能需要几分钟。

### 7.3 构建前端

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

### 7.4 验证构建结果

```cmd
dir dist
```

应该包含：
- `index.html`
- `assets/` 文件夹

---

## 八、启动完整系统

### 8.1 启动后端服务

在第一个 CMD 窗口（conda 环境）：

```cmd
cd C:\projects\medical-report-annotation\backend
conda activate medanno
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

保持窗口运行。

### 8.2 启动前端服务

在第二个 CMD 窗口：

```cmd
cd C:\projects\medical-report-annotation\frontend\dist
python -m http.server 80
```

或者使用 npx serve：
```cmd
npx serve dist -l 80
```

保持窗口运行。

### 8.3 访问系统

打开浏览器：

- **本机访问**：http://localhost/
- **API 文档**：http://127.0.0.1:8000/docs

### 8.4 登录测试

1. 在浏览器打开 http://localhost/
2. 输入用户名：`admin`
3. 输入密码：`admin123`（第六步设置的密码）
4. 点击登录

---

## 九、配置防火墙（局域网访问）

如果其他电脑需要访问，需要开放 80 端口：

### 9.1 图形界面方式

1. 打开 "控制面板" → "系统和安全" → "Windows Defender 防火墙"
2. 点击左侧 "高级设置"
3. 点击左侧 "入站规则"，右侧点击 "新建规则"
4. 选择 "端口"，点击 "下一步"
5. 选择 "TCP"，输入 `80`，点击 "下一步"
6. 选择 "允许连接"，点击 "下一步"
7. 勾选 "域"、"专用"、"公用"，点击 "下一步"
8. 名称输入 `Medical Annotation HTTP`，点击 "完成"

重复上述步骤，再添加 8000 端口（后端 API 端口）。

### 9.2 命令行方式（管理员权限）

以管理员身份运行 CMD：

```cmd
netsh advfirewall firewall add rule name="Medical Annotation HTTP" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="Medical Annotation API" dir=in action=allow protocol=TCP localport=8000
```

### 9.3 获取本机 IP

```cmd
ipconfig
```

找到 "IPv4 地址"，例如 `192.168.1.100`。

其他电脑可以通过 http://192.168.1.100/ 访问。

---

## 十、Conda 环境管理

### 10.1 常用命令

```cmd
:: 查看所有环境
conda env list

:: 激活环境
conda activate medanno

:: 退出环境
conda deactivate

:: 删除环境（如果需要重新创建）
conda env remove -n medanno

:: 查看环境中已安装的包
conda list

:: 安装新包
conda install 包名 -c conda-forge

:: 更新包
conda update 包名
```

### 10.2 导出环境（用于离线部署）

导出环境配置：
```cmd
conda activate medanno
conda env export > environment.yml
```

导出 pip 依赖：
```cmd
pip freeze > requirements-freeze.txt
```

### 10.3 导出离线包（用于医院部署）

下载所有依赖到本地目录：
```cmd
conda activate medanno

:: 创建下载目录
mkdir C:\hospital-deploy\conda-packages
mkdir C:\hospital-deploy\pip-packages

:: 导出 conda 包列表
conda list --explicit > C:\hospital-deploy\conda-packages\package-list.txt

:: 下载 pip 依赖
pip download -r requirements.txt -d C:\hospital-deploy\pip-packages --platform win_amd64
```

**注意**：conda 的离线包比较复杂，建议在医院部署时直接使用第二份文档的 pip wheels 方式。

---

## 十一、日常使用

### 11.1 启动系统

每次使用前，需要启动两个服务：

**窗口 1 - 后端：**
```cmd
cd C:\projects\medical-report-annotation\backend
conda activate medanno
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**窗口 2 - 前端：**
```cmd
cd C:\projects\medical-report-annotation\frontend\dist
python -m http.server 80
```

### 11.2 停止系统

直接关闭两个 CMD 窗口，或者在窗口中按 `Ctrl + C`。

### 11.3 开发模式（热重载）

如果需要修改代码：

**后端开发模式**：
```cmd
conda activate medanno
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**前端开发模式**：
```cmd
cd C:\projects\medical-report-annotation\frontend
npm run dev
```

---

## 十二、数据库备份

### 12.1 使用 pgAdmin 备份

1. 打开 pgAdmin 4
2. 右键点击 `med_anno` 数据库 → "Backup..."
3. Filename: 选择保存位置，输入文件名如 `backup_20240101`
4. Format: 选择 "Custom"
5. 点击 "Backup"

### 12.2 使用命令行备份

```cmd
"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe" -h localhost -U meduser -d med_anno -F c -f "C:\backup\med_anno_backup.dump"
```

会提示输入密码：`meduser123`

### 12.3 恢复备份

```cmd
"C:\Program Files\PostgreSQL\15\bin\pg_restore.exe" -h localhost -U meduser -d med_anno "C:\backup\med_anno_backup.dump"
```

---

## 十三、常见问题

### Q1: conda 命令找不到

**解决**：重新安装 Miniconda，确保勾选 "Add to PATH"。

或者手动添加环境变量：
- 系统属性 → 环境变量 → Path → 编辑
- 添加 `C:\Users\你的用户名\miniconda3\Scripts`
- 添加 `C:\Users\你的用户名\miniconda3`

### Q2: conda 安装包很慢

**解决**：配置清华镜像（见 2.4 节）

### Q3: conda 找不到某个包

**解决**：先搜索包：
```cmd
conda search 包名 -c conda-forge
```

如果找不到，使用 pip 安装：
```cmd
pip install 包名
```

### Q4: psycopg2 安装失败

**解决**：使用 conda 安装：
```cmd
conda install psycopg2 -c conda-forge
```

而不是 `psycopg2-binary`。

### Q5: 其他问题

参考原生 Python 版本的 Q1-Q5。

---

## 十四、下一步

完成本部署后，请参考第二份文档《医院离线部署文档》，将环境打包用于医院离线部署。

---

**文档版本**: v1.0  
**适用系统**: Windows 10/11  
**使用工具**: Miniconda  
**最后更新**: 2026-04-02
