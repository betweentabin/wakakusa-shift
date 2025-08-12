"""
Django共通設定（ベース）
全環境で共通の設定項目
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',  # Django REST Framework を追加
    'shift_management',
    'cultivation',
]

# Django REST Framework設定
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'shift_management.middleware.OrganizationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'shift_management' / 'templates'
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'ja'
TIME_ZONE = 'Asia/Tokyo'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files (User uploaded files)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Messages settings
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG: 'secondary',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}

# ログイン関連の設定
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# セッション設定
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24時間

# ファイルアップロード設定
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB

# キャッシュ設定（デフォルト：ローカルメモリ）
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# OCR設定（栽培区画認識特化版）
OCR_SETTINGS = {
    'TESSERACT_CMD': '/opt/homebrew/bin/tesseract',  # macOS Homebrewでのパス
    'TEMP_DIR': os.path.join(BASE_DIR, 'media', 'temp_ocr'),
    'MAX_FILE_SIZE': 15 * 1024 * 1024,  # 15MB（高解像度画像対応）
    'SUPPORTED_FORMATS': ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'],
    'DEFAULT_CONFIDENCE_THRESHOLD': 55,  # 栽培区画用に少し緩和
    'CACHE_ENABLED': True,
    'CACHE_DURATION': 7200,  # 2時間（処理時間を考慮して延長）
    'OCR_LANGUAGES': 'jpn+eng',  # 日本語+英語
    'DEBUG_MODE': True,  # デバッグモード有効
    
    # 高度な前処理設定
    'ADVANCED_PREPROCESSING': {
        'enabled': True,
        'perspective_correction': True,      # 歪み補正有効
        'super_resolution': True,           # 超解像有効
        'adaptive_denoising': True,         # アダプティブノイズ除去有効
        'text_enhancement': True,           # テキスト領域強化有効
        'multi_stage_binarization': True,   # 多段階二値化有効
        'character_correction': True,       # 文字形状補正有効
        
        'resolution_threshold': 1200,       # 解像度向上の閾値
        'scale_factor': 2.0,               # 拡大倍率
        'noise_analysis_enabled': True,     # ノイズ分析有効
    },
    
    # 栽培区画特化設定
    'CULTIVATION_SPECIALIZED': {
        'enabled': True,
        'multi_mode_ocr': True,            # マルチモードOCR有効
        'numeric_specialized': True,        # 数字特化OCR有効
        'japanese_specialized': True,       # 日本語特化OCR有効
        'alphanumeric_specialized': True,   # 英数字特化OCR有効
        
        # 信頼度調整
        'confidence_bonuses': {
            'numeric_bonus': 10,
            'japanese_bonus': 5,
            'cultivation_vocabulary_bonus': 15,
            'alphanumeric_bonus': 8,
            'position_bonus_max': 5,
            'context_bonus_max': 25,
        },
        
        # タイプ別閾値調整
        'type_thresholds': {
            'section_number': -10,      # 区画番号は緩く
            'variety_name': -5,         # 品種名は少し緩く
            'measurement': 5,           # 測定値は厳しく
            'management_code': 0,       # 管理コードは標準
        },
        
        # 栽培関連語彙
        'cultivation_keywords': [
            'トマト', 'きゅうり', 'なす', 'ピーマン', 'レタス', 'キャベツ', 'ほうれん草',
            'いちご', 'メロン', 'すいか', 'かぼちゃ', 'ズッキーニ', 'オクラ', 'ししとう',
            '区画', '棚', 'ハウス', '温室', '育苗', '播種', '定植', '収穫', '管理',
            '品種', '苗', '種子', '肥料', '農薬', 'pH', '温度', '湿度', 'EC', 'ppm',
            'A棟', 'B棟', 'C棟', 'D棟', '1号', '2号', '3号', '4号', '5号',
            '東', '西', '南', '北', '中央', '左', '右', '上', '下',
            '第1', '第2', '第3', '第4', '第5', 'No.1', 'No.2', 'No.3',
        ]
    },
    
    # レガシー設定（後方互換性）
    'IMAGE_PREPROCESSING': {
        'DENOISE_STRENGTH': 10,
        'CLAHE_CLIP_LIMIT': 2.0,
        'CLAHE_TILE_GRID_SIZE': (8, 8),
        'BINARY_THRESHOLD': 0,
        'BINARY_MAX_VALUE': 255
    },
    'ADAPTIVE_SETTINGS': {
        'enabled': True,
        'confidence_fallback_threshold': 50,
        'retry_with_different_psm': True,
        'psm_modes': [6, 8, 7, 3],  # 試行するPSMモード
        'max_retries': 3
    }
} 