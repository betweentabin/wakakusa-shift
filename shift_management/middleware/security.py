"""
セキュリティ強化ミドルウェア
"""

import time
import logging
from django.core.cache import cache
from django.http import HttpResponseTooManyRequests, JsonResponse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
import hashlib

logger = logging.getLogger(__name__)

class RateLimitMiddleware(MiddlewareMixin):
    """
    レート制限ミドルウェア
    同一IPからの過度なリクエストを制限
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # 設定値（本番環境では環境変数から取得推奨）
        self.rate_limit = getattr(settings, 'RATE_LIMIT_REQUESTS', 100)  # 1分間のリクエスト数
        self.rate_limit_window = getattr(settings, 'RATE_LIMIT_WINDOW', 60)  # 時間窓（秒）
        self.rate_limit_login = getattr(settings, 'RATE_LIMIT_LOGIN', 5)  # ログイン試行回数
        super().__init__(get_response)
    
    def process_request(self, request):
        # 管理者は制限を適用しない
        if hasattr(request, 'user') and request.user.is_superuser:
            return None
        
        # IPアドレスを取得
        ip_address = self.get_client_ip(request)
        
        # ログインページの特別な制限
        if request.path == '/login/' and request.method == 'POST':
            return self.check_login_rate_limit(ip_address)
        
        # 一般的なレート制限
        return self.check_general_rate_limit(ip_address)
    
    def get_client_ip(self, request):
        """クライアントIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def check_general_rate_limit(self, ip_address):
        """一般的なレート制限チェック"""
        cache_key = f"rate_limit_{ip_address}"
        current_requests = cache.get(cache_key, 0)
        
        if current_requests >= self.rate_limit:
            logger.warning(f"Rate limit exceeded for IP: {ip_address}")
            return HttpResponseTooManyRequests(
                "リクエスト数が制限を超えました。しばらく待ってから再試行してください。"
            )
        
        # リクエスト数を増加
        cache.set(cache_key, current_requests + 1, self.rate_limit_window)
        return None
    
    def check_login_rate_limit(self, ip_address):
        """ログイン試行のレート制限チェック"""
        cache_key = f"login_attempts_{ip_address}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= self.rate_limit_login:
            logger.warning(f"Login rate limit exceeded for IP: {ip_address}")
            return JsonResponse({
                'error': 'ログイン試行回数が制限を超えました。15分後に再試行してください。'
            }, status=429)
        
        # 試行回数を増加（15分間保持）
        cache.set(cache_key, attempts + 1, 900)
        return None

class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    セキュリティヘッダーを追加するミドルウェア
    """
    
    def process_response(self, request, response):
        # セキュリティヘッダーを追加
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # CSP（Content Security Policy）
        if not settings.DEBUG:
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "img-src 'self' data:; "
                "connect-src 'self';"
            )
            response['Content-Security-Policy'] = csp_policy
        
        return response

class AuditLogMiddleware(MiddlewareMixin):
    """
    監査ログミドルウェア
    重要な操作をログに記録
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.audit_logger = logging.getLogger('audit')
        super().__init__(get_response)
    
    def process_request(self, request):
        # リクエスト開始時刻を記録
        request._audit_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        # 監査対象のパスかチェック
        if self.should_audit(request):
            self.log_request(request, response)
        
        return response
    
    def should_audit(self, request):
        """監査対象かどうかを判定"""
        audit_paths = [
            '/admin/',
            '/login/',
            '/logout/',
            '/api/shift/update/',
            '/api/shift/delete/',
            '/staff/create/',
            '/staff/edit/',
            '/staff/delete/',
        ]
        
        return any(request.path.startswith(path) for path in audit_paths)
    
    def log_request(self, request, response):
        """リクエストをログに記録"""
        duration = time.time() - getattr(request, '_audit_start_time', time.time())
        
        log_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'user': str(request.user) if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser) else 'Anonymous',
            'ip_address': self.get_client_ip(request),
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration': f"{duration:.3f}s",
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
        }
        
        # POST データがある場合（パスワードなどの機密情報は除外）
        if request.method == 'POST' and hasattr(request, 'POST'):
            safe_post_data = {}
            for key, value in request.POST.items():
                if key.lower() not in ['password', 'password1', 'password2', 'old_password']:
                    safe_post_data[key] = value
            if safe_post_data:
                log_data['post_data'] = safe_post_data
        
        self.audit_logger.info(f"AUDIT: {log_data}")
    
    def get_client_ip(self, request):
        """クライアントIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class MaintenanceModeMiddleware(MiddlewareMixin):
    """
    メンテナンスモードミドルウェア
    """
    
    def process_request(self, request):
        # メンテナンスモードフラグをチェック
        maintenance_mode = cache.get('maintenance_mode', False)
        
        if maintenance_mode:
            # 管理者は除外
            if hasattr(request, 'user') and request.user.is_superuser:
                return None
            
            # ヘルスチェックエンドポイントは除外
            if request.path in ['/health/', '/ready/', '/live/']:
                return None
            
            # メンテナンス画面を表示
            from django.template.response import TemplateResponse
            return TemplateResponse(request, 'maintenance.html', status=503)
        
        return None 