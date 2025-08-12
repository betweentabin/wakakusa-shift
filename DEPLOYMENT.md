# 本番環境デプロイ手順 - 統合システム（シフト管理 + 栽培管理）

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

### 5. 依存関係の更新（新しいライブラリを含む）
```bash
# 新しい依存関係をインストール
pip install -r requirements.txt

# 必要に応じてシステムレベルの依存関係も確認
# Tesseract OCRがインストールされているか確認
tesseract --version
```

### 6. データベースマイグレーション
```bash
# 全てのアプリのマイグレーション状態を確認
python manage.py showmigrations

# シフト管理システムのマイグレーション
python manage.py migrate shift_management

# 栽培管理システムのマイグレーション
python manage.py migrate cultivation
```

### 7. 静的ファイルの収集
```bash
python manage.py collectstatic --noinput
```

### 8. 初期データの作成
```bash
# シフト管理の権限制御用サンプルデータ作成（初回のみ）
python manage.py setup_production

# 栽培管理システムの組織アカウント作成（初回のみ）
python manage.py create_organization_accounts

# 栽培管理システムのサンプル組織作成（必要に応じて）
python manage.py create_sample_organizations
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

### 1. システム全体の動作確認
- **メインページ**: http://162.43.31.158:8080/ にアクセス
- **シフト管理**: http://162.43.31.158:8080/shift_management/ にアクセス
- **栽培管理**: http://162.43.31.158:8080/cultivation/ にアクセス
- ログイン画面が正常に表示されることを確認

### 2. シフト管理システムの動作確認
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

### 3. 栽培管理システムの動作確認

#### 組織選択機能
- http://162.43.31.158:8080/cultivation/ にアクセス
- 組織選択画面が表示されることを確認
- 組織管理者ログイン機能の確認

#### 栽培管理機能
- レイアウト作成・編集機能の確認
- 区画管理機能の確認
- 作物管理機能の確認
- プロット（区画プロット）管理機能の確認

#### OCR機能（画像が利用可能な場合）
- 栽培レイアウトのOCR読み取り機能
- 画像アップロード・処理機能の確認

#### 3D表示機能
- Three.jsを使用した3Dフロアプラン表示の確認
- インタラクティブな操作の確認

### 4. スタッフ登録機能の確認
- 管理者でログイン
- スタッフ管理 → 新規スタッフ登録
- 権限選択カードが正常に表示・動作することを確認

### 5. 管理画面の確認
- `/admin/` にアクセス
- シフト管理のスタッフ一覧で権限種別が表示されることを確認
- 栽培管理の各モデル（Layout, Section, Plot, Crop等）が管理できることを確認

## 🛠️ トラブルシューティング

### マイグレーションエラーが発生した場合
```bash
# マイグレーション状態の確認
python manage.py showmigrations

# 特定のアプリのマイグレーションを手動実行
python manage.py migrate shift_management 0008
python manage.py migrate cultivation 0010

# マイグレーションのリセット（最終手段）
python manage.py migrate shift_management zero
python manage.py migrate shift_management
python manage.py migrate cultivation zero  
python manage.py migrate cultivation
```

### 栽培管理システム特有のエラー

#### OCR関連エラー
```bash
# Tesseract OCRのインストール確認
tesseract --version

# Ubuntu/Debianの場合
sudo apt-get install tesseract-ocr tesseract-ocr-jpn

# CentOS/RHELの場合
sudo yum install tesseract tesseract-langpack-jpn
```

#### 画像処理ライブラリエラー
```bash
# OpenCVの依存関係問題の場合
pip uninstall opencv-python
pip install opencv-python-headless

# Pillowの問題の場合
pip install --upgrade Pillow
```

#### 3D表示（Three.js）の問題
- ブラウザの開発者ツールでJavaScriptエラーをチェック
- 静的ファイルが正しく読み込まれているか確認
- Three.jsライブラリがCDNから正しく読み込まれているか確認

### 静的ファイルが読み込まれない場合
```bash
# 静的ファイルの再収集
python manage.py collectstatic --clear --noinput

# Nginxの設定確認
sudo nginx -t
sudo systemctl reload nginx

# 栽培管理システムの静的ファイルパスも確認
ls -la /path/to/static/css/
ls -la /path/to/static/js/
```

### データベース接続エラーの場合
```bash
# データベース接続テスト
python manage.py dbshell

# 設定ファイルの確認
python manage.py check --deploy

# 新しいアプリ（cultivation）のテーブル作成確認
python manage.py shell
>>> from cultivation.models import *
>>> CultivationLayout.objects.count()
```

### 組織アカウント関連のエラー
```bash
# 組織アカウントの作成状況確認
python manage.py shell
>>> from shift_management.models import Organization
>>> Organization.objects.all()

# 組織アカウント再作成
python manage.py create_organization_accounts --force
```

## 📊 ☑️ 新機能の説明

### 1. シフト管理システム（既存機能）
#### 権限制御システム
- **4段階の権限レベル**: 利用者、アルバイト、職員、管理者
- **データベースレベルでの制御**: セキュアな権限管理
- **直感的なUI**: アイコンと色分けによる分かりやすい表示

#### 新しいフィールド
- `Staff.role_type`: 権限種別フィールド
- デフォルト値: `user`（利用者）

### 2. 栽培管理システム（新機能）
#### 主要機能
- **栽培レイアウト管理**: 施設の栽培レイアウトを作成・管理
- **区画管理**: レイアウト内の区画を管理
- **作物管理**: 栽培する作物の品種情報を管理
- **プロット管理**: 各区画内の細かい栽培区画を管理

#### OCR機能
- **画像読み取り**: レイアウト図面からのOCR読み取り
- **自動区画認識**: 画像から区画情報を自動抽出
- **日本語対応**: Tesseract OCRによる日本語テキスト認識

#### 3D表示機能
- **Three.js使用**: インタラクティブな3Dフロアプラン
- **リアルタイム表示**: 動的なレイアウト表示
- **操作性**: マウスによる視点操作

#### 組織管理
- **マルチ組織対応**: 複数の栽培組織を管理
- **組織別データ分離**: セキュアなデータ管理
- **管理者権限**: 組織ごとの管理者設定

#### 技術仕様
- **新しい依存関係**: OpenCV、Tesseract OCR、pandas等
- **画像処理**: Pillow、scikit-image使用
- **PDF処理**: PyPDF2、pdfplumber対応
- **データ分析**: pandas、numpy使用

### 3. 統合システム
- **共通認証**: 両システム間での認証情報共有
- **統一UI**: 一貫したユーザーインターフェース
- **管理者機能**: Django管理画面での統合管理

## 🔄 ロールバック手順（問題が発生した場合）

### 完全ロールバック（栽培管理システム導入前に戻す）
```bash
# 前のバージョンに戻す（栽培管理システム導入前）
git checkout cac1887  # 権限制御システムのコミット

# 栽培管理システムのマイグレーションを完全に戻す
python manage.py migrate cultivation zero

# シフト管理システムのマイグレーションを前のバージョンに戻す
python manage.py migrate shift_management 0007

# 静的ファイルの再収集
python manage.py collectstatic --noinput

# Webサーバーの再起動
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

### 部分ロールバック（栽培管理システムのみ無効化）
```bash
# settings.pyから栽培管理アプリを一時的に削除
python manage.py shell
>>> # INSTALLED_APPSから'cultivation'を除外する設定変更

# URLルーティングから栽培管理を削除
# core/urls.pyの cultivation URLパターンをコメントアウト

# 静的ファイルの再収集
python manage.py collectstatic --noinput

# Webサーバーの再起動
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

## 📝 注意事項

1. **バックアップ**: デプロイ前に必ずデータベースのバックアップを取得
   ```bash
   # SQLiteの場合
   cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d_%H%M%S)
   
   # PostgreSQLの場合
   pg_dump database_name > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **メンテナンス時間**: ユーザーが少ない時間帯に実施

3. **段階的デプロイ**: 
   - 先にシフト管理システムの動作を確認
   - 栽培管理システムの動作を確認
   - 最後に統合動作を確認

4. **動作確認**: 各権限レベル・各システムでの動作を必ず確認

5. **システム要件確認**: 
   - Tesseract OCRのインストール状況
   - Python依存関係の互換性
   - ディスク容量（画像ファイル保存用）

6. **ログ監視**: デプロイ後はエラーログを監視

7. **セキュリティ**: 
   - 画像アップロード機能のファイルタイプ制限確認
   - OCR処理のリソース使用量監視

## 📊 パフォーマンス監視

### 監視すべき項目
- **CPU使用率**: OCR処理時の負荷
- **メモリ使用量**: 画像処理・3D表示時
- **ディスク容量**: アップロード画像の蓄積
- **レスポンス時間**: 特に栽培管理システムの重い処理

### 最適化のヒント
```bash
# 画像ファイルの定期クリーンアップ設定
# 古いOCR結果ファイルの削除
find /path/to/media/ -name "*.jpg" -mtime +30 -delete

# データベースの最適化
python manage.py optimize_db  # カスタムコマンドがある場合
```

## 📞 サポート

問題が発生した場合は、以下のログを確認：
- **Djangoアプリケーションログ**: アプリケーション固有のエラー
- **Webサーバーログ（Nginx/Apache）**: HTTP関連のエラー
- **システムログ（systemctl status）**: サービス起動関連のエラー
- **OCR処理ログ**: Tesseract関連のエラー（ある場合）
- **画像処理ログ**: OpenCV/Pillow関連のエラー（ある場合）

### ログ確認コマンド
```bash
# アプリケーションログ
tail -f /path/to/logs/django.log

# Nginx/Apacheログ
tail -f /var/log/nginx/error.log
tail -f /var/log/nginx/access.log

# システムログ
journalctl -u gunicorn -f
systemctl status nginx
``` 


