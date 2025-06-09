# Xserver本番環境デプロイメント手順書

## 📋 事前準備

### 1. Xserverアカウント情報の確認
- [ ] サーバーアカウント名
- [ ] ドメイン名
- [ ] MySQLデータベース情報
- [ ] FTPアカウント情報

### 2. 必要なソフトウェア
- [ ] FTPクライアント（FileZilla等）
- [ ] テキストエディタ
- [ ] ターミナル/コマンドプロンプト

## 🚀 デプロイメント手順

### Step 1: ローカル環境での準備

1. **本番環境用パッケージのインストール**
```bash
pip install -r requirements_production.txt
```

2. **デプロイメントスクリプトの実行**
```bash
python deploy.py
```

3. **静的ファイルの収集確認**
```bash
python manage.py collectstatic --settings=core.settings_production
```

### Step 2: 環境変数の設定

1. **env_template.txtをコピーして.envファイルを作成**
```bash
cp env_template.txt .env
```

2. **.envファイルを編集して実際の値を設定**
```
DJANGO_SECRET_KEY=実際のシークレットキー
DB_NAME=実際のデータベース名
DB_USER=実際のデータベースユーザー
DB_PASSWORD=実際のデータベースパスワード
EMAIL_HOST_USER=実際のメールアドレス
EMAIL_HOST_PASSWORD=実際のメールパスワード
ALLOWED_HOSTS=実際のドメイン名
```

### Step 3: Xserverでのデータベース作成

1. **Xserverパネルにログイン**
2. **MySQL設定 → MySQL追加**
3. **データベース名、ユーザー名、パスワードを設定**
4. **文字コードをutf8mb4に設定**

### Step 4: ファイルのアップロード

1. **FTPクライアントでXserverに接続**
2. **以下のファイル・フォルダをアップロード**
   - プロジェクト全体（wakakusa-shift/）
   - .env ファイル
   - django.cgi ファイル
   - .htaccess ファイル

3. **アップロード先ディレクトリ構成**
```
/home/your-account/your-domain.com/
├── public_html/
│   ├── .htaccess
│   ├── cgi-bin/
│   │   └── django.cgi
│   ├── staticfiles/ (collectstaticで生成)
│   └── media/
└── wakakusa-shift/ (プロジェクトフォルダ)
    ├── core/
    ├── shift_management/
    ├── templates/
    ├── static/
    ├── .env
    └── manage.py
```

### Step 5: ファイル権限の設定

1. **django.cgiの実行権限を設定**
```bash
chmod 755 cgi-bin/django.cgi
```

2. **必要なディレクトリの権限設定**
```bash
chmod 755 wakakusa-shift/
chmod 755 wakakusa-shift/logs/
chmod 755 wakakusa-shift/cache/
chmod 755 public_html/staticfiles/
chmod 755 public_html/media/
```

### Step 6: 設定ファイルの調整

1. **django.cgiのパス修正**
```python
project_path = '/home/your-account/your-domain.com/wakakusa-shift'
```

2. **.htaccessのパス修正**
```apache
Alias /static/ /home/your-account/your-domain.com/public_html/staticfiles/
Alias /media/ /home/your-account/your-domain.com/public_html/media/
```

3. **settings_production.pyの調整**
```python
ALLOWED_HOSTS = ['your-actual-domain.com', 'www.your-actual-domain.com']
```

### Step 7: データベースマイグレーション

1. **SSH接続（可能な場合）**
```bash
cd /home/your-account/your-domain.com/wakakusa-shift
python manage.py migrate --settings=core.settings_production
python manage.py createsuperuser --settings=core.settings_production
```

2. **SSH接続不可の場合**
- ローカルでマイグレーションファイルを生成
- データベースを手動でエクスポート/インポート

### Step 8: 動作確認

1. **ブラウザでアクセス**
   - https://your-domain.com/
   - 管理画面: https://your-domain.com/admin/

2. **確認項目**
   - [ ] トップページが表示される
   - [ ] 静的ファイル（CSS/JS）が読み込まれる
   - [ ] 管理画面にログインできる
   - [ ] データベース操作が正常に動作する

## 🔧 トラブルシューティング

### よくある問題と解決方法

1. **500 Internal Server Error**
   - django.cgiの権限確認 (755)
   - パスの設定確認
   - .envファイルの存在確認

2. **静的ファイルが読み込まれない**
   - collectstaticの実行確認
   - .htaccessのAlias設定確認
   - ファイル権限確認

3. **データベース接続エラー**
   - データベース情報の確認
   - MySQLサーバーの稼働確認
   - 文字コード設定確認

4. **ImportError**
   - 必要なパッケージのインストール確認
   - Pythonパスの設定確認

## 📝 メンテナンス

### 定期的な作業

1. **ログファイルの確認**
```bash
tail -f logs/django.log
```

2. **静的ファイルの更新**
```bash
python manage.py collectstatic --settings=core.settings_production
```

3. **データベースバックアップ**
```bash
mysqldump -u username -p database_name > backup.sql
```

### セキュリティ更新

1. **Djangoのアップデート**
2. **依存パッケージの更新**
3. **SSL証明書の更新**

## 📞 サポート

問題が発生した場合は、以下を確認してください：

1. エラーログの内容
2. 設定ファイルの内容
3. ファイル権限
4. データベース接続情報

---

**注意**: 本番環境では必ずSSL証明書を設定し、セキュリティ設定を有効にしてください。 