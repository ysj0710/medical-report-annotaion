#!/bin/bash
#
# 创建 systemd 服务
#

set -e

APP_DIR="/opt/medical-annotation"
SERVICE_USER="medical"

echo "创建 systemd 服务..."

cat > /etc/systemd/system/medical-annotation.service <<EOF
[Unit]
Description=Medical Report Annotation API
After=network.target postgresql.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$APP_DIR/backend
Environment=PATH=$APP_DIR/backend/venv/bin
EnvironmentFile=$APP_DIR/backend/.env
ExecStart=$APP_DIR/backend/venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --access-logfile /var/log/medical-annotation/access.log --error-logfile /var/log/medical-annotation/error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable medical-annotation
systemctl start medical-annotation

echo "服务已创建并启动"
echo ""
echo "查看状态: sudo systemctl status medical-annotation"
echo "查看日志: sudo journalctl -u medical-annotation -f"
