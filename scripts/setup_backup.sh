#!/bin/bash
#
# 设置自动备份
#

set -e

APP_DIR="/opt/medical-annotation"
DB_NAME="med_anno"
DB_USER="meduser"

echo "设置自动备份..."

# 创建备份脚本
cat > $APP_DIR/backup.sh <<EOF
#!/bin/bash
BACKUP_DIR="$APP_DIR/backups"
DATE=\$(date +%Y%m%d_%H%M%S)
mkdir -p \$BACKUP_DIR

# 备份数据库
pg_dump -h localhost -U $DB_USER $DB_NAME > \$BACKUP_DIR/med_anno_\$DATE.sql

# 保留最近 30 天的备份
find \$BACKUP_DIR -name "*.sql" -mtime +30 -delete

echo "[\$(date)] Backup completed: \$BACKUP_DIR/med_anno_\$DATE.sql"
EOF

chmod +x $APP_DIR/backup.sh

# 添加到 crontab（每天凌晨 2 点备份）
echo "0 2 * * * $APP_DIR/backup.sh >> /var/log/medical-annotation/backup.log 2>&1" | crontab -

echo "备份已设置完成"
echo "备份时间: 每天凌晨 2:00"
echo "备份位置: $APP_DIR/backups/"
echo ""
echo "手动备份命令: $APP_DIR/backup.sh"
