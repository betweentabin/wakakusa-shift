# 🌸 わかくさシフト - Xserver-VPS 本番環境セットアップガイド

## 概要
このガイドでは、Xserver-VPSでの「わかくさシフト」システムの本番環境構築手順を説明します。pm2を使用したプロセス管理とデータベース設定を含みます。

---

## 前提条件

### サーバー環境
- **Xserver-VPS** (Ubuntu 20.04 LTS 推奨)
- **sudoコマンド使用可能**なユーザーアカウント
- **SSH接続**が可能

### 必要なソフトウェア
- Python 3.8+
- Node.js 16+ (pm2用)
- PostgreSQL 12+
- Nginx
- Git

---

## 1. 基本環境のセットアップ

### システムアップデート
```bash
sudo apt update && sudo apt upgrade -y
```

### 必要パッケージのインストール
```bash
# Python関連
sudo apt install python3 python3-pip python3-venv python3-dev -y

# PostgreSQL
sudo apt install postgresql postgresql-contrib libpq-dev -y

# Nginx
sudo apt install nginx -y

# Node.js (pm2用)
curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash -
sudo apt install nodejs -y

# その他必要なパッケージ
sudo apt install git build-essential -y
```

### pm2のインストール
```bash
sudo npm install -g pm2
```

---

## 2. PostgreSQLデータベースの設定

### PostgreSQLサービス開始
```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### データベースとユーザーの作成
```bash
# PostgreSQLユーザーに切り替え
sudo -u postgres psql

# データベースとユーザーを作成
CREATE DATABASE wakakusa_shift;
CREATE USER wakakusa_user WITH PASSWORD 'your_secure_password_here';
ALTER ROLE wakakusa_user SET client_encoding TO 'utf8';
ALTER ROLE wakakusa_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE wakakusa_user SET timezone TO 'Asia/Tokyo';
GRANT ALL PRIVILEGES ON DATABASE wakakusa_shift TO wakakusa_user;
\q
```

### PostgreSQL設定ファイルの編集
```bash
# postgresql.conf の編集
sudo nano /etc/postgresql/12/main/postgresql.conf

# 以下の行を編集
listen_addresses = 'localhost'
timezone = 'Asia/Tokyo'

# pg_hba.conf の編集
sudo nano /etc/postgresql/12/main/pg_hba.conf

# 以下の行を追加（local connections用）
local   wakakusa_shift  wakakusa_user                   md5
```

### PostgreSQL再起動
```bash
sudo systemctl restart postgresql
```

---

## 3. アプリケーションのデプロイ

### プロジェクトディレクトリの作成
```bash
sudo mkdir -p /var/www/wakakusa-shift
sudo chown $USER:$USER /var/www/wakakusa-shift
cd /var/www/wakakusa-shift
```

### Gitリポジトリのクローン
```bash
# GitHubからクローン（実際のリポジトリURLに変更）
git clone https://github.com/your-username/wakakusa-shift.git .

# または、ローカルからファイルをアップロード
# scp -r /path/to/local/wakakusa-shift/* user@server:/var/www/wakakusa-shift/
```

### Python仮想環境の作成
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 本番用設定ファイルの作成
```bash
# 本番用設定ファイルを作成
cp core/settings.py core/settings_production.py
```

### 本番用設定の編集
```python
# core/settings_production.py

import os
from .settings import *

# 本番環境設定
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com', 'your-server-ip']

# データベース設定
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'wakakusa_shift',
        'USER': 'wakakusa_user',
        'PASSWORD': 'your_secure_password_here',
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'charset': 'utf8',
        },
    }
}

# セキュリティ設定
SECRET_KEY = 'your-production-secret-key-here'  # 新しいキーを生成
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# 静的ファイル設定
STATIC_URL = '/static/'
STATIC_ROOT = '/var/www/wakakusa-shift/staticfiles/'
MEDIA_URL = '/media/'
MEDIA_ROOT = '/var/www/wakakusa-shift/media/'

# ログ設定
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/www/wakakusa-shift/logs/django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# タイムゾーン
TIME_ZONE = 'Asia/Tokyo'
USE_TZ = True
```

### 必要なディレクトリの作成
```bash
mkdir -p logs
mkdir -p staticfiles
mkdir -p media
```

### データベースマイグレーション
```bash
# 本番用設定を使用
export DJANGO_SETTINGS_MODULE=core.settings_production

# マイグレーション実行
python manage.py makemigrations
python manage.py migrate

# 静的ファイル収集
python manage.py collectstatic --noinput

# スーパーユーザー作成
python manage.py createsuperuser
```

---

## 4. pm2設定とプロセス管理

### pm2設定ファイルの作成
```bash
# ecosystem.config.js を作成
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [{
    name: 'wakakusa-shift',
    script: 'venv/bin/python',
    args: 'manage.py runserver 127.0.0.1:8000',
    cwd: '/var/www/wakakusa-shift',
    env: {
      DJANGO_SETTINGS_MODULE: 'core.settings_production',
      PYTHONPATH: '/var/www/wakakusa-shift'
    },
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    error_file: '/var/www/wakakusa-shift/logs/pm2-error.log',
    out_file: '/var/www/wakakusa-shift/logs/pm2-out.log',
    log_file: '/var/www/wakakusa-shift/logs/pm2-combined.log',
    time: true
  }]
};
EOF
```

### Gunicorn設定（推奨）
```bash
# Gunicornをインストール
pip install gunicorn

# Gunicorn設定ファイルを作成
cat > gunicorn.conf.py << 'EOF'
bind = "127.0.0.1:8000"
workers = 2
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
preload_app = True
daemon = False
user = "www-data"
group = "www-data"
tmp_upload_dir = None
logfile = "/var/www/wakakusa-shift/logs/gunicorn.log"
loglevel = "info"
access_logfile = "/var/www/wakakusa-shift/logs/gunicorn-access.log"
error_logfile = "/var/www/wakakusa-shift/logs/gunicorn-error.log"
EOF

# pm2設定をGunicorn用に更新
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [{
    name: 'wakakusa-shift',
    script: 'venv/bin/gunicorn',
    args: 'core.wsgi:application -c gunicorn.conf.py',
    cwd: '/var/www/wakakusa-shift',
    env: {
      DJANGO_SETTINGS_MODULE: 'core.settings_production',
      PYTHONPATH: '/var/www/wakakusa-shift'
    },
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    error_file: '/var/www/wakakusa-shift/logs/pm2-error.log',
    out_file: '/var/www/wakakusa-shift/logs/pm2-out.log',
    log_file: '/var/www/wakakusa-shift/logs/pm2-combined.log',
    time: true
  }]
};
EOF
```

### pm2でアプリケーション起動
```bash
# アプリケーション起動
pm2 start ecosystem.config.js

# pm2プロセス確認
pm2 list

# ログ確認
pm2 logs wakakusa-shift

# pm2を自動起動に設定
pm2 startup
pm2 save
```

---

## 5. Nginx設定

### Nginx設定ファイルの作成
```bash
sudo nano /etc/nginx/sites-available/wakakusa-shift
```

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    
    # HTTPからHTTPSへリダイレクト
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;
    
    # SSL証明書設定（Let's Encryptを使用する場合）
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # SSL設定
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    
    # セキュリティヘッダー
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    
    # 静的ファイル設定
    location /static/ {
        alias /var/www/wakakusa-shift/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /var/www/wakakusa-shift/media/;
        expires 1y;
        add_header Cache-Control "public";
    }
    
    # Django アプリケーション
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # タイムアウト設定
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # ログ設定
    access_log /var/log/nginx/wakakusa-shift-access.log;
    error_log /var/log/nginx/wakakusa-shift-error.log;
}
```

### Nginx設定の有効化
```bash
# 設定ファイルのシンボリックリンク作成
sudo ln -s /etc/nginx/sites-available/wakakusa-shift /etc/nginx/sites-enabled/

# デフォルト設定を無効化
sudo rm /etc/nginx/sites-enabled/default

# 設定テスト
sudo nginx -t

# Nginx再起動
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 6. SSL証明書の設定（Let's Encrypt）

### Certbotのインストール
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### SSL証明書の取得
```bash
# 証明書取得（ドメイン名を実際のものに変更）
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# 自動更新の設定
sudo crontab -e

# 以下の行を追加
0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 7. ファイアウォール設定

### UFWの設定
```bash
# UFW有効化
sudo ufw enable

# 必要なポートを開放
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'

# 状態確認
sudo ufw status
```

---

## 8. 監視とログ管理

### ログローテーション設定
```bash
sudo nano /etc/logrotate.d/wakakusa-shift
```

```
/var/www/wakakusa-shift/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        pm2 reload wakakusa-shift
    endscript
}
```

### システム監視スクリプト
```bash
# 監視スクリプトの作成
cat > /var/www/wakakusa-shift/monitor.sh << 'EOF'
#!/bin/bash

# アプリケーションの死活監視
if ! pm2 list | grep -q "wakakusa-shift.*online"; then
    echo "$(date): wakakusa-shift is down, restarting..." >> /var/www/wakakusa-shift/logs/monitor.log
    pm2 restart wakakusa-shift
fi

# ディスク使用量チェック
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "$(date): Disk usage is ${DISK_USAGE}%" >> /var/www/wakakusa-shift/logs/monitor.log
fi

# メモリ使用量チェック
MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100.0)}')
if [ $MEMORY_USAGE -gt 80 ]; then
    echo "$(date): Memory usage is ${MEMORY_USAGE}%" >> /var/www/wakakusa-shift/logs/monitor.log
fi
EOF

chmod +x /var/www/wakakusa-shift/monitor.sh

# Cronジョブに追加
(crontab -l 2>/dev/null; echo "*/5 * * * * /var/www/wakakusa-shift/monitor.sh") | crontab -
```

---

## 9. バックアップ設定

### データベースバックアップスクリプト
```bash
cat > /var/www/wakakusa-shift/backup_db.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/var/www/wakakusa-shift/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="wakakusa_shift"
DB_USER="wakakusa_user"

# バックアップディレクトリ作成
mkdir -p $BACKUP_DIR

# データベースバックアップ
pg_dump -U $DB_USER -h localhost $DB_NAME > $BACKUP_DIR/db_backup_$DATE.sql

# 7日以上古いバックアップを削除
find $BACKUP_DIR -name "db_backup_*.sql" -mtime +7 -delete

echo "$(date): Database backup completed: db_backup_$DATE.sql" >> /var/www/wakakusa-shift/logs/backup.log
EOF

chmod +x /var/www/wakakusa-shift/backup_db.sh

# 毎日午前2時にバックアップ実行
(crontab -l 2>/dev/null; echo "0 2 * * * /var/www/wakakusa-shift/backup_db.sh") | crontab -
```

---

## 10. デプロイメント自動化

### デプロイスクリプトの作成
```bash
cat > /var/www/wakakusa-shift/deploy.sh << 'EOF'
#!/bin/bash

cd /var/www/wakakusa-shift

echo "Starting deployment..."

# Git pull
git pull origin main

# 仮想環境アクティベート
source venv/bin/activate

# 依存関係更新
pip install -r requirements.txt

# マイグレーション
export DJANGO_SETTINGS_MODULE=core.settings_production
python manage.py migrate

# 静的ファイル収集
python manage.py collectstatic --noinput

# pm2でアプリケーション再起動
pm2 restart wakakusa-shift

echo "Deployment completed!"
EOF

chmod +x /var/www/wakakusa-shift/deploy.sh
```

---

## 11. 運用コマンド集

### pm2関連コマンド
```bash
# アプリケーション起動
pm2 start ecosystem.config.js

# アプリケーション停止
pm2 stop wakakusa-shift

# アプリケーション再起動
pm2 restart wakakusa-shift

# アプリケーション削除
pm2 delete wakakusa-shift

# ログ確認
pm2 logs wakakusa-shift

# プロセス監視
pm2 monit

# 設定保存
pm2 save
```

### データベース関連コマンド
```bash
# データベース接続
sudo -u postgres psql wakakusa_shift

# バックアップ作成
pg_dump -U wakakusa_user -h localhost wakakusa_shift > backup.sql

# バックアップ復元
psql -U wakakusa_user -h localhost wakakusa_shift < backup.sql
```

### ログ確認コマンド
```bash
# Django ログ
tail -f /var/www/wakakusa-shift/logs/django.log

# Gunicorn ログ
tail -f /var/www/wakakusa-shift/logs/gunicorn.log

# Nginx ログ
sudo tail -f /var/log/nginx/wakakusa-shift-access.log
sudo tail -f /var/log/nginx/wakakusa-shift-error.log

# pm2 ログ
pm2 logs wakakusa-shift
```

---

## 12. トラブルシューティング

### よくある問題と解決方法

#### アプリケーションが起動しない
```bash
# pm2ログを確認
pm2 logs wakakusa-shift

# 設定ファイルを確認
python manage.py check --settings=core.settings_production

# データベース接続を確認
python manage.py dbshell --settings=core.settings_production
```

#### 静的ファイルが表示されない
```bash
# 静的ファイルを再収集
python manage.py collectstatic --clear --noinput

# Nginxの設定を確認
sudo nginx -t

# ファイル権限を確認
ls -la /var/www/wakakusa-shift/staticfiles/
```

#### データベース接続エラー
```bash
# PostgreSQLサービス状態確認
sudo systemctl status postgresql

# データベース接続テスト
psql -U wakakusa_user -h localhost wakakusa_shift

# 設定ファイルの確認
cat core/settings_production.py | grep -A 10 DATABASES
```

---

## 13. セキュリティチェックリスト

- [ ] SSH鍵認証の設定
- [ ] rootログインの無効化
- [ ] ファイアウォールの設定
- [ ] SSL証明書の設定
- [ ] Django SECRET_KEYの変更
- [ ] データベースパスワードの強化
- [ ] 定期的なセキュリティアップデート
- [ ] ログ監視の設定
- [ ] バックアップの自動化

---

## まとめ

このガイドに従って設定することで、Xserver-VPS上でpm2を使用した安定したDjangoアプリケーションの運用が可能になります。

### 重要なポイント
1. **pm2によるプロセス管理** - 自動再起動とログ管理
2. **PostgreSQLデータベース** - 本番環境に適したデータベース
3. **Nginx + SSL** - 高性能なWebサーバーとセキュリティ
4. **監視とバックアップ** - 安定した運用のための仕組み

定期的なメンテナンスとモニタリングを行い、安全で安定したサービス運用を心がけてください。

---

*最終更新: 2024年6月* 