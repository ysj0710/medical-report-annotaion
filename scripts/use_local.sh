#!/bin/bash
# 切换到本地环境（5432 端口）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "切换到本地环境..."
echo "DATABASE_URL=postgresql+psycopg2://enjoy0710@127.0.0.1:5432/med_anno_local" > "$SCRIPT_DIR/../backend/.env"

echo "✅ 已切换到本地环境（ysj conda + 5432 端口）"
echo "   数据库: med_anno_local"
echo "   启动方式: conda activate ysj && uvicorn app.main:app --host 127.0.0.1 --port 8088 --reload"
