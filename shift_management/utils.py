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
        # まず、ユーザーの全てのスタッフレコードを確認
        staff_records = Staff.objects.filter(
            user=user,
            approval_status='approved',
            is_active=True
        )

        # グローバル管理者チェック（どの組織のレコードでもOK）
        if staff_records.filter(role_type='global_admin').exists():
            return True

        # 指定された組織のスタッフレコードを取得
        staff = staff_records.filter(organization=organization).first()

        if not staff:
            return False

        # 管理者は自動的に在庫管理の全権限を持つ
        if staff.role_type == 'manager':
            return True

        # 職員・アルバイト(role_type='staff' or 'part_time')は基本的な在庫閲覧・編集権限を持つ
        if staff.role_type in ['staff', 'part_time']:
            # 職員・アルバイトは view と edit レベルの権限を持つ（admin権限は個別設定が必要）
            permission_hierarchy = {
                'none': 0,
                'view': 1,
                'edit': 2,
                'admin': 3
            }
            required_level = permission_hierarchy.get(permission_level, 0)
            # 職員・アルバイトはeditレベル（2）までデフォルトで許可
            if required_level <= 2:
                return True
            # admin権限が必要な場合は、inventory_permissionをチェック
            return staff.inventory_permission == 'admin'

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
    """現在選択されている組織を取得（属性→セッションの順で判定）"""
    # Request属性に設定済みならそれを優先
    if hasattr(request, 'current_organization') and request.current_organization:
        return request.current_organization
    # セッションから取得
    org_id = request.session.get('current_organization_id')
    if org_id:
        try:
            return Organization.objects.get(id=org_id, is_active=True)
        except Organization.DoesNotExist:
            # 無効IDの場合はセッションをクリーン
            request.session.pop('current_organization_id', None)
            request.session.pop('current_organization_name', None)
    return None


def is_global_admin(user):
    """ユーザーがグローバル管理者かどうかを判定"""
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    try:
        staff = Staff.objects.get(user=user)
        return staff.role_type == 'global_admin' and staff.is_active and staff.approval_status == 'approved'
    except Staff.DoesNotExist:
        return False


def get_accessible_organizations(user):
    """ユーザーがアクセス可能な組織のクエリセットを返す"""
    if not user or not user.is_authenticated:
        return Organization.objects.none()

    # グローバル管理者は全組織にアクセス可能
    if is_global_admin(user):
        return Organization.objects.filter(is_active=True)

    # 通常のユーザーは自分の組織のみ
    try:
        staff = Staff.objects.get(user=user, is_active=True, approval_status='approved')
        if staff.organization:
            return Organization.objects.filter(id=staff.organization.id, is_active=True)
    except Staff.DoesNotExist:
        pass

    return Organization.objects.none()


def filter_by_organization(queryset, user, org_field='organization'):
    """
    クエリセットを組織でフィルタリング

    Args:
        queryset: フィルタリング対象のクエリセット
        user: 現在のユーザー
        org_field: 組織フィールド名（デフォルト: 'organization'）
                  リレーション経由の場合は 'staff__organization' のように指定

    Returns:
        フィルタリングされたクエリセット
    """
    if not user or not user.is_authenticated:
        return queryset.none()

    # グローバル管理者はフィルタリングなし
    if is_global_admin(user):
        return queryset

    # 通常のユーザーは自分の組織のみ
    try:
        staff = Staff.objects.get(user=user, is_active=True, approval_status='approved')
        if staff.organization:
            filter_kwargs = {org_field: staff.organization}
            return queryset.filter(**filter_kwargs)
    except Staff.DoesNotExist:
        pass

    # スタッフ情報がない場合は空のクエリセットを返す
    return queryset.none()


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
