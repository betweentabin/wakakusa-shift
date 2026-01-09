# わかくさシフト管理システム

## 概要

わかくさシフト管理システムは、医療・介護施設向けのシフト管理Webアプリケーションです。
Django 5.2.1をベースに構築され、直感的なカレンダーインターフェースでシフトの作成・編集・確認が可能です。

## 主な機能

- 📅 **カレンダー形式のシフト表示**
- 👥 **スタッフ管理**（管理者・一般スタッフの権限分離）
- 🔄 **シフト種別管理**（早番・遅番・夜勤など）
- 📊 **シフトテンプレート機能**
- 📱 **レスポンシブ対応**（PC・タブレット・スマートフォン）
- 🔐 **認証・認可システム**
- 📈 **レポート・エクスポート機能**

## 技術スタック

- **Backend**: Django 5.2.1, Python 3.11+
- **Database**: SQLite (開発), MySQL (本番)
- **Frontend**: Bootstrap 5, FullCalendar 6.1.8
- **Cache**: Redis (本番環境)
- **Web Server**: Gunicorn + Nginx (本番環境)

## クイックスタート

### 開発環境

```bash
# リポジトリをクローン
git clone <repository-url>
cd wakakusa-shift-1

# 仮想環境を作成・アクティベート
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt

# データベースマイグレーション
python manage.py migrate

# スーパーユーザーを作成（ユーザー名: admin固定）
python manage.py createsuperuser

# 開発サーバーを起動
python manage.py runserver 0.0.0.0:8020
```

ブラウザで `http://localhost:8020` にアクセス

### 本番環境

詳細は [PRODUCTION_SETUP_GUIDE.md](PRODUCTION_SETUP_GUIDE.md) を参照してください。

```bash
# 環境変数を設定
cp env.example .env
# .envファイルを編集

# 自動デプロイスクリプトを実行
./scripts/deploy.sh production
```

## ディレクトリ構成

```
wakakusa-shift-1/
├── core/                          # Django設定
│   ├── settings/                  # 環境別設定
│   │   ├── base.py               # 共通設定
│   │   ├── development.py        # 開発環境
│   │   └── production.py         # 本番環境
│   ├── urls.py
│   ├── wsgi.py
│   └── wsgi_production.py        # 本番用WSGI
├── shift_management/              # メインアプリケーション
│   ├── models.py                 # データモデル
│   ├── views/                    # ビュー
│   ├── templates/                # テンプレート
│   ├── management/               # 管理コマンド
│   ├── middleware/               # カスタムミドルウェア
│   └── utils/                    # ユーティリティ
├── templates/                     # 共通テンプレート
├── static/                       # 静的ファイル
├── scripts/                      # 運用スクリプト
│   ├── deploy.sh                # デプロイスクリプト
│   ├── backup_database.py       # バックアップスクリプト
│   ├── monitor.py               # 監視スクリプト
│   └── crontab.example          # cron設定例
├── requirements.txt              # 開発環境依存関係
├── requirements_production.txt   # 本番環境依存関係
├── manage.py                     # Django管理スクリプト
├── manage_prod.py               # 本番環境管理スクリプト
├── gunicorn.conf.py             # Gunicorn設定
└── env.example                  # 環境変数テンプレート
```

## 使用方法

### 基本操作

1. **ログイン**: 管理者または一般スタッフでログイン
2. **シフト確認**: カレンダーでシフトを確認
3. **シフト作成**: 管理者はシフトの作成・編集が可能
4. **スタッフ管理**: 管理者はスタッフの追加・編集が可能

### 権限レベル

- **管理者 (admin)**: 全機能にアクセス可能
- **一般スタッフ (staff)**: シフト確認のみ（読み取り専用）

### 管理コマンド

```bash
# 本番環境初期セットアップ
python manage_prod.py setup_production --create-superuser --create-sample-data

# メンテナンスモード制御
python manage_prod.py maintenance_mode --enable
python manage_prod.py maintenance_mode --disable

# データベースバックアップ
python scripts/backup_database.py

# システム監視
python scripts/monitor.py
```

## API エンドポイント

### ヘルスチェック

- `GET /health/` - システム全体の健康状態
- `GET /ready/` - アプリケーション準備状態
- `GET /live/` - アプリケーション生存確認

### シフト管理

- `GET /api/shifts/` - シフト一覧取得
- `POST /api/shift/update/` - シフト更新
- `POST /api/shift/delete/` - シフト削除

## 開発

### 開発環境のセットアップ

詳細は [LOCAL_SETUP.md](LOCAL_SETUP.md) を参照してください。

### テスト実行

```bash
python manage.py test
```

### コードスタイル

```bash
# flake8でコードチェック
flake8 .

# blackでコードフォーマット
black .
```

## デプロイメント

### 開発環境から本番環境への移行

1. 環境変数の設定（`.env`ファイル）
2. データベースの設定（MySQL）
3. 自動デプロイスクリプトの実行
4. Webサーバーの設定（Nginx + Gunicorn）
5. 監視・ログ設定

詳細は [PRODUCTION_SETUP_GUIDE.md](PRODUCTION_SETUP_GUIDE.md) を参照してください。

## 監視・運用

### 監視項目

- CPU・メモリ・ディスク使用率
- アプリケーション応答時間
- データベース・キャッシュ接続状態
- エラーログ監視

### バックアップ

- データベース: 毎日自動バックアップ
- ファイル: 週次バックアップ
- 保持期間: 30日

## トラブルシューティング

### よくある問題

1. **アプリケーションが起動しない**
   - ログファイルを確認: `tail -f logs/django.log`
   - 依存関係を再インストール: `pip install -r requirements.txt`

2. **データベース接続エラー**
   - 設定を確認: `python manage.py shell`
   - MySQL接続テスト: `mysql -u user -p database`

3. **静的ファイルが表示されない**
   - 静的ファイル再収集: `python manage.py collectstatic`

## ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。

## サポート

- 開発チーム: dev@wakakusa-shift.com
- 運用チーム: ops@wakakusa-shift.com
- 緊急連絡: emergency@wakakusa-shift.com

---

**最終更新**: 2024年12月  
**バージョン**: 1.0  
**作成者**: 開発チーム 