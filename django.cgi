#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xserver用 Django CGIスクリプト
"""

import os
import sys
import cgitb

# CGIエラーの詳細表示（デバッグ用、本番では無効化推奨）
# cgitb.enable()

# プロジェクトのパスを設定
project_path = '/home/your-account/your-domain.com/wakakusa-shift'
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# 環境変数の設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_production')
os.environ['DJANGO_PRODUCTION'] = 'True'

# .envファイルから環境変数を読み込み
try:
    from dotenv import load_dotenv
    env_path = os.path.join(project_path, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

# Django設定
import django
from django.conf import settings
from django.core.wsgi import get_wsgi_application

# Django初期化
django.setup()

# WSGIアプリケーション
application = get_wsgi_application()

# CGI実行
if __name__ == '__main__':
    try:
        from wsgiref.handlers import CGIHandler
        CGIHandler().run(application)
    except Exception as e:
        print("Content-Type: text/html\n")
        print(f"<h1>Django CGI Error</h1>")
        print(f"<p>Error: {str(e)}</p>")
        print(f"<p>Python Path: {sys.path}</p>")
        print(f"<p>Project Path: {project_path}</p>")
        import traceback
        print(f"<pre>{traceback.format_exc()}</pre>") 