#!/bin/bash
#
# 医疗影像报告标注系统 - 医院内网部署脚本
# 使用方法: sudo bash deploy.sh
#

set -e  # 遇到错误立即退出

echo "=============================================="
echo "医疗影像报告标注系统 - 医院内网部署脚本"
echo "=============================================="

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量
APP_DIR="/opt/medical-annotation"
DB_NAME="med_anno"
DB_USER="meduser"
DB_PASSWORD="$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24)"
SERVICE_USER="medical"

echo ""
echo -e "${YELLOW}[1/8] 检查系统环境...${NC}"

# 检测操作系统
if [ -f /etc/redhat-release ]; then
    OS="centos"
    PKG_MANAGER="yum"
elif [ -f /etc/debian_version ]; then
    OS="ubuntu"
    PKG_MANAGER="apt"
else
    echo -e "${RED}不支持的操作系统${NC}"
    exit 1
fi

echo "检测到操作系统: $OS"

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 sudo 运行此脚本${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}[2/8] 安装系统依赖...${NC}"

if [ "$OS" = "centos" ]; then
    $PKG_MANAGER install -y postgresql-server postgresql-contrib nginx python3 python3-pip
    # 初始化 PostgreSQL
    if [ ! -f /var/lib/pgsql/data/PG_VERSION ]; then
        postgresql-setup initdb
    fi
else
    $PKG_MANAGER update
    $PKG_MANAGER install -y postgresql postgresql-contrib nginx python3 python3-pip
fi

echo ""
echo -e "${YELLOW}[3/8] 启动 PostgreSQL...${NC}"

systemctl enable postgresql
systemctl start postgresql

# 等待 PostgreSQL 启动
sleep 2

echo ""
echo -e "${YELLOW}[4/8] 配置数据库...${NC}"

# 创建数据库和用户
sudo -u postgres psql <<EOF
DROP DATABASE IF EXISTS $DB_NAME;
DROP USER IF EXISTS $DB_USER;
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

echo "数据库已创建: $DB_NAME"
echo "数据库用户: $DB_USER"
echo "数据库密码: $DB_PASSWORD"

# 配置 PostgreSQL 仅本地访问
if [ "$OS" = "centos" ]; then
    PG_HBA="/var/lib/pgsql/data/pg_hba.conf"
    PG_CONF="/var/lib/pgsql/data/postgresql.conf"
else
    PG_VERSION=$(ls /etc/postgresql/)
    PG_HBA="/etc/postgresql/$PG_VERSION/main/pg_hba.conf"
    PG_CONF="/etc/postgresql/$PG_VERSION/main/postgresql.conf"
fi

# 确保只监听本地
sed -i "s/^#*listen_addresses.*/listen_addresses = 'localhost'/g" "$PG_CONF"

# 配置访问权限
grep -q "^local.*all.*all.*md5" "$PG_HBA" || echo "local   all             all                                     md5" >> "$PG_HBA"
grep -q "^host.*all.*all.*127.0.0.1" "$PG_HBA" || echo "host    all             all             127.0.0.1/32            md5" >> "$PG_HBA"

systemctl restart postgresql

echo ""
echo -e "${YELLOW}[5/8] 创建应用目录...${NC}"

# 创建用户
id -u $SERVICE_USER &>/dev/null || useradd -r -s /bin/false $SERVICE_USER

# 创建目录
mkdir -p $APP_DIR
mkdir -p /var/log/medical-annotation
mkdir -p $APP_DIR/backups

# 设置权限
chown -R $SERVICE_USER:$SERVICE_USER $APP_DIR
chown -R $SERVICE_USER:$SERVICE_USER /var/log/medical-annotation

echo ""
echo -e "${YELLOW}[6/8] 请上传后端代码到 $APP_DIR/backend${NC}"
echo ""
echo "请执行以下步骤:"
echo "1. 在开发机打包: tar -czf backend.tar.gz backend/"
echo "2. 上传到服务器: scp backend.tar.gz user@server:/tmp/"
echo "3. 解压到目标目录: tar -xzf /tmp/backend.tar.gz -C $APP_DIR/"
echo ""
read -p "完成后按 Enter 继续..."

# 检查后端代码是否存在
if [ ! -d "$APP_DIR/backend" ]; then
    echo -e "${RED}错误: 未找到后端代码目录 $APP_DIR/backend${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}[7/8] 安装 Python 依赖...${NC}"

cd $APP_DIR/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

echo ""
echo -e "${YELLOW}[8/8] 配置环境变量...${NC}"

# 生成随机 SECRET_KEY
SECRET_KEY=$(openssl rand -hex 32)

# 创建 .env 文件
cat > $APP_DIR/backend/.env <<EOF
DATABASE_URL=postgresql+psycopg2://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME
SECRET_KEY=$SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES=1440
EOF

chown $SERVICE_USER:$SERVICE_USER $APP_DIR/backend/.env
chmod 600 $APP_DIR/backend/.env

echo ""
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}基础部署完成！${NC}"
echo -e "${GREEN}==============================================${NC}"
echo ""
echo "数据库配置:"
echo "  数据库名: $DB_NAME"
echo "  用户名: $DB_USER"
echo "  密码: $DB_PASSWORD"
echo ""
echo "下一步:"
echo "1. 创建 systemd 服务: sudo bash scripts/setup_service.sh"
echo "2. 创建管理员账号: cd $APP_DIR/backend && source venv/bin/activate && python scripts/init_admin.py"
echo "3. 部署前端: sudo bash scripts/deploy_frontend.sh"
echo ""
