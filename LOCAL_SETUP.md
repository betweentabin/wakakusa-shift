# 🚀 わかくさシフト ローカル実行手順

## 📥 ダウンロード・準備

```bash
# 1. プロジェクトをダウンロード
git clone <repository-url>
cd wakakusa-shift-1

# 2. 仮想環境を作成
python3 -m venv venv

# 3. 仮想環境を有効化
# Windows の場合:
venv\Scripts\activate
# Mac/Linux の場合:
source venv/bin/activate

# 4. 必要なパッケージをインストール
pip install -r requirements.txt
```

## 🗄️ データベース準備

```bash
# データベースを作成
python manage.py migrate

# 🔐 管理者ユーザーを作成（初回のみ、ユーザー名: admin固定）
python manage.py createsuperuser
```

## ▶️ サーバー起動

```bash
# サーバーを起動（ローカルのみ）
python manage.py runserver

# 📱 携帯・他のデバイスからもアクセスしたい場合
python manage.py runserver 0.0.0.0:8020
```

## 🌐 ブラウザで確認

### パソコンから
ブラウザで http://localhost:8020/ にアクセス

### 📱 携帯・他のデバイスから
1. パソコンのIPアドレスを確認
   ```bash
   # Mac/Linuxの場合
   ifconfig | grep "inet " | grep -v 127.0.0.1
   
   # Windowsの場合
   ipconfig
   ```

2. 携帯のブラウザで `http://[パソコンのIPアドレス]:8020/` にアクセス
   - 例: `http://192.168.1.100:8020/`

## 🔐 ログイン機能

### 👑 管理者アカウント
- **ユーザー名**: admin（固定）
- **パスワード**: 作成時に設定
- **権限**: 
  - シフトの作成・編集・削除
  - スタッフ管理
  - シフト種別管理
  - テンプレート管理
  - 全ての管理機能

### 👥 一般スタッフアカウント
- **ユーザー名**: staff
- **パスワード**: staff123
- **権限**: 
  - シフトの確認のみ（読み取り専用）
  - 編集・削除はできません

### ログイン後の画面
- **管理者**: シフト管理画面（編集可能）
- **一般スタッフ**: シフト確認画面（読み取り専用）

### ログアウト
- 画面右上のユーザー名をクリック → 「ログアウト」を選択

### 新しいユーザーの追加
- Django管理画面（`http://localhost:8020/admin/`）からユーザーを追加できます
- 管理者でログインして、「ユーザー」→「追加」から新規ユーザーを作成

## 🎯 主な機能

### 📅 カレンダー表示
- 月・週・日・リスト表示の切り替え
- ドラッグ&ドロップでシフト編集
- レスポンシブ対応（PC・タブレット・スマートフォン）

### 👥 スタッフ管理
- スタッフの追加・編集・削除
- アクティブ/非アクティブ管理

### 🔄 シフト種別管理
- 早番・遅番・夜勤などの種別設定
- 色分け表示

### 📊 テンプレート機能
- よく使うシフトパターンの保存
- 一括適用機能

### 📈 レポート・エクスポート
- シフト表のPDF出力
- CSV形式でのデータエクスポート

## 🔧 ヘルスチェック機能

システムの動作確認用エンドポイント：
- **システム健康状態**: http://localhost:8020/health/
- **アプリケーション準備状態**: http://localhost:8020/ready/
- **アプリケーション生存確認**: http://localhost:8020/live/

## ❓ うまくいかない時は

### ポートが使われている場合
```bash
python manage.py runserver 0.0.0.0:8021
```

### 携帯からアクセスできない場合
- パソコンとスマホが同じWi-Fiネットワークに接続されているか確認
- ファイアウォールがポート8020をブロックしていないか確認
- IPアドレスが正しいか確認

### ログインできない場合
- ユーザー名とパスワードが正しいか確認
- スーパーユーザーが作成されているか確認
- データベースのマイグレーションが完了しているか確認

### CSRFエラーが出る場合
```bash
# ブラウザのキャッシュをクリア（Cmd+Shift+R または Ctrl+Shift+R）
# またはプライベートブラウジングモードで試行
```

### エラーが出る場合
```bash
# データベースをリセット
rm db.sqlite3
python manage.py migrate
# ユーザー名は「admin」固定、メールアドレスとパスワードを入力
python manage.py createsuperuser
```

### 仮想環境の問題
```bash
# 仮想環境が正しくアクティベートされているか確認
which python
# 出力例: /path/to/wakakusa-shift-1/venv/bin/python

# 依存関係を再インストール
pip install -r requirements.txt
```

## 📁 プロジェクト構成

```
wakakusa-shift-1/
├── manage.py                     # Django管理スクリプト
├── requirements.txt              # 依存関係
├── db.sqlite3                   # データベース（作成後）
├── core/                        # Django設定
│   ├── settings/               # 環境別設定
│   ├── urls.py                 # URLルーティング
│   └── wsgi.py                 # WSGI設定
├── shift_management/            # メインアプリケーション
│   ├── models.py               # データモデル
│   ├── views.py                # ビュー
│   ├── urls.py                 # URLパターン
│   ├── forms.py                # フォーム
│   └── templates/              # テンプレート
├── templates/                   # 共通テンプレート
├── static/                     # 静的ファイル
└── venv/                       # 仮想環境
```

---

**完了！** シフトカレンダーが表示されます ��

**以上！簡単でしょ？ 😊**
