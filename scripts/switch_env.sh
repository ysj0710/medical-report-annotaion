#!/bin/bash
# 医疗报告标注系统 - 环境切换脚本
# 用法: ./switch_env.sh [online|local]

set -e

ENV_TYPE=${1:-}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -z "$ENV_TYPE" ]; then
    echo "用法: ./switch_env.sh [online|local|status]"
    echo "  online - 切换到线上环境 (Docker + med_anno)"
    echo "  local  - 切换到本地环境 (ysj conda + med_anno_local)"
    echo "  status - 查看当前环境状态"
    exit 1
fi

show_status() {
    echo "=== 当前环境状态 ==="
    echo ""
    
    # 检查端口占用
    echo "端口 5432 占用情况:"
    lsof -nP -iTCP:5432 2>/dev/null | grep -E "(COMMAND|docker|postgres|Python)" || echo "  5432 端口空闲"
    echo ""
    
    # 检查 Docker 数据库
    echo "Docker 数据库状态:"
    cd "$PROJECT_DIR/infra" && docker compose ps 2>/dev/null || echo "  未运行"
    echo ""
    
    # 检查本地 PostgreSQL
    echo "本地 PostgreSQL 状态:"
    export PGDATA=/opt/miniconda3/envs/ysj/var/postgresql
    if [ -f "$PGDATA/postmaster.pid" ]; then
        echo "  运行中 (PID: $(cat $PGDATA/postmaster.pid | head -1))"
    else
        echo "  未运行"
    fi
    echo ""
    
    # 检查后端
    echo "后端服务 (8088):"
    if lsof -ti:8088 > /dev/null 2>&1; then
        echo "  运行中 (PID: $(lsof -ti:8088 | head -1))"
    else
        echo "  未运行"
    fi
    echo ""
    
    # 检查前端
    echo "前端服务 (5173):"
    if lsof -ti:5173 > /dev/null 2>&1; then
        echo "  运行中 (PID: $(lsof -ti:5173 | head -1))"
    else
        echo "  未运行"
    fi
}

switch_online() {
    echo "=== 切换到线上环境 ==="
    
    # 1. 停止本地 PostgreSQL
    echo "1. 停止本地 PostgreSQL..."
    export PGDATA=/opt/miniconda3/envs/ysj/var/postgresql
    if [ -f "$PGDATA/postmaster.pid" ]; then
        pg_ctl stop -D "$PGDATA" -m fast 2>/dev/null || true
        sleep 2
    fi
    
    # 2. 启动 Docker 数据库
    echo "2. 启动 Docker 数据库..."
    cd "$PROJECT_DIR/infra"
    docker compose up -d
    sleep 3
    
    # 3. 等待数据库就绪
    echo "3. 等待数据库就绪..."
    until docker exec infra-db-1 pg_isready -U postgres > /dev/null 2>&1; do
        echo "  等待中..."
        sleep 1
    done
    
    # 4. 更新后端配置为线上数据库
    echo "4. 更新后端配置..."
    echo "DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/med_anno" > "$PROJECT_DIR/backend/.env"
    
    echo ""
    echo "✅ 线上环境已就绪！"
    echo "   数据库: Docker (med_anno)"
    echo "   启动后端: cd backend && source venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8088 --reload"
    echo "   启动前端: cd frontend && npm run dev"
}

switch_local() {
    echo "=== 切换到本地环境 ==="
    
    # 1. 停止 Docker 数据库
    echo "1. 停止 Docker 数据库..."
    cd "$PROJECT_DIR/infra"
    docker compose stop 2>/dev/null || true
    sleep 2
    
    # 2. 确保端口释放
    echo "2. 确保端口 5432 释放..."
    sleep 1
    
    # 3. 启动本地 PostgreSQL
    echo "3. 启动本地 PostgreSQL..."
    source /opt/miniconda3/bin/activate
    conda activate ysj
    export PGDATA=/opt/miniconda3/envs/ysj/var/postgresql
    
    if [ ! -f "$PGDATA/postmaster.pid" ]; then
        pg_ctl start -D "$PGDATA" -l "$PGDATA/logfile"
        sleep 3
    else
        echo "  本地 PostgreSQL 已在运行"
    fi
    
    # 4. 创建本地数据库（如果不存在）
    echo "4. 检查本地数据库..."
    psql -U "$USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='med_anno_local'" | grep -q 1 || \
        psql -U "$USER" -d postgres -c "CREATE DATABASE med_anno_local;"
    
    # 5. 更新后端配置为本地数据库
    echo "5. 更新后端配置..."
    echo "DATABASE_URL=postgresql+psycopg2://$USER@127.0.0.1:5432/med_anno_local" > "$PROJECT_DIR/backend/.env"
    
    echo ""
    echo "✅ 本地环境已就绪！"
    echo "   数据库: ysj conda (med_anno_local)"
    echo "   启动后端: cd backend && source /opt/miniconda3/bin/activate && conda activate ysj && uvicorn app.main:app --host 127.0.0.1 --port 8088 --reload"
    echo "   启动前端: cd frontend && npm run dev"
}

case "$ENV_TYPE" in
    online)
        switch_online
        ;;
    local)
        switch_local
        ;;
    status)
        show_status
        ;;
    *)
        echo "错误: 未知环境 '$ENV_TYPE'"
        echo "用法: ./switch_env.sh [online|local|status]"
        exit 1
        ;;
esac
