# 🚀 wakakusa-shift ローカル実行手順

## 📥 ダウンロード・準備

```bash
# 1. プロジェクトをダウンロード
git clone https://github.com/betweentabin/wakakusa-shift.git
cd wakakusa-shift

# 2. 仮想環境を作成
python -m venv venv

# 3. 仮想環境を有効化
# Windows の場合:
venv\Scripts\activate
# Mac/Linux の場合:
source venv/bin/activate

# 4. 必要なパッケージをインストール
pip install -r requirements.txt


## 🗄️ データベース準備

```bash
# データベースを作成
python manage.py migrate


## ▶️ サーバー起動

```bash
# サーバーを起動
python manage.py runserver


## 🌐 ブラウザで確認

ブラウザで http://127.0.0.1:8000/ にアクセス

**完了！** シフトカレンダーが表示されます 🎉

## ❓ うまくいかない時は

### ポートが使われている場合
```bash
python manage.py runserver 8001
```

### エラーが出る場合
```bash
# データベースをリセット
rm db.sqlite3
python manage.py migrate
```

---

**以上！簡単でしょ？ 😊** 
