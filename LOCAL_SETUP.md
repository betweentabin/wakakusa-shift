# wakakusa-shift ローカル環境構築手順

## 📋 前提条件

- Python 3.8以上がインストールされていること
- Gitがインストールされていること

## 🚀 セットアップ手順

### 1. リポジトリのクローン

```bash
git clone https://github.com/betweentabin/wakakusa-shift.git
cd wakakusa-shift
```

### 2. 仮想環境の作成・有効化

#### Windows
```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS/Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. データベースのセットアップ

```bash
# マイグレーションファイルの作成
python manage.py makemigrations

# データベースの作成・更新
python manage.py migrate

# 管理者ユーザーの作成（オプション）
python manage.py createsuperuser
```

### 5. 静的ファイルの収集

```bash
python manage.py collectstatic --noinput
```

## 🖥️ ローカルサーバーの起動

### 開発サーバーの起動

```bash
python manage.py runserver
```

### アクセス方法

ブラウザで以下のURLにアクセス：
- **メインページ**: http://127.0.0.1:8000/
- **管理画面**: http://127.0.0.1:8000/admin/

## 📱 動作確認

### 基本機能の確認

1. **カレンダー表示**
   - メインページでシフトカレンダーが表示されること
   - 月・週・日・リスト表示の切り替えができること

2. **スタッフ管理**
   - スタッフ一覧ページ（/staff/）にアクセス
   - 新規スタッフの登録・編集・削除

3. **シフト管理**
   - 新規シフト登録（/shift/create/）
   - 一括シフト登録（/shift/bulk-create/）
   - 事由登録（/shift/reason/create/）

4. **レスポンシブ対応**
   - ブラウザの開発者ツールでモバイル表示を確認
   - 画面サイズに応じたレイアウト変更

## 🔧 トラブルシューティング

### よくある問題と解決方法

#### 1. ポート競合エラー
```
Error: That port is already in use.
```
**解決方法**: 別のポートを指定
```bash
python manage.py runserver 8001
```

#### 2. パッケージインストールエラー
```
ERROR: Could not install packages
```
**解決方法**: pipのアップグレード
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. データベースエラー
```
django.db.utils.OperationalError
```
**解決方法**: データベースの再作成
```bash
rm db.sqlite3
python manage.py migrate
```

#### 4. 静的ファイルが読み込まれない
**解決方法**: 静的ファイルの再収集
```bash
python manage.py collectstatic --clear --noinput
```

## 📂 プロジェクト構造

```
wakakusa-shift/
├── core/                    # プロジェクト設定
│   ├── settings.py         # 開発環境設定
│   ├── settings_production.py  # 本番環境設定
│   ├── urls.py             # URLルーティング
│   └── wsgi.py             # WSGIアプリケーション
├── shift_management/        # メインアプリケーション
│   ├── models.py           # データモデル
│   ├── views.py            # ビュー関数
│   ├── forms.py            # フォーム定義
│   ├── urls.py             # アプリURL
│   └── templates/          # テンプレート
├── static/                  # 静的ファイル
│   └── css/                # スタイルシート
├── templates/               # 共通テンプレート
├── requirements.txt         # 開発環境用パッケージ
├── requirements_production.txt  # 本番環境用パッケージ
└── manage.py               # Django管理コマンド
```

## 🎯 開発時のヒント

### 1. デバッグモード
`core/settings.py`で`DEBUG = True`に設定されていることを確認

### 2. ログの確認
エラーが発生した場合は、ターミナルのログを確認

### 3. データベースの初期化
テストデータを追加したい場合：
```bash
python manage.py shell
```

### 4. 管理画面の活用
- スタッフ、シフト種別、シフトの管理が可能
- http://127.0.0.1:8000/admin/ でアクセス

## 📞 サポート

問題が解決しない場合は、以下を確認してください：
- Python、Djangoのバージョン
- エラーメッセージの詳細
- 実行環境（OS、ブラウザ）

---

**Happy Coding! 🚀** 