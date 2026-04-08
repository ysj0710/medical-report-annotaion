#!/bin/bash
# 切换到线上环境（5433 端口）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "切换到线上环境..."
echo "DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5433/med_anno" > "$SCRIPT_DIR/../backend/.env"

echo "✅ 已切换到线上环境（Docker + 5433 端口）"
echo "   数据库: med_anno"
echo "   启动方式: source venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8088 --reload"
