"""
権限チェック用デコレータ
"""
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


def get_staff_for_user_internal(user):
    """ユーザーに対応するStaffオブジェクトを取得（内部用）"""
    from .models import Staff
    try:
        return Staff.objects.get(user=user, is_active=True, approval_status='approved')
    except Staff.DoesNotExist:
        return None


def require_inventory_permission(min_permission='view'):
    """
    在庫管理権限チェックデコレータ

    Args:
        min_permission: 必要な最小権限レベル
            - 'view': 閲覧のみ
            - 'edit': 編集可能
            - 'admin': 管理者権限

    使用例:
        @login_required
        @require_inventory_permission('edit')
        def order_create(request):
            # 編集権限が必要な処理
            pass
    """
    permission_levels = {
        'none': 0,
        'view': 1,
        'edit': 2,
        'admin': 3,
    }

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # スーパーユーザーは常に許可
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # スタッフ情報を取得
            staff = get_staff_for_user_internal(request.user)
            if not staff:
                messages.error(request, 'スタッフ情報が見つかりません。管理者にお問い合わせください。')
                return redirect('shift_management:calendar')

            # グローバル管理者と管理者は在庫管理の全権限を持つ
            if staff.role_type in ['global_admin', 'manager']:
                return view_func(request, *args, **kwargs)

            # 職員・アルバイト(staff, part_time)は基本的な閲覧・編集権限を持つ
            if staff.role_type in ['staff', 'part_time']:
                required_level = permission_levels.get(min_permission, 1)
                # 職員・アルバイトはeditレベル（2）までデフォルトで許可
                if required_level <= 2:
                    return view_func(request, *args, **kwargs)
                # admin権限が必要な場合は、inventory_permissionをチェック
                if staff.inventory_permission == 'admin':
                    return view_func(request, *args, **kwargs)

            # その他の役割は在庫管理権限をチェック
            user_permission_level = permission_levels.get(staff.inventory_permission, 0)
            required_level = permission_levels.get(min_permission, 1)

            if user_permission_level >= required_level:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(
                    request,
                    f'この機能へのアクセス権限がありません。必要な権限: {min_permission}'
                )
                return redirect('shift_management:calendar')

        return wrapper
    return decorator


def manager_or_inventory_admin_required(view_func):
    """
    管理者または在庫管理者のみアクセス可能にするデコレータ

    使用例:
        @manager_or_inventory_admin_required
        def order_delete(request, pk):
            # 管理者のみ実行可能な処理
            pass
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        # スーパーユーザーは常に許可
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        # スタッフ情報を取得
        staff = get_staff_for_user_internal(request.user)
        if not staff:
            messages.error(request, 'スタッフ情報が見つかりません。')
            return redirect('shift_management:calendar')

        # 管理者、グローバル管理者、または在庫管理者
        if staff.role_type in ['manager', 'global_admin'] or staff.inventory_permission == 'admin':
            return view_func(request, *args, **kwargs)
        else:
            messages.error(
                request,
                'この機能へのアクセス権限がありません。管理者にお問い合わせください。'
            )
            return redirect('shift_management:calendar')

    return wrapper


def require_role(allowed_roles):
    """
    特定の役割のみアクセス可能にするデコレータ

    Args:
        allowed_roles: 許可する役割のリスト
                      例: ['manager', 'staff', 'global_admin']

    使用例:
        @require_role(['manager', 'global_admin'])
        def staff_approval(request, pk):
            # 管理者・グローバル管理者のみ実行可能
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # スーパーユーザーは常に許可
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # スタッフ情報を取得
            staff = get_staff_for_user_internal(request.user)
            if not staff:
                messages.error(request, 'スタッフ情報が見つかりません。')
                return redirect('shift_management:calendar')

            # 役割チェック
            if staff.role_type in allowed_roles:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(
                    request,
                    f'この機能へのアクセス権限がありません。必要な役割: {", ".join(allowed_roles)}'
                )
                return redirect('shift_management:calendar')

        return wrapper
    return decorator
