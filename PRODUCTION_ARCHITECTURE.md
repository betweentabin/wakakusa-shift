# わかくさシフト 本番環境アーキテクチャ設計書

## 概要

本ドキュメントは、わかくさシフト管理システムの本番環境における設計思想、アーキテクチャ、および運用方針を記載します。

## アーキテクチャ概要

### システム構成

```
[ユーザー] 
    ↓ HTTPS
[ロードバランサー/CDN]
    ↓
[Webサーバー (Apache/Nginx)]
    ↓ WSGI
[Djangoアプリケーション (Gunicorn)]
    ↓
[データベース (MySQL)] + [キャッシュ (Redis)]
    ↓
[ファイルストレージ] + [ログ管理]
```

### 技術スタック

- **フレームワーク**: Django 5.2.1
- **データベース**: MySQL 8.0+
- **キャッシュ**: Redis 7.0+
- **Webサーバー**: Apache/Nginx + Gunicorn
- **言語**: Python 3.11+
- **OS**: Linux (Ubuntu 22.04 LTS推奨)

## 設定管理

### 環境別設定

```
core/
├── settings/
│   ├── __init__.py
│   ├── base.py          # 共通設定
│   ├── development.py   # 開発環境
│   └── production.py    # 本番環境
```

### 環境変数管理

本番環境では以下の環境変数が必要：

```bash
# Django設定
DJANGO_SETTINGS_MODULE=core.settings.production
DJANGO_SECRET_KEY=your-super-secret-key

# データベース
DB_NAME=wakakusa_shift_db
DB_USER=wakakusa_user
DB_PASSWORD=secure-password
DB_HOST=localhost
DB_PORT=3306

# セキュリティ
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
USE_HTTPS=true

# キャッシュ
REDIS_URL=redis://localhost:6379/1

# メール
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=app-password
```

## セキュリティ設計

### 1. 認証・認可

- Django標準認証システム
- セッションベース認証
- 権限レベル：管理者（superuser）、一般スタッフ（staff）

### 2. セキュリティヘッダー

```python
# SecurityHeadersMiddleware により自動設定
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'...
```

### 3. レート制限

- 一般リクエスト: 100回/分
- ログイン試行: 5回/15分
- IPベースの制限

### 4. HTTPS強制

```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

## パフォーマンス最適化

### 1. データベース最適化

```sql
-- 自動作成されるインデックス
CREATE INDEX idx_shift_date_staff ON shift_management_shift(date, staff_id);
CREATE INDEX idx_shift_date_range ON shift_management_shift(date);
CREATE INDEX idx_staff_active ON shift_management_staff(is_active);
```

### 2. キャッシュ戦略

```python
# キャッシュ階層
- L1: アプリケーションレベル（Django ORM）
- L2: Redisキャッシュ（5-10分）
- L3: データベース
```

### 3. 静的ファイル配信

```python
# WhiteNoise + ManifestStaticFilesStorage
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
```

## 監視・ログ管理

### 1. ヘルスチェックエンドポイント

- `/health/` - システム全体の健康状態
- `/ready/` - アプリケーション準備状態
- `/live/` - アプリケーション生存確認

### 2. ログ管理

```
logs/
├── django.log          # 一般ログ
├── django_error.log    # エラーログ
└── audit.log          # 監査ログ
```

### 3. 監査ログ

重要な操作を自動記録：
- ログイン/ログアウト
- データ変更操作
- 管理者操作

## バックアップ戦略

### 1. データベースバックアップ

```bash
# 自動バックアップ（日次）
0 2 * * * /path/to/project/scripts/backup_database.py

# 保持期間: 30日
# 形式: wakakusa_shift_backup_YYYYMMDD_HHMMSS.sql
```

### 2. ファイルバックアップ

- 静的ファイル
- メディアファイル
- 設定ファイル

## デプロイメント

### 1. 自動デプロイスクリプト

```bash
# 本番環境デプロイ
./scripts/deploy.sh production

# ステージング環境デプロイ
./scripts/deploy.sh staging
```

### 2. デプロイフロー

1. 環境チェック
2. バックアップ作成
3. 依存関係更新
4. データベースマイグレーション
5. 静的ファイル収集
6. パフォーマンス最適化
7. ヘルスチェック

## 運用・保守

### 1. 定期メンテナンス

```bash
# 週次実行推奨
- ログローテーション
- 古いバックアップファイル削除
- データベース最適化
- キャッシュクリア
```

### 2. 監視項目

- CPU使用率
- メモリ使用率
- ディスク容量
- データベース接続数
- レスポンス時間
- エラー率

### 3. アラート設定

- ディスク使用率 > 90%
- エラー率 > 5%
- レスポンス時間 > 3秒
- データベース接続エラー

## スケーラビリティ

### 1. 水平スケーリング

```
[ロードバランサー]
    ├── [Djangoサーバー1]
    ├── [Djangoサーバー2]
    └── [Djangoサーバー3]
         ↓
    [共有データベース] + [共有Redis]
```

### 2. 垂直スケーリング

- CPU: 2コア → 4コア
- メモリ: 4GB → 8GB
- ストレージ: SSD推奨

## セキュリティチェックリスト

### デプロイ前チェック

- [ ] SECRET_KEYが本番用に変更済み
- [ ] DEBUG=False設定済み
- [ ] ALLOWED_HOSTSが適切に設定済み
- [ ] データベース認証情報が安全
- [ ] HTTPS設定が有効
- [ ] セキュリティヘッダーが設定済み
- [ ] レート制限が有効
- [ ] 監査ログが有効

### 定期セキュリティチェック

- [ ] 依存関係の脆弱性チェック
- [ ] ログの異常確認
- [ ] 不正アクセス試行の確認
- [ ] SSL証明書の有効期限確認

## トラブルシューティング

### よくある問題と対処法

1. **データベース接続エラー**
   ```bash
   # 接続確認
   mysql -h $DB_HOST -u $DB_USER -p $DB_NAME
   ```

2. **静的ファイルが表示されない**
   ```bash
   # 静的ファイル再収集
   python manage_prod.py collectstatic --clear
   ```

3. **キャッシュ関連の問題**
   ```bash
   # Redisキャッシュクリア
   redis-cli FLUSHDB
   ```

4. **パフォーマンス問題**
   ```bash
   # データベース最適化
   python -c "from shift_management.utils.cache import DatabaseOptimization; DatabaseOptimization.create_indexes()"
   ```

## 今後の拡張計画

### Phase 1: 基本機能強化
- 通知機能（メール/SMS）
- レポート機能強化
- モバイルアプリ対応

### Phase 2: 高度な機能
- AI による自動シフト生成
- 多言語対応
- API公開

### Phase 3: エンタープライズ機能
- マルチテナント対応
- 高可用性構成
- 災害復旧対応

## 連絡先・サポート

- 開発チーム: dev@wakakusa-shift.com
- 運用チーム: ops@wakakusa-shift.com
- 緊急連絡: emergency@wakakusa-shift.com

---

**最終更新**: 2024年12月
**バージョン**: 1.0
**作成者**: 開発チーム 