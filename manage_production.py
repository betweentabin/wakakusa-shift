#!/usr/bin/env python
"""
本番環境用Django管理スクリプト
"""
import os
import sys

if __name__ == '__main__':
    # 本番環境設定を使用
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_production')
    os.environ['DJANGO_PRODUCTION'] = 'True'
    
    # .envファイルから環境変数を読み込み
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv) 