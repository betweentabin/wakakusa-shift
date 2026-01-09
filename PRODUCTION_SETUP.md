# 本番環境セットアップガイド

## 🎯 概要

このガイドでは、わかくさシフト管理システムを本番環境にデプロイする手順を説明します。
Ubuntu 20.04 LTS + Nginx + Gunicorn + PostgreSQL構成を前提としています。

## 📋 前提条件

### サーバー要件
- **OS**: Ubuntu 20.04 LTS以上
- **CPU**: 2コア以上
- **メモリ**: 4GB以上
- **ストレージ**: 20GB以上
- **ネットワーク**: 固定IPアドレス

### ドメイン・SSL
- 独自ドメインの取得
- DNS設定の完了
- SSL証明書（Let's Encrypt推奨）

## 🚀 セットアップ手順

### 1. システム更新とパッケージインストール

```bash
# システム更新
sudo apt update && sudo apt upgrade -y

# 必要なパッケージのインストール
sudo apt install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib git curl

# Node.js（フロントエンド用）
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2. PostgreSQLセットアップ

```bash
# PostgreSQLサービス開始
sudo systemctl start postgresql
sudo systemctl enable postgresql

# データベースとユーザー作成
sudo -u postgres psql << EOF
CREATE DATABASE wakakusa_shift;
CREATE USER wakakusa_user WITH PASSWORD 'your_secure_password';
ALTER ROLE wakakusa_user SET client_encoding TO 'utf8';
ALTER ROLE wakakusa_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE wakakusa_user SET timezone TO 'Asia/Tokyo';
GRANT ALL PRIVILEGES ON DATABASE wakakusa_shift TO wakakusa_user;
\q
EOF
```

### 3. アプリケーションユーザー作成

```bash
# アプリケーション用ユーザー作成
sudo adduser --system --group --home /opt/wakakusa wakakusa

# ディレクトリ作成
sudo mkdir -p /opt/wakakusa/app
sudo mkdir -p /opt/wakakusa/logs
sudo mkdir -p /opt/wakakusa/static
sudo mkdir -p /opt/wakakusa/media

# 権限設定
sudo chown -R wakakusa:wakakusa /opt/wakakusa
```

### 4. アプリケーションデプロイ

```bash
# アプリケーションユーザーに切り替え
sudo -u wakakusa -i

# アプリケーションコードの取得
cd /opt/wakakusa
git clone https://github.com/your-repo/wakakusa-shift-1.git app
cd app

# Python仮想環境作成
python3 -m venv venv
source venv/bin/activate

# 依存関係インストール
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
```

### 5. Django設定

#### 5.1 本番用設定ファイル作成

```bash
# 本番用設定ファイル作成
cat > core/settings_production.py << 'EOF'
from .settings import *
import os

# セキュリティ設定
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com']

# データベース設定
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'wakakusa_shift',
        'USER': 'wakakusa_user',
        'PASSWORD': 'your_secure_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# 静的ファイル設定
STATIC_ROOT = '/opt/wakakusa/static'
MEDIA_ROOT = '/opt/wakakusa/media'

# セキュリティ設定
SECRET_KEY = 'your-very-secure-secret-key-here'
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ログ設定
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/opt/wakakusa/logs/django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
EOF
```

#### 5.2 環境変数設定

```bash
# 環境変数ファイル作成
cat > .env << 'EOF'
DJANGO_SETTINGS_MODULE=core.settings_production
SECRET_KEY=your-very-secure-secret-key-here
DATABASE_URL=postgresql://wakakusa_user:your_secure_password@localhost/wakakusa_shift
EOF
```

#### 5.3 データベースマイグレーション

```bash
# マイグレーション実行
python manage.py migrate

# 静的ファイル収集
python manage.py collectstatic --noinput

# 管理者ユーザー作成
python manage.py createsuperuser
```

### 6. Gunicorn設定

#### 6.1 Gunicorn設定ファイル

```bash
cat > gunicorn.conf.py << 'EOF'
import multiprocessing

# サーバー設定
bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2

# ログ設定
accesslog = "/opt/wakakusa/logs/gunicorn_access.log"
errorlog = "/opt/wakakusa/logs/gunicorn_error.log"
loglevel = "info"

# プロセス設定
user = "wakakusa"
group = "wakakusa"
daemon = False
pidfile = "/opt/wakakusa/gunicorn.pid"

# セキュリティ
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
EOF
```

#### 6.2 systemdサービス作成

```bash
# rootユーザーに戻る
exit

# systemdサービスファイル作成
sudo cat > /etc/systemd/system/wakakusa.service << 'EOF'
[Unit]
Description=Wakakusa Shift Management System
After=network.target

[Service]
Type=notify
User=wakakusa
Group=wakakusa
RuntimeDirectory=wakakusa
WorkingDirectory=/opt/wakakusa/app
Environment=DJANGO_SETTINGS_MODULE=core.settings_production
ExecStart=/opt/wakakusa/app/venv/bin/gunicorn core.wsgi:application -c gunicorn.conf.py
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# サービス有効化・開始
sudo systemctl daemon-reload
sudo systemctl enable wakakusa
sudo systemctl start wakakusa
```

### 7. Nginx設定

#### 7.1 Nginx設定ファイル

```bash
sudo cat > /etc/nginx/sites-available/wakakusa << 'EOF'
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL設定
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # セキュリティヘッダー
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    # ログ設定
    access_log /var/log/nginx/wakakusa_access.log;
    error_log /var/log/nginx/wakakusa_error.log;

    # 静的ファイル
    location /static/ {
        alias /opt/wakakusa/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /opt/wakakusa/media/;
        expires 1y;
        add_header Cache-Control "public";
    }

    # アプリケーション
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # ファイルアップロード制限
    client_max_body_size 10M;
}
EOF

# サイト有効化
sudo ln -s /etc/nginx/sites-available/wakakusa /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 8. SSL証明書設定（Let's Encrypt）

```bash
# Certbot インストール
sudo apt install -y certbot python3-certbot-nginx

# SSL証明書取得
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# 自動更新設定
sudo crontab -e
# 以下を追加
0 12 * * * /usr/bin/certbot renew --quiet
```

### 9. ファイアウォール設定

```bash
# UFW有効化
sudo ufw enable

# 必要なポートを開放
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'

# 状態確認
sudo ufw status
```

### 10. ログローテーション設定

```bash
sudo cat > /etc/logrotate.d/wakakusa << 'EOF'
/opt/wakakusa/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 wakakusa wakakusa
    postrotate
        systemctl reload wakakusa
    endscript
}
EOF
```

## 🔧 運用・保守

### 定期バックアップ

#### データベースバックアップスクリプト

```bash
sudo cat > /opt/wakakusa/backup_db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/wakakusa/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="wakakusa_shift"
DB_USER="wakakusa_user"

mkdir -p $BACKUP_DIR

# データベースバックアップ
pg_dump -U $DB_USER -h localhost $DB_NAME | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# 古いバックアップ削除（30日以上）
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +30 -delete

echo "Database backup completed: db_backup_$DATE.sql.gz"
EOF

sudo chmod +x /opt/wakakusa/backup_db.sh
sudo chown wakakusa:wakakusa /opt/wakakusa/backup_db.sh

# cron設定
sudo -u wakakusa crontab -e
# 以下を追加
0 2 * * * /opt/wakakusa/backup_db.sh
```

### 監視設定

#### システム監視スクリプト

```bash
sudo cat > /opt/wakakusa/monitor.sh << 'EOF'
#!/bin/bash
LOG_FILE="/opt/wakakusa/logs/monitor.log"

# サービス状態チェック
if ! systemctl is-active --quiet wakakusa; then
    echo "$(date): Wakakusa service is down!" >> $LOG_FILE
    systemctl restart wakakusa
fi

if ! systemctl is-active --quiet nginx; then
    echo "$(date): Nginx service is down!" >> $LOG_FILE
    systemctl restart nginx
fi

if ! systemctl is-active --quiet postgresql; then
    echo "$(date): PostgreSQL service is down!" >> $LOG_FILE
    systemctl restart postgresql
fi

# ディスク使用量チェック
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "$(date): Disk usage is high: ${DISK_USAGE}%" >> $LOG_FILE
fi

# メモリ使用量チェック
MEM_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ $MEM_USAGE -gt 80 ]; then
    echo "$(date): Memory usage is high: ${MEM_USAGE}%" >> $LOG_FILE
fi
EOF

sudo chmod +x /opt/wakakusa/monitor.sh

# cron設定
sudo crontab -e
# 以下を追加
*/5 * * * * /opt/wakakusa/monitor.sh
```

### アップデート手順

```bash
# アプリケーションユーザーに切り替え
sudo -u wakakusa -i
cd /opt/wakakusa/app

# コード更新
git pull origin main

# 仮想環境アクティベート
source venv/bin/activate

# 依存関係更新
pip install -r requirements.txt

# マイグレーション実行
python manage.py migrate

# 静的ファイル更新
python manage.py collectstatic --noinput

# サービス再起動
exit
sudo systemctl restart wakakusa
```

## 🔍 トラブルシューティング

### よくある問題と対処法

#### 1. サービスが起動しない
```bash
# ログ確認
sudo journalctl -u wakakusa -f
sudo tail -f /opt/wakakusa/logs/gunicorn_error.log

# 設定確認
sudo -u wakakusa /opt/wakakusa/app/venv/bin/python /opt/wakakusa/app/manage.py check --deploy
```

#### 2. データベース接続エラー
```bash
# PostgreSQL状態確認
sudo systemctl status postgresql

# 接続テスト
sudo -u wakakusa psql -h localhost -U wakakusa_user -d wakakusa_shift
```

#### 3. 静的ファイルが表示されない
```bash
# 権限確認
ls -la /opt/wakakusa/static/

# Nginx設定確認
sudo nginx -t
sudo systemctl reload nginx
```

## 📊 パフォーマンス最適化

### データベース最適化

```sql
-- インデックス作成
CREATE INDEX idx_shift_date ON shift_management_shift(date);
CREATE INDEX idx_shift_staff ON shift_management_shift(staff_id);
CREATE INDEX idx_shift_approval ON shift_management_shift(approval_status);
CREATE INDEX idx_staff_approval ON shift_management_staff(approval_status);

-- 統計情報更新
ANALYZE;
```

### Nginx最適化

```nginx
# gzip圧縮
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

# キープアライブ
keepalive_timeout 65;
keepalive_requests 100;
```

## 🔐 セキュリティ強化

### 追加セキュリティ設定

```bash
# fail2ban インストール
sudo apt install -y fail2ban

# fail2ban設定
sudo cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true

[nginx-http-auth]
enabled = true
EOF

sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

**最終更新**: 2025年6月13日  
**バージョン**: 1.0.0 