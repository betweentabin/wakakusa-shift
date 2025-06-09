"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys
from django.core.wsgi import get_wsgi_application

# 本番環境の場合は設定を切り替え
if 'DJANGO_PRODUCTION' in os.environ:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_production')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# プロジェクトのパスを追加（Xserver用）
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_path not in sys.path:
    sys.path.append(project_path)

application = get_wsgi_application() 