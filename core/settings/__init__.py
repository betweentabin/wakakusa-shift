"""
Django settings for cultivation_project project.
開発環境用設定（本番環境では core.settings.production を使用）
"""

# 開発環境設定を使用
from .development import *

# 開発環境用の追加設定
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8020',
    'http://127.0.0.1:8020',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# 環境別設定ファイルパッケージ 