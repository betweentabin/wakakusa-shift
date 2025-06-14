import os
from .settings import *

# 本番環境用設定
DEBUG = False

# 本番環境で使用するドメインを設定（後で更新）
ALLOWED_HOSTS = [
    '162.43.31.158',  # サーバーIP
    'localhost',
    '127.0.0.1',
    # 'your-domain.com',  # ドメイン取得後に追加
]

# データベース設定（PostgreSQL）
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'wakakusa_shift'),
        'USER': os.environ.get('DB_USER', 'wakakusa_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# セキュリティ設定
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# 静的ファイル設定
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# メディアファイル設定
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# セキュリティ設定
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# HTTPS設定（ドメイン取得後に有効化）
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True

# ログ設定
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/wakakusa_shift/django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
} 