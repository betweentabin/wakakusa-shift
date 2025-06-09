#!/usr/bin/env python
"""
本番環境デプロイメント用スクリプト
Xserver向け
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, description):
    """コマンドを実行し、結果を表示"""
    print(f"\n🔄 {description}")
    print(f"実行中: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ 成功: {description}")
        if result.stdout:
            print(f"出力: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ エラー: {description}")
        print(f"エラー内容: {e.stderr}")
        return False

def create_directories():
    """必要なディレクトリを作成"""
    directories = ['logs', 'cache', 'staticfiles', 'media']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"📁 ディレクトリ作成: {directory}")

def collect_static_files():
    """静的ファイルを収集"""
    return run_command(
        "python manage.py collectstatic --noinput --settings=core.settings_production",
        "静的ファイルの収集"
    )

def run_migrations():
    """データベースマイグレーションを実行"""
    return run_command(
        "python manage.py migrate --settings=core.settings_production",
        "データベースマイグレーション"
    )

def create_superuser():
    """スーパーユーザーの作成（対話式）"""
    print("\n👤 スーパーユーザーの作成")
    print("本番環境用の管理者アカウントを作成してください。")
    
    try:
        subprocess.run([
            "python", "manage.py", "createsuperuser", 
            "--settings=core.settings_production"
        ], check=True)
        print("✅ スーパーユーザーが作成されました")
        return True
    except subprocess.CalledProcessError:
        print("❌ スーパーユーザーの作成に失敗しました")
        return False

def check_deployment():
    """デプロイメントの確認"""
    return run_command(
        "python manage.py check --deploy --settings=core.settings_production",
        "デプロイメント設定の確認"
    )

def main():
    """メイン処理"""
    print("🚀 Xserver本番環境デプロイメント開始")
    print("=" * 50)
    
    # 必要なディレクトリを作成
    create_directories()
    
    # デプロイメント設定の確認
    if not check_deployment():
        print("❌ デプロイメント設定に問題があります。修正してから再実行してください。")
        return False
    
    # 静的ファイルの収集
    if not collect_static_files():
        print("❌ 静的ファイルの収集に失敗しました。")
        return False
    
    # データベースマイグレーション
    if not run_migrations():
        print("❌ データベースマイグレーションに失敗しました。")
        return False
    
    # スーパーユーザーの作成
    create_superuser_choice = input("\n❓ スーパーユーザーを作成しますか？ (y/n): ")
    if create_superuser_choice.lower() == 'y':
        create_superuser()
    
    print("\n🎉 デプロイメント完了！")
    print("=" * 50)
    print("📋 次のステップ:")
    print("1. .env ファイルを作成し、環境変数を設定")
    print("2. Xserverにファイルをアップロード")
    print("3. データベース接続情報を確認")
    print("4. ドメイン設定を確認")
    print("5. SSL証明書の設定（推奨）")
    
    return True

if __name__ == "__main__":
    main() 