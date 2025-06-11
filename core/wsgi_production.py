"""
本番環境用WSGI設定
"""

import os
from django.core.wsgi import get_wsgi_application

# 本番環境設定を使用
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.production')

application = get_wsgi_application() 