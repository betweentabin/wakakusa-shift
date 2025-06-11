"""
Gunicorn設定ファイル（本番環境用）
使用方法: gunicorn -c gunicorn.conf.py core.wsgi_production:application
"""

import multiprocessing
import os

# サーバー設定
bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
preload_app = True
timeout = 30
keepalive = 2

# ログ設定
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# プロセス設定
daemon = False
pidfile = "logs/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# セキュリティ設定
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# パフォーマンス設定
worker_tmp_dir = "/dev/shm"  # メモリ上の一時ディレクトリ（Linuxの場合）

# 環境変数設定
raw_env = [
    'DJANGO_SETTINGS_MODULE=core.settings.production',
]

# フック関数
def on_starting(server):
    """サーバー開始時の処理"""
    server.log.info("わかくさシフト Gunicornサーバーを開始します...")

def on_reload(server):
    """リロード時の処理"""
    server.log.info("🔄 Gunicornサーバーをリロードしています...")

def worker_int(worker):
    """ワーカー中断時の処理"""
    worker.log.info(f"👷 ワーカー {worker.pid} が中断されました")

def pre_fork(server, worker):
    """ワーカーフォーク前の処理"""
    server.log.info(f"👷 ワーカー {worker.pid} をフォークします")

def post_fork(server, worker):
    """ワーカーフォーク後の処理"""
    server.log.info(f"👷 ワーカー {worker.pid} がフォークされました")

def when_ready(server):
    """サーバー準備完了時の処理"""
    server.log.info("✅ Gunicornサーバーの準備が完了しました")

def worker_abort(worker):
    """ワーカー異常終了時の処理"""
    worker.log.error(f"❌ ワーカー {worker.pid} が異常終了しました")

# 本番環境での推奨設定
if os.environ.get('DJANGO_SETTINGS_MODULE') == 'core.settings.production':
    # 本番環境では少し厳しめの設定
    timeout = 60
    max_requests = 500
    workers = min(multiprocessing.cpu_count() * 2 + 1, 8)  # 最大8ワーカー