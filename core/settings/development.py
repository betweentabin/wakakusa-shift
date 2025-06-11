"""
開発環境用設定
ローカル開発時に使用
"""

from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-h7d3f8j2k4l5m6n7b8v9c0x1z2a3s4d5f6g7h8j9k0l1m2n3'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# CSRF設定（開発環境用）
CSRF_TRUSTED_ORIGINS = [
    'https://8000-it74zvry9ngu35atr58eg-7ea0d6d9.manusvm.computer',
    'https://*.githubpreview.dev',
    'https://*.app.github.dev',
    'http://localhost:8000',
    'http://localhost:8010',
    'http://localhost:8020',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:8010',
    'http://127.0.0.1:8020',
    'http://0.0.0.0:8020',
]

# 開発環境用CSRF設定の緩和
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False
CSRF_USE_SESSIONS = False
CSRF_COOKIE_SAMESITE = 'Lax'

# Database（開発環境：SQLite）
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Static files
STATIC_ROOT = BASE_DIR / 'staticfiles'

# 開発環境用ログ設定
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'shift_management': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# 開発環境用メール設定（コンソール出力）
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' 