# サブドメイン管理計画
## xrosspoint-bpo.com ドメイン活用

### 🌐 推奨サブドメイン構成

#### 1. **メインサービス**
- `shift.xrosspoint-bpo.com` - シフト管理システム（メイン）
- `admin.xrosspoint-bpo.com` - 管理者専用画面
- `api.xrosspoint-bpo.com` - API専用エンドポイント

#### 2. **環境別サブドメイン**
- `dev.xrosspoint-bpo.com` - 開発環境
- `staging.xrosspoint-bpo.com` - ステージング環境
- `prod.xrosspoint-bpo.com` - 本番環境

#### 3. **機能別サブドメイン**
- `staff.xrosspoint-bpo.com` - スタッフ専用画面
- `reports.xrosspoint-bpo.com` - レポート・分析画面
- `docs.xrosspoint-bpo.com` - ドキュメント・ヘルプ

### 🔧 DNS設定（必要な作業）

#### A. **DNSレコード設定**
```
# メインドメイン
xrosspoint-bpo.com.          A    162.43.31.158

# サブドメイン（ワイルドカード）
*.xrosspoint-bpo.com.        A    162.43.31.158

# 個別設定（推奨）
shift.xrosspoint-bpo.com.    A    162.43.31.158
admin.xrosspoint-bpo.com.    A    162.43.31.158
api.xrosspoint-bpo.com.      A    162.43.31.158
```

#### B. **SSL証明書対応**
- ワイルドカード証明書: `*.xrosspoint-bpo.com`
- Let's Encrypt対応
- 自動更新設定

### 🚀 実装手順

#### Phase 1: DNS設定
1. ドメインレジストラでDNS設定
2. A レコードの追加
3. DNS伝播の確認（24-48時間）

#### Phase 2: SSL証明書取得
```bash
# Let's Encrypt証明書取得
certbot certonly --standalone -d xrosspoint-bpo.com -d *.xrosspoint-bpo.com
```

#### Phase 3: Nginx設定
```nginx
# /etc/nginx/sites-available/xrosspoint-bpo
server {
    listen 80;
    server_name xrosspoint-bpo.com *.xrosspoint-bpo.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name shift.xrosspoint-bpo.com;
    
    ssl_certificate /etc/letsencrypt/live/xrosspoint-bpo.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/xrosspoint-bpo.com/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Phase 4: Django設定更新
```python
# settings/production.py
ALLOWED_HOSTS = [
    'xrosspoint-bpo.com',
    '*.xrosspoint-bpo.com',
    'shift.xrosspoint-bpo.com',
    'admin.xrosspoint-bpo.com',
    'api.xrosspoint-bpo.com',
    '162.43.31.158',
]

# サブドメイン別設定
SUBDOMAIN_ROUTING = {
    'shift': 'shift_management.urls',
    'admin': 'admin_panel.urls',
    'api': 'api.urls',
}
```

### 🔒 セキュリティ設定

#### A. **HTTPS強制**
```python
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

#### B. **CORS設定**
```python
CORS_ALLOWED_ORIGINS = [
    "https://xrosspoint-bpo.com",
    "https://shift.xrosspoint-bpo.com",
    "https://admin.xrosspoint-bpo.com",
]
```

### 📊 監視・ログ設定

#### A. **サブドメイン別ログ**
```python
LOGGING = {
    'handlers': {
        'shift_file': {
            'filename': '/var/log/wakakusa_shift/shift.log',
        },
        'admin_file': {
            'filename': '/var/log/wakakusa_shift/admin.log',
        },
    }
}
```

#### B. **ヘルスチェック**
- `https://shift.xrosspoint-bpo.com/health/`
- `https://admin.xrosspoint-bpo.com/health/`
- `https://api.xrosspoint-bpo.com/health/`

### 🎯 現在の状況

#### ✅ 完了済み
- SSL証明書作成（セルフサイン）
- ALLOWED_HOSTS設定
- 基本的なHTTPS設定

#### 🔄 次のステップ
1. **DNS設定** - ドメインレジストラでの設定
2. **Let's Encrypt証明書** - 正式なSSL証明書取得
3. **Nginx設定** - リバースプロキシとサブドメインルーティング
4. **サブドメイン別機能** - 機能分離とルーティング

### 💡 運用上の利点

1. **機能分離**: 各サービスを独立して管理
2. **セキュリティ**: サブドメイン別アクセス制御
3. **スケーラビリティ**: 将来的な機能拡張に対応
4. **ユーザビリティ**: 直感的なURL構造
5. **SEO対応**: 検索エンジン最適化

### 📞 次のアクション

1. **DNS設定の実行**
   - ドメインレジストラにログイン
   - A レコードの追加
   - 設定の確認

2. **証明書取得の準備**
   - sudo権限の取得
   - certbotのインストール
   - 自動更新の設定

3. **Nginx設定**
   - インストールと設定
   - サブドメインルーティング
   - SSL設定

この計画に沿って進めることで、プロフェッショナルなサブドメイン管理システムを構築できます。 