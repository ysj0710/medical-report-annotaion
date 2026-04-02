#!/bin/bash
#
# 前端部署脚本
#

set -e

APP_DIR="/opt/medical-annotation"

echo "=============================================="
echo "前端部署"
echo "=============================================="

echo ""
echo "请上传前端构建文件到服务器:"
echo "1. 在开发机构建: cd frontend && npm run build"
echo "2. 打包: tar -czf frontend-dist.tar.gz dist/"
echo "3. 上传: scp frontend-dist.tar.gz user@server:/tmp/"
echo ""
read -p "上传完成后按 Enter 继续..."

if [ ! -f "/tmp/frontend-dist.tar.gz" ]; then
    echo "错误: 未找到 /tmp/frontend-dist.tar.gz"
    exit 1
fi

# 解压前端文件
cd $APP_DIR
tar -xzf /tmp/frontend-dist.tar.gz
chown -R medical:medical $APP_DIR/dist

echo "前端文件已部署到 $APP_DIR/dist"

# 配置 Nginx
echo ""
echo "配置 Nginx..."

cat > /etc/nginx/conf.d/medical-annotation.conf <<'EOF'
server {
    listen 80;
    server_name _;

    access_log /var/log/nginx/medical-annotation-access.log;
    error_log /var/log/nginx/medical-annotation-error.log;

    location / {
        root /opt/medical-annotation/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    client_max_body_size 100M;
}
EOF

# 测试并重载 Nginx
nginx -t
systemctl enable nginx
systemctl restart nginx

echo ""
echo "=============================================="
echo "前端部署完成！"
echo "=============================================="
echo ""
echo "系统已可以通过 http://<服务器IP>/ 访问"
