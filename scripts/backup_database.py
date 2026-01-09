#!/usr/bin/env python
"""
データベースバックアップスクリプト
定期実行でデータベースをバックアップ
"""

import os
import sys
import subprocess
import datetime
from pathlib import Path

# Djangoプロジェクトのパスを追加
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Django設定を読み込み
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.production')

import django
django.setup()

from django.conf import settings

def backup_mysql():
    """MySQLデータベースのバックアップ"""
    db_config = settings.DATABASES['default']
    
    # バックアップファイル名（日時付き）
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"wakakusa_shift_backup_{timestamp}.sql"
    backup_path = BASE_DIR / 'backups' / backup_filename
    
    # バックアップディレクトリを作成
    backup_path.parent.mkdir(exist_ok=True)
    
    # mysqldumpコマンドを実行
    cmd = [
        'mysqldump',
        f"--host={db_config['HOST']}",
        f"--port={db_config['PORT']}",
        f"--user={db_config['USER']}",
        f"--password={db_config['PASSWORD']}",
        '--single-transaction',
        '--routines',
        '--triggers',
        db_config['NAME']
    ]
    
    try:
        with open(backup_path, 'w') as f:
            subprocess.run(cmd, stdout=f, check=True)
        
        print(f"✅ バックアップ完了: {backup_path}")
        
        # 古いバックアップファイルを削除（30日以上前）
        cleanup_old_backups()
        
        return backup_path
        
    except subprocess.CalledProcessError as e:
        print(f"❌ バックアップエラー: {e}")
        return None

def backup_sqlite():
    """SQLiteデータベースのバックアップ"""
    db_path = settings.DATABASES['default']['NAME']
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return None
    
    # バックアップファイル名（日時付き）
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"wakakusa_shift_backup_{timestamp}.sqlite3"
    backup_path = BASE_DIR / 'backups' / backup_filename
    
    # バックアップディレクトリを作成
    backup_path.parent.mkdir(exist_ok=True)
    
    try:
        # ファイルをコピー
        import shutil
        shutil.copy2(db_path, backup_path)
        
        print(f"✅ バックアップ完了: {backup_path}")
        
        # 古いバックアップファイルを削除
        cleanup_old_backups()
        
        return backup_path
        
    except Exception as e:
        print(f"❌ バックアップエラー: {e}")
        return None

def cleanup_old_backups(days=30):
    """古いバックアップファイルを削除"""
    backup_dir = BASE_DIR / 'backups'
    if not backup_dir.exists():
        return
    
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
    
    for backup_file in backup_dir.glob('wakakusa_shift_backup_*'):
        if backup_file.stat().st_mtime < cutoff_date.timestamp():
            try:
                backup_file.unlink()
                print(f"🗑️  古いバックアップを削除: {backup_file.name}")
            except Exception as e:
                print(f"⚠️  削除エラー: {backup_file.name} - {e}")

def main():
    """メイン処理"""
    print("🔄 データベースバックアップを開始...")
    
    db_engine = settings.DATABASES['default']['ENGINE']
    
    if 'mysql' in db_engine:
        backup_path = backup_mysql()
    elif 'sqlite' in db_engine:
        backup_path = backup_sqlite()
    else:
        print(f"❌ サポートされていないデータベース: {db_engine}")
        return
    
    if backup_path:
        print("✅ バックアップ処理完了")
    else:
        print("❌ バックアップ処理失敗")

if __name__ == '__main__':
    main() 