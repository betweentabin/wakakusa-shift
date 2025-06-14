#!/bin/bash

# わかくさシフト本番環境デプロイスクリプト
echo "=== わかくさシフト デプロイ開始 ==="

# 色付きメッセージ用の関数
print_status() {
    echo -e "\033[32m[INFO]\033[0m $1"
}

print_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

# エラー時の処理
set -e
trap 'print_error "デプロイ中にエラーが発生しました"' ERR

# 1. 最新コードの取得
print_status "最新コードを取得中..."
git pull origin new_main

# 2. 仮想環境のアクティベート
print_status "仮想環境をアクティベート中..."
source venv/bin/activate

# 3. 依存関係のインストール
print_status "依存関係をインストール中..."
pip install -r requirements.txt

# 4. 静的ファイルの収集
print_status "静的ファイルを収集中..."
python manage.py collectstatic --noinput --settings=wakakusa_shift.settings_production

# 5. データベースマイグレーション
print_status "データベースマイグレーション実行中..."
python manage.py migrate --settings=wakakusa_shift.settings_production

# 6. Gunicornの再起動
print_status "Gunicornを再起動中..."
sudo systemctl restart gunicorn
sudo systemctl restart nginx

# 7. サービス状態の確認
print_status "サービス状態を確認中..."
sudo systemctl status gunicorn --no-pager
sudo systemctl status nginx --no-pager

print_status "デプロイ完了！"
echo "=== わかくさシフト デプロイ完了 ===" 