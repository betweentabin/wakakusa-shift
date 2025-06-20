# 本番環境デプロイ手順 - 権限制御システム

## 🚀 本番環境への反映手順

### 1. 本番サーバーへの接続
```bash
# 本番サーバーにSSH接続
ssh user@162.43.31.158
```

### 2. アプリケーションディレクトリに移動
```bash
cd /path/to/wakakusa-shift-1
```

### 3. 最新コードの取得
```bash
# 最新のコードをプル
git fetch origin
git checkout new_main
git pull origin new_main
```

### 4. 仮想環境の有効化
```bash
# 仮想環境を有効化
source venv/bin/activate
```

### 5. 依存関係の更新（必要に応じて）
```bash
pip install -r requirements.txt
```

### 6. データベースマイグレーション
```bash
# マイグレーションファイルの確認
python manage.py showmigrations shift_management

# マイグレーションの実行
python manage.py migrate
```

### 7. 静的ファイルの収集
```bash
python manage.py collectstatic --noinput
```

### 8. 権限制御用のサンプルデータ作成（初回のみ）
```bash
# サンプルデータを作成（既存データがある場合はスキップされます）
python manage.py setup_production
```

### 9. Webサーバーの再起動
```bash
# Gunicorn/uWSGIの再起動（使用しているWebサーバーに応じて）
sudo systemctl restart gunicorn
# または
sudo systemctl restart uwsgi

# Nginxの再起動
sudo systemctl restart nginx
```

## 🔍 デプロイ後の確認事項

### 1. アプリケーションの動作確認
- http://162.43.31.158:8080/ にアクセス
- ログイン画面が正常に表示されることを確認

### 2. 権限制御の動作確認
以下のテストアカウントで動作確認：

#### 管理者アカウント
- ユーザー名: `manager`
- パスワード: `password123`
- 確認項目: 全スタッフのシフト表示、承認パネル表示

#### 職員アカウント
- ユーザー名: `staff`
- パスワード: `password123`
- 確認項目: 職員・アルバイトのシフト表示

#### アルバイトアカウント
- ユーザー名: `parttime1` または `parttime2`
- パスワード: `password123`
- 確認項目: アルバイトのシフトのみ表示

#### 利用者アカウント
- ユーザー名: `user`
- パスワード: `password123`
- 確認項目: 自分のシフトのみ表示

### 3. スタッフ登録機能の確認
- 管理者でログイン
- スタッフ管理 → 新規スタッフ登録
- 権限選択カードが正常に表示・動作することを確認

### 4. 管理画面の確認
- `/admin/` にアクセス
- スタッフ一覧で権限種別が表示されることを確認

## 🛠️ トラブルシューティング

### マイグレーションエラーが発生した場合
```bash
# マイグレーション状態の確認
python manage.py showmigrations

# 特定のマイグレーションを手動実行
python manage.py migrate shift_management 0007

# マイグレーションのリセット（最終手段）
python manage.py migrate shift_management zero
python manage.py migrate shift_management
```

### 静的ファイルが読み込まれない場合
```bash
# 静的ファイルの再収集
python manage.py collectstatic --clear --noinput

# Nginxの設定確認
sudo nginx -t
sudo systemctl reload nginx
```

### データベース接続エラーの場合
```bash
# データベース接続テスト
python manage.py dbshell

# 設定ファイルの確認
python manage.py check --deploy
```

## 📊 新機能の説明

### 権限制御システム
- **4段階の権限レベル**: 利用者、アルバイト、職員、管理者
- **データベースレベルでの制御**: セキュアな権限管理
- **直感的なUI**: アイコンと色分けによる分かりやすい表示

### 新しいフィールド
- `Staff.role_type`: 権限種別フィールド
- デフォルト値: `user`（利用者）

### 新しいテストアカウント
上記の確認事項で記載したアカウントが自動作成されます。

## 🔄 ロールバック手順（問題が発生した場合）

```bash
# 前のバージョンに戻す
git checkout 前のコミットハッシュ

# マイグレーションを戻す
python manage.py migrate shift_management 0006

# 静的ファイルの再収集
python manage.py collectstatic --noinput

# Webサーバーの再起動
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

## 📝 注意事項

1. **バックアップ**: デプロイ前に必ずデータベースのバックアップを取得
2. **メンテナンス時間**: ユーザーが少ない時間帯に実施
3. **動作確認**: 各権限レベルでの動作を必ず確認
4. **ログ監視**: デプロイ後はエラーログを監視

## 📞 サポート

問題が発生した場合は、以下のログを確認：
- Djangoアプリケーションログ
- Webサーバーログ（Nginx/Apache）
- システムログ（systemctl status） 