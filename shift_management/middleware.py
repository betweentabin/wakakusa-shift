"""
組織選択用ミドルウェア
"""
from django.shortcuts import get_object_or_404
from .models import Organization


class OrganizationMiddleware:
    """
    セッションから現在の組織を取得してリクエストに設定するミドルウェア
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # セッションから組織IDを取得
        org_id = request.session.get('current_organization_id')
        
        if org_id:
            try:
                request.current_organization = Organization.objects.get(id=org_id, is_active=True)
            except Organization.DoesNotExist:
                # 無効な組織IDの場合はセッションをクリア
                if 'current_organization_id' in request.session:
                    del request.session['current_organization_id']
                if 'current_organization_name' in request.session:
                    del request.session['current_organization_name']
                request.current_organization = None
        else:
            request.current_organization = None
        
        response = self.get_response(request)
        return response