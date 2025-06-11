# わかくさシフト 本番環境セットアップガイド

## 概要

このガイドでは、わかくさシフト管理システムを本番環境にデプロイする手順を詳しく説明します。

## 前提条件

- Linux サーバー（Ubuntu 22.04 LTS推奨）
- Python 3.11以上
- MySQL 8.0以上
- Redis 7.0以上（推奨）
- Nginx または Apache
- SSL証明書（HTTPS対応）

## 1. システム準備

### 1.1 必要なパッケージのインストール

```bash
# システムアップデート
sudo apt update && sudo apt upgrade -y

# 必要なパッケージをインストール
sudo apt install -y python3 python3-pip python3-venv git nginx mysql-server redis-server
sudo apt install -y build-essential libmysqlclient-dev pkg-config
sudo apt install -y supervisor logrotate curl htop

# Python依存関係
sudo apt install -y python3-dev python3-setuptools
```

### 1.2 ユーザー作成

```bash
# アプリケーション用ユーザーを作成
sudo useradd -m -s /bin/bash wakakusa
sudo usermod -aG sudo wakakusa

# ユーザーを切り替え
sudo su - wakakusa
```

## 2. プロジェクトのデプロイ

### 2.1 プロジェクトのクローン

```bash
# ホームディレクトリに移動
cd /home/wakakusa

# プロジェクトをクローン
git clone https://github.com/your-repo/wakakusa-shift-1.git
cd wakakusa-shift-1

# 実行権限を付与
chmod +x scripts/*.sh
chmod +x scripts/*.py
```

### 2.2 環境変数の設定

```bash
# 環境変数ファイルを作成
cp env.example .env

# 環境変数を編集
nano .env
```

`.env`ファイルの設定例：

```bash
# Django設定
DJANGO_SETTINGS_MODULE=core.settings.production
DJANGO_SECRET_KEY=your-super-secret-key-change-this

# データベース設定
DB_NAME=wakakusa_shift_db
DB_USER=wakakusa_user
DB_PASSWORD=your-secure-password
DB_HOST=localhost
DB_PORT=3306

# ホスト設定
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# HTTPS設定
USE_HTTPS=true

# Redis設定
REDIS_URL=redis://localhost:6379/1

# メール設定
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
ADMIN_EMAIL=admin@yourdomain.com
```

### 2.3 データベースの設定

```bash
# MySQLにログイン
sudo mysql -u root -p

# データベースとユーザーを作成
CREATE DATABASE wakakusa_shift_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'wakakusa_user'@'localhost' IDENTIFIED BY 'your-secure-password';
GRANT ALL PRIVILEGES ON wakakusa_shift_db.* TO 'wakakusa_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

## 3. アプリケーションのセットアップ

### 3.1 自動デプロイスクリプトの実行

```bash
# 環境変数を読み込み
source .env

# 本番環境デプロイを実行
./scripts/deploy.sh production
```

### 3.2 手動セットアップ（必要に応じて）

```bash
# 仮想環境を作成
python3 -m venv venv
source venv/bin/activate

# 依存関係をインストール
pip install -r requirements_production.txt

# データベースマイグレーション
python3 manage_prod.py migrate

# 静的ファイル収集
python3 manage_prod.py collectstatic --noinput

# 初期セットアップ
python3 manage_prod.py setup_production --create-superuser --create-sample-data --optimize-db --warm-cache
```

## 4. Webサーバーの設定

### 4.1 Gunicornの設定

```bash
# Gunicornをテスト起動
cd /home/wakakusa/wakakusa-shift-1
source venv/bin/activate
gunicorn -c gunicorn.conf.py core.wsgi_production:application
```

### 4.2 Supervisorの設定

```bash
# Supervisor設定ファイルを作成
sudo nano /etc/supervisor/conf.d/wakakusa-shift.conf
```

設定内容：

```ini
[program:wakakusa-shift]
command=/home/wakakusa/wakakusa-shift-1/venv/bin/gunicorn -c gunicorn.conf.py core.wsgi_production:application
directory=/home/wakakusa/wakakusa-shift-1
user=wakakusa
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/wakakusa/wakakusa-shift-1/logs/gunicorn_supervisor.log
environment=DJANGO_SETTINGS_MODULE=core.settings.production
```

```bash
# Supervisorを再起動
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start wakakusa-shift
```

### 4.3 Nginxの設定

```bash
# Nginx設定ファイルを作成
sudo nano /etc/nginx/sites-available/wakakusa-shift
```

設定内容：

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /path/to/ssl/certificate.crt;
    ssl_certificate_key /path/to/ssl/private.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /static/ {
        alias /home/wakakusa/wakakusa-shift-1/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /home/wakakusa/wakakusa-shift-1/media/;
        expires 1y;
        add_header Cache-Control "public";
    }

    # ヘルスチェックエンドポイント
    location /health/ {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
    }

    # セキュリティヘッダー
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

```bash
# 設定を有効化
sudo ln -s /etc/nginx/sites-available/wakakusa-shift /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 5. 監視とログ設定

### 5.1 ログローテーション

```bash
# logrotate設定を作成
sudo nano /etc/logrotate.d/wakakusa-shift
```

設定内容：

```
/home/wakakusa/wakakusa-shift-1/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 wakakusa wakakusa
    postrotate
        sudo supervisorctl restart wakakusa-shift
    endscript
}
```

### 5.2 Cronジョブの設定

```bash
# crontabを編集
crontab -e

# scripts/crontab.example の内容を参考に設定を追加
```

### 5.3 監視スクリプトの設定

```bash
# 監視スクリプトに実行権限を付与
chmod +x scripts/monitor.py

# 必要な依存関係をインストール
pip install psutil requests

# テスト実行
python3 scripts/monitor.py
```

## 6. セキュリティ設定

### 6.1 ファイアウォール設定

```bash
# UFWを有効化
sudo ufw enable

# 必要なポートを開放
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443

# 状態確認
sudo ufw status
```

### 6.2 SSL証明書の設定

Let's Encryptを使用する場合：

```bash
# Certbotをインストール
sudo apt install certbot python3-certbot-nginx

# SSL証明書を取得
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# 自動更新を設定
sudo crontab -e
# 以下を追加: 0 12 * * * /usr/bin/certbot renew --quiet
```

## 7. 動作確認

### 7.1 基本動作確認

```bash
# ヘルスチェック
curl -f https://yourdomain.com/health/

# アプリケーション確認
curl -f https://yourdomain.com/

# ログ確認
tail -f logs/django.log
tail -f logs/gunicorn_error.log
```

### 7.2 パフォーマンステスト

```bash
# 簡単な負荷テスト
ab -n 100 -c 10 https://yourdomain.com/

# レスポンス時間確認
curl -w "@curl-format.txt" -o /dev/null -s https://yourdomain.com/
```

## 8. 運用・保守

### 8.1 定期メンテナンス

```bash
# 週次メンテナンススクリプト
#!/bin/bash
cd /home/wakakusa/wakakusa-shift-1

# ログローテーション
sudo logrotate -f /etc/logrotate.d/wakakusa-shift

# データベース最適化
python3 manage_prod.py shell -c "
from shift_management.utils.cache import DatabaseOptimization
DatabaseOptimization.optimize_shift_queries()
"

# キャッシュクリア
python3 manage_prod.py shell -c "
from django.core.cache import cache
cache.clear()
"

# 古いバックアップ削除
find backups/ -name "wakakusa_shift_backup_*" -mtime +30 -delete

echo "週次メンテナンス完了: $(date)"
```

### 8.2 アップデート手順

```bash
# 1. メンテナンスモードを有効化
python3 manage_prod.py maintenance_mode --enable --message "システムアップデート中"

# 2. バックアップ作成
python3 scripts/backup_database.py

# 3. コードを更新
git pull origin main

# 4. 依存関係を更新
source venv/bin/activate
pip install -r requirements_production.txt

# 5. マイグレーション実行
python3 manage_prod.py migrate

# 6. 静的ファイル更新
python3 manage_prod.py collectstatic --noinput

# 7. アプリケーション再起動
sudo supervisorctl restart wakakusa-shift

# 8. 動作確認
curl -f http://localhost:8000/health/

# 9. メンテナンスモードを無効化
python3 manage_prod.py maintenance_mode --disable
```

## 9. トラブルシューティング

### 9.1 よくある問題

**問題**: アプリケーションが起動しない
```bash
# ログを確認
tail -f logs/gunicorn_error.log
tail -f logs/django.log

# プロセス状態確認
sudo supervisorctl status wakakusa-shift

# 手動起動テスト
cd /home/wakakusa/wakakusa-shift-1
source venv/bin/activate
python3 manage_prod.py runserver 0.0.0.0:8000
```

**問題**: データベース接続エラー
```bash
# MySQL接続テスト
mysql -h localhost -u wakakusa_user -p wakakusa_shift_db

# Django設定確認
python3 manage_prod.py shell -c "
from django.db import connection
print(connection.settings_dict)
"
```

**問題**: 静的ファイルが表示されない
```bash
# 静的ファイル再収集
python3 manage_prod.py collectstatic --clear --noinput

# Nginx設定確認
sudo nginx -t
sudo systemctl reload nginx
```

## 10. 監視・アラート

### 10.1 監視項目

- CPU使用率（閾値: 80%）
- メモリ使用率（閾値: 85%）
- ディスク使用率（閾値: 90%）
- アプリケーション応答時間（閾値: 3秒）
- データベース接続状態
- キャッシュ接続状態

### 10.2 アラート設定

```bash
# メール通知設定
# /etc/aliases に以下を追加
admin: your-email@example.com

# newaliases コマンドを実行
sudo newaliases
```

## 11. バックアップ・復旧

### 11.1 バックアップ戦略

- **データベース**: 毎日午前2時に自動バックアップ
- **ファイル**: 週次でフルバックアップ
- **設定ファイル**: Git管理

### 11.2 復旧手順

```bash
# データベース復旧
mysql -u wakakusa_user -p wakakusa_shift_db < backups/wakakusa_shift_backup_YYYYMMDD_HHMMSS.sql

# アプリケーション復旧
git checkout <commit-hash>
./scripts/deploy.sh production
```

## 12. セキュリティチェックリスト

- [ ] SECRET_KEYが本番用に変更済み
- [ ] DEBUG=False設定済み
- [ ] ALLOWED_HOSTSが適切に設定済み
- [ ] HTTPS強制設定済み
- [ ] セキュリティヘッダー設定済み
- [ ] ファイアウォール設定済み
- [ ] SSL証明書設定済み
- [ ] 定期バックアップ設定済み
- [ ] 監視システム設定済み
- [ ] ログ監視設定済み

---

**最終更新**: 2024年12月
**バージョン**: 1.0
**作成者**: 開発チーム 