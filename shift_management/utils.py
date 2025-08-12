"""
在庫管理システムのユーティリティ関数
"""
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from .models import InventoryAuditLog, Staff, Organization
import json


def create_audit_log(user, organization, action, target_obj=None, description=None, old_values=None, new_values=None, request=None):
    """監査ログを作成する"""
    
    # IPアドレスとユーザーエージェントを取得
    ip_address = None
    user_agent = None
    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # ターゲットオブジェクトの情報を取得
    target_model = None
    target_id = None
    if target_obj:
        target_model = target_obj.__class__.__name__
        target_id = target_obj.pk
    
    # JSONシリアライザブルに変換
    def make_serializable(obj):
        if obj is None:
            return None
        if isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        if hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        return str(obj)
    
    old_values_json = make_serializable(old_values) if old_values else None
    new_values_json = make_serializable(new_values) if new_values else None
    
    InventoryAuditLog.objects.create(
        organization=organization,
        user=user,
        action=action,
        target_model=target_model,
        target_id=target_id,
        description=description,
        old_values=old_values_json,
        new_values=new_values_json,
        ip_address=ip_address,
        user_agent=user_agent
    )


def get_client_ip(request):
    """クライアントのIPアドレスを取得"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def has_inventory_permission(user, organization, permission_level):
    """
    在庫管理権限をチェックする
    
    Args:
        user: ユーザーオブジェクト
        organization: 組織オブジェクト
        permission_level: 'view', 'edit', 'admin'のいずれか
    
    Returns:
        bool: 権限があるかどうか
    """
    if not user or not user.is_authenticated:
        return False
    
    # スーパーユーザーは全ての権限を持つ
    if user.is_superuser:
        return True
    
    # 組織が指定されていない場合、スーパーユーザー以外は権限なし
    if not organization:
        return False
    
    try:
        staff = Staff.objects.get(user=user, organization=organization)
        if staff.approval_status != 'approved' or not staff.is_active:
            return False
        
        user_permission = staff.inventory_permission
        
        # 権限レベルの階層
        permission_hierarchy = {
            'none': 0,
            'view': 1,
            'edit': 2,
            'admin': 3
        }
        
        required_level = permission_hierarchy.get(permission_level, 0)
        user_level = permission_hierarchy.get(user_permission, 0)
        
        return user_level >= required_level
        
    except Staff.DoesNotExist:
        return False


def get_user_organizations(user):
    """ユーザーが所属する組織一覧を取得"""
    if not user or not user.is_authenticated:
        return Organization.objects.none()
    
    return Organization.objects.filter(
        staff__user=user,
        staff__approval_status='approved',
        staff__is_active=True,
        is_active=True
    ).distinct()


def get_current_organization(request):
    """現在選択されている組織を取得"""
    if hasattr(request, 'current_organization'):
        return request.current_organization
    return None


class InventoryPermissionMixin:
    """在庫管理権限チェック用のMixin"""
    
    required_permission = 'view'  # デフォルトは閲覧権限
    
    def dispatch(self, request, *args, **kwargs):
        current_org = get_current_organization(request)
        
        if not current_org:
            from django.shortcuts import redirect
            from django.contrib import messages
            messages.error(request, "組織を選択してください。")
            return redirect('shift_management:organization_select')
        
        if not has_inventory_permission(request.user, current_org, self.required_permission):
            from django.shortcuts import redirect
            from django.contrib import messages
            messages.error(request, "この操作を実行する権限がありません。")
            return redirect('shift_management:inventory_dashboard')
        
        return super().dispatch(request, *args, **kwargs)


def log_model_change(user, organization, action, instance, old_values=None, request=None):
    """モデル変更時の監査ログを記録"""
    model_name = instance.__class__.__name__
    
    # 新しい値を取得
    new_values = {}
    for field in instance._meta.fields:
        if not field.name.endswith('_id'):  # 外部キーのIDフィールドは除外
            new_values[field.name] = getattr(instance, field.name, None)
    
    # 説明を生成
    description = f"{model_name}の{action}"
    if hasattr(instance, 'name'):
        description += f": {instance.name}"
    elif hasattr(instance, 'item_name'):
        description += f": {instance.item_name}"
    elif hasattr(instance, '__str__'):
        description += f": {str(instance)}"
    
    create_audit_log(
        user=user,
        organization=organization,
        action=action,
        target_obj=instance,
        description=description,
        old_values=old_values,
        new_values=new_values,
        request=request
    )