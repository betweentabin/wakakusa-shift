"""
在庫管理システムのRESTful APIビュー

MD仕様書で指定されたAPI設計に基づいて実装
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction as db_transaction
from django.contrib.auth.models import User

from .models import Item, Inventory, Transaction, Order, Organization, Staff
from .utils import (
    has_inventory_permission, create_audit_log, get_user_organizations,
    log_model_change
)

import json
from datetime import datetime


def get_user_organization(request, org_id=None):
    """ユーザーの組織を取得"""
    user_orgs = get_user_organizations(request.user)
    
    if org_id:
        return get_object_or_404(user_orgs, id=org_id)
    else:
        # セッションから現在の組織を取得
        current_org_id = request.session.get('current_organization_id')
        if current_org_id:
            try:
                return user_orgs.get(id=current_org_id)
            except Organization.DoesNotExist:
                pass
        
        # デフォルトで最初の組織を返す
        return user_orgs.first()


def check_api_permission(request, organization, permission_level):
    """API用権限チェック"""
    if not has_inventory_permission(request.user, organization, permission_level):
        return Response({
            'error': 'この操作を実行する権限がありません。',
            'required_permission': permission_level
        }, status=status.HTTP_403_FORBIDDEN)
    return None


# ===== 品目管理API =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_items_list(request):
    """GET /api/items: 全品目リストの取得"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 閲覧権限をチェック
    perm_error = check_api_permission(request, organization, 'view')
    if perm_error:
        return perm_error
    
    items = Item.objects.filter(organization=organization, is_active=True)
    
    items_data = []
    for item in items:
        inventory, created = Inventory.objects.get_or_create(
            item=item,
            defaults={'current_stock': 0}
        )
        
        items_data.append({
            'item_id': item.id,
            'item_code': item.item_code,
            'item_name': item.item_name,
            'unit': item.unit,
            'order_url': item.order_url,
            'threshold': item.threshold,
            'current_stock': inventory.current_stock,
            'is_low_stock': inventory.current_stock <= item.threshold,
            'is_active': item.is_active,
            'created_at': item.created_at.isoformat(),
            'updated_at': item.updated_at.isoformat()
        })
    
    return Response({
        'items': items_data,
        'total_count': len(items_data),
        'organization': {
            'id': organization.id,
            'name': organization.name
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_item_detail(request, item_id):
    """GET /api/items/{item_id}: 特定品目の詳細取得"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 閲覧権限をチェック
    perm_error = check_api_permission(request, organization, 'view')
    if perm_error:
        return perm_error
    
    item = get_object_or_404(Item, id=item_id, organization=organization)
    inventory, created = Inventory.objects.get_or_create(
        item=item,
        defaults={'current_stock': 0}
    )
    
    return Response({
        'item_id': item.id,
        'item_code': item.item_code,
        'item_name': item.item_name,
        'unit': item.unit,
        'order_url': item.order_url,
        'threshold': item.threshold,
        'current_stock': inventory.current_stock,
        'is_low_stock': inventory.current_stock <= item.threshold,
        'is_active': item.is_active,
        'created_at': item.created_at.isoformat(),
        'updated_at': item.updated_at.isoformat(),
        'organization': {
            'id': organization.id,
            'name': organization.name
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_item_create(request):
    """POST /api/items: 新規品目の登録"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 編集権限をチェック
    perm_error = check_api_permission(request, organization, 'edit')
    if perm_error:
        return perm_error
    
    data = request.data
    
    # 必須フィールドのチェック
    required_fields = ['item_code', 'item_name', 'unit']
    for field in required_fields:
        if not data.get(field):
            return Response({
                'error': f'必須フィールド "{field}" が指定されていません。'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # 品目コードの重複チェック
    if Item.objects.filter(
        item_code=data['item_code'],
        organization=organization
    ).exists():
        return Response({
            'error': '指定された品目コードは既に存在します。'
        }, status=status.HTTP_409_CONFLICT)
    
    try:
        with db_transaction.atomic():
            item = Item.objects.create(
                item_code=data['item_code'],
                item_name=data['item_name'],
                unit=data['unit'],
                order_url=data.get('order_url', ''),
                threshold=data.get('threshold', 10),
                organization=organization
            )
            
            # 在庫レコードを作成
            inventory = Inventory.objects.create(
                item=item,
                current_stock=data.get('initial_stock', 0)
            )
            
            # 監査ログを記録
            log_model_change(
                user=request.user,
                organization=organization,
                action='item_create',
                instance=item,
                request=request
            )
            
            # 初期在庫が設定されている場合は入庫記録も作成
            if data.get('initial_stock', 0) > 0:
                Transaction.objects.create(
                    item=item,
                    transaction_type='in',
                    quantity=data['initial_stock'],
                    user=request.user,
                    notes='初期在庫'
                )
        
        return Response({
            'message': '品目が正常に作成されました。',
            'item_id': item.id,
            'item_code': item.item_code,
            'item_name': item.item_name,
            'current_stock': inventory.current_stock
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'error': f'品目作成中にエラーが発生しました: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_item_update(request, item_id):
    """PUT /api/items/{item_id}: 特定品目の情報更新"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 編集権限をチェック
    perm_error = check_api_permission(request, organization, 'edit')
    if perm_error:
        return perm_error
    
    item = get_object_or_404(Item, id=item_id, organization=organization)
    data = request.data
    
    # 変更前のデータを保存
    old_values = {
        'item_code': item.item_code,
        'item_name': item.item_name,
        'unit': item.unit,
        'order_url': item.order_url,
        'threshold': item.threshold,
        'is_active': item.is_active
    }
    
    try:
        # 更新可能なフィールド
        updatable_fields = ['item_name', 'unit', 'order_url', 'threshold', 'is_active']
        
        for field in updatable_fields:
            if field in data:
                setattr(item, field, data[field])
        
        item.save()
        
        # 監査ログを記録
        log_model_change(
            user=request.user,
            organization=organization,
            action='item_update',
            instance=item,
            old_values=old_values,
            request=request
        )
        
        return Response({
            'message': '品目が正常に更新されました。',
            'item_id': item.id,
            'item_code': item.item_code,
            'item_name': item.item_name,
        })
        
    except Exception as e:
        return Response({
            'error': f'品目更新中にエラーが発生しました: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_item_delete(request, item_id):
    """DELETE /api/items/{item_id}: 特定品目の削除"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 管理者権限をチェック
    perm_error = check_api_permission(request, organization, 'admin')
    if perm_error:
        return perm_error
    
    item = get_object_or_404(Item, id=item_id, organization=organization)
    
    # 在庫や取引履歴がある場合は物理削除ではなく論理削除
    if (Transaction.objects.filter(item=item).exists() or 
        Order.objects.filter(item=item).exists()):
        
        item.is_active = False
        item.save()
        
        # 監査ログを記録
        log_model_change(
            user=request.user,
            organization=organization,
            action='item_delete',
            instance=item,
            request=request
        )
        
        return Response({
            'message': '品目を無効化しました（履歴保持のため物理削除はされません）。'
        })
    else:
        # 履歴がない場合は物理削除
        item_name = item.item_name
        item.delete()
        
        return Response({
            'message': f'品目 "{item_name}" を完全に削除しました。'
        })


# ===== 在庫管理API =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_inventory_list(request):
    """GET /api/inventory: 全品目の在庫状況取得"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 閲覧権限をチェック
    perm_error = check_api_permission(request, organization, 'view')
    if perm_error:
        return perm_error
    
    items = Item.objects.filter(organization=organization, is_active=True)
    
    inventory_data = []
    low_stock_count = 0
    
    for item in items:
        inventory, created = Inventory.objects.get_or_create(
            item=item,
            defaults={'current_stock': 0}
        )
        
        is_low_stock = inventory.current_stock <= item.threshold
        if is_low_stock:
            low_stock_count += 1
        
        inventory_data.append({
            'item_id': item.id,
            'item_code': item.item_code,
            'item_name': item.item_name,
            'unit': item.unit,
            'current_stock': inventory.current_stock,
            'threshold': item.threshold,
            'is_low_stock': is_low_stock,
            'last_updated': inventory.last_updated.isoformat()
        })
    
    return Response({
        'inventory': inventory_data,
        'summary': {
            'total_items': len(inventory_data),
            'low_stock_count': low_stock_count,
            'sufficient_count': len(inventory_data) - low_stock_count
        },
        'organization': {
            'id': organization.id,
            'name': organization.name
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_inventory_detail(request, item_id):
    """GET /api/inventory/{item_id}: 特定品目の在庫状況取得"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 閲覧権限をチェック
    perm_error = check_api_permission(request, organization, 'view')
    if perm_error:
        return perm_error
    
    item = get_object_or_404(Item, id=item_id, organization=organization)
    inventory, created = Inventory.objects.get_or_create(
        item=item,
        defaults={'current_stock': 0}
    )
    
    # 最近の取引履歴も含める
    recent_transactions = Transaction.objects.filter(
        item=item
    ).order_by('-transaction_date')[:10]
    
    transactions_data = [{
        'transaction_id': t.id,
        'transaction_type': t.transaction_type,
        'quantity': t.quantity,
        'transaction_date': t.transaction_date.isoformat(),
        'user': t.user.username if t.user else None,
        'notes': t.notes
    } for t in recent_transactions]
    
    return Response({
        'item_id': item.id,
        'item_code': item.item_code,
        'item_name': item.item_name,
        'unit': item.unit,
        'current_stock': inventory.current_stock,
        'threshold': item.threshold,
        'is_low_stock': inventory.current_stock <= item.threshold,
        'last_updated': inventory.last_updated.isoformat(),
        'recent_transactions': transactions_data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_inventory_inbound(request):
    """POST /api/inventory/inbound: 入庫処理"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 編集権限をチェック
    perm_error = check_api_permission(request, organization, 'edit')
    if perm_error:
        return perm_error
    
    data = request.data
    
    # 必須フィールドのチェック
    required_fields = ['item_id', 'quantity']
    for field in required_fields:
        if field not in data:
            return Response({
                'error': f'必須フィールド "{field}" が指定されていません。'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        quantity = int(data['quantity'])
        if quantity <= 0:
            return Response({
                'error': '数量は1以上である必要があります。'
            }, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError):
        return Response({
            'error': '数量は数値である必要があります。'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    item = get_object_or_404(Item, id=data['item_id'], organization=organization)
    
    try:
        with db_transaction.atomic():
            # トランザクション記録を作成
            transaction_obj = Transaction.objects.create(
                item=item,
                transaction_type='in',
                quantity=quantity,
                user=request.user,
                notes=data.get('notes', '')
            )
            
            # 在庫を更新
            inventory, created = Inventory.objects.get_or_create(
                item=item,
                defaults={'current_stock': 0}
            )
            
            old_stock = inventory.current_stock
            inventory.current_stock += quantity
            inventory.save()
            
            # 監査ログを記録
            create_audit_log(
                user=request.user,
                organization=organization,
                action='inventory_in',
                target_obj=item,
                description=f"{item.item_name}の入庫: {old_stock}{item.unit} → {inventory.current_stock}{item.unit}",
                old_values={'stock': old_stock},
                new_values={'stock': inventory.current_stock, 'quantity': quantity},
                request=request
            )
        
        return Response({
            'message': '入庫処理が完了しました。',
            'transaction_id': transaction_obj.id,
            'item_name': item.item_name,
            'old_stock': old_stock,
            'new_stock': inventory.current_stock,
            'quantity': quantity
        })
        
    except Exception as e:
        return Response({
            'error': f'入庫処理中にエラーが発生しました: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_inventory_outbound(request):
    """POST /api/inventory/outbound: 出庫処理"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 編集権限をチェック
    perm_error = check_api_permission(request, organization, 'edit')
    if perm_error:
        return perm_error
    
    data = request.data
    
    # 必須フィールドのチェック
    required_fields = ['item_id', 'quantity']
    for field in required_fields:
        if field not in data:
            return Response({
                'error': f'必須フィールド "{field}" が指定されていません。'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        quantity = int(data['quantity'])
        if quantity <= 0:
            return Response({
                'error': '数量は1以上である必要があります。'
            }, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError):
        return Response({
            'error': '数量は数値である必要があります。'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    item = get_object_or_404(Item, id=data['item_id'], organization=organization)
    
    try:
        with db_transaction.atomic():
            # 現在の在庫をチェック
            inventory, created = Inventory.objects.get_or_create(
                item=item,
                defaults={'current_stock': 0}
            )
            
            if inventory.current_stock < quantity:
                return Response({
                    'error': f'在庫不足です。現在の在庫: {inventory.current_stock}{item.unit}',
                    'current_stock': inventory.current_stock,
                    'requested_quantity': quantity
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # トランザクション記録を作成
            transaction_obj = Transaction.objects.create(
                item=item,
                transaction_type='out',
                quantity=quantity,
                user=request.user,
                notes=data.get('notes', '')
            )
            
            # 在庫を更新
            old_stock = inventory.current_stock
            inventory.current_stock -= quantity
            inventory.save()
            
            # 監査ログを記録
            create_audit_log(
                user=request.user,
                organization=organization,
                action='inventory_out',
                target_obj=item,
                description=f"{item.item_name}の出庫: {old_stock}{item.unit} → {inventory.current_stock}{item.unit}",
                old_values={'stock': old_stock},
                new_values={'stock': inventory.current_stock, 'quantity': quantity},
                request=request
            )
        
        return Response({
            'message': '出庫処理が完了しました。',
            'transaction_id': transaction_obj.id,
            'item_name': item.item_name,
            'old_stock': old_stock,
            'new_stock': inventory.current_stock,
            'quantity': quantity
        })
        
    except Exception as e:
        return Response({
            'error': f'出庫処理中にエラーが発生しました: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_inventory_adjust(request, item_id):
    """PUT /api/inventory/{item_id}/adjust: 在庫修正"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 管理者権限をチェック
    perm_error = check_api_permission(request, organization, 'admin')
    if perm_error:
        return perm_error
    
    data = request.data
    
    # 必須フィールドのチェック
    if 'new_stock' not in data:
        return Response({
            'error': '必須フィールド "new_stock" が指定されていません。'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        new_stock = int(data['new_stock'])
        if new_stock < 0:
            return Response({
                'error': '在庫数は0以上である必要があります。'
            }, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError):
        return Response({
            'error': '在庫数は数値である必要があります。'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    item = get_object_or_404(Item, id=item_id, organization=organization)
    
    try:
        with db_transaction.atomic():
            # 在庫を取得・更新
            inventory, created = Inventory.objects.get_or_create(
                item=item,
                defaults={'current_stock': 0}
            )
            
            old_stock = inventory.current_stock
            inventory.current_stock = new_stock
            inventory.save()
            
            # トランザクション記録を作成
            transaction_obj = Transaction.objects.create(
                item=item,
                transaction_type='adjustment',
                quantity=new_stock,
                user=request.user,
                notes=data.get('reason', '在庫修正')
            )
            
            # 監査ログを記録
            create_audit_log(
                user=request.user,
                organization=organization,
                action='inventory_adjust',
                target_obj=item,
                description=f"{item.item_name}の在庫修正: {old_stock}{item.unit} → {new_stock}{item.unit}",
                old_values={'stock': old_stock},
                new_values={'stock': new_stock, 'reason': data.get('reason', '')},
                request=request
            )
        
        return Response({
            'message': '在庫修正が完了しました。',
            'transaction_id': transaction_obj.id,
            'item_name': item.item_name,
            'old_stock': old_stock,
            'new_stock': new_stock,
        })
        
    except Exception as e:
        return Response({
            'error': f'在庫修正中にエラーが発生しました: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== 発注管理API =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_orders_list(request):
    """GET /api/orders: 全発注履歴の取得"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 閲覧権限をチェック
    perm_error = check_api_permission(request, organization, 'view')
    if perm_error:
        return perm_error
    
    # フィルタリングオプション
    status_filter = request.GET.get('status')
    item_id_filter = request.GET.get('item_id')
    
    orders = Order.objects.filter(
        item__organization=organization
    ).select_related('item', 'user')
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if item_id_filter:
        try:
            orders = orders.filter(item__id=int(item_id_filter))
        except ValueError:
            pass
    
    orders = orders.order_by('-order_date')
    
    orders_data = [{
        'order_id': order.id,
        'item': {
            'item_id': order.item.id,
            'item_code': order.item.item_code,
            'item_name': order.item.item_name,
            'unit': order.item.unit
        },
        'ordered_quantity': order.ordered_quantity,
        'order_date': order.order_date.isoformat(),
        'supplier_url': order.supplier_url,
        'status': order.status,
        'status_display': order.get_status_display(),
        'user': order.user.username if order.user else None,
        'delivery_date': order.delivery_date.isoformat() if order.delivery_date else None,
        'notes': order.notes
    } for order in orders]
    
    return Response({
        'orders': orders_data,
        'total_count': len(orders_data),
        'organization': {
            'id': organization.id,
            'name': organization.name
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_order_detail(request, order_id):
    """GET /api/orders/{order_id}: 特定発注の詳細取得"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 閲覧権限をチェック
    perm_error = check_api_permission(request, organization, 'view')
    if perm_error:
        return perm_error
    
    order = get_object_or_404(
        Order.objects.select_related('item', 'user'),
        id=order_id,
        item__organization=organization
    )
    
    return Response({
        'order_id': order.id,
        'item': {
            'item_id': order.item.id,
            'item_code': order.item.item_code,
            'item_name': order.item.item_name,
            'unit': order.item.unit
        },
        'ordered_quantity': order.ordered_quantity,
        'order_date': order.order_date.isoformat(),
        'supplier_url': order.supplier_url,
        'status': order.status,
        'status_display': order.get_status_display(),
        'user': order.user.username if order.user else None,
        'delivery_date': order.delivery_date.isoformat() if order.delivery_date else None,
        'notes': order.notes
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_order_create(request):
    """POST /api/orders: 新規発注の作成"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 編集権限をチェック
    perm_error = check_api_permission(request, organization, 'edit')
    if perm_error:
        return perm_error
    
    data = request.data
    
    # 必須フィールドのチェック
    required_fields = ['item_id', 'ordered_quantity']
    for field in required_fields:
        if field not in data:
            return Response({
                'error': f'必須フィールド "{field}" が指定されていません。'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        ordered_quantity = int(data['ordered_quantity'])
        if ordered_quantity <= 0:
            return Response({
                'error': '発注数量は1以上である必要があります。'
            }, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError):
        return Response({
            'error': '発注数量は数値である必要があります。'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    item = get_object_or_404(Item, id=data['item_id'], organization=organization)
    
    try:
        order = Order.objects.create(
            item=item,
            ordered_quantity=ordered_quantity,
            supplier_url=data.get('supplier_url', item.order_url or ''),
            user=request.user,
            notes=data.get('notes', '')
        )
        
        # 監査ログを記録
        log_model_change(
            user=request.user,
            organization=organization,
            action='order_create',
            instance=order,
            request=request
        )
        
        return Response({
            'message': '発注が正常に作成されました。',
            'order_id': order.id,
            'item_name': item.item_name,
            'ordered_quantity': ordered_quantity,
            'status': order.status
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'error': f'発注作成中にエラーが発生しました: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_order_update_status(request, order_id):
    """PUT /api/orders/{order_id}/status: 発注ステータスの更新"""
    organization = get_user_organization(request)
    if not organization:
        return Response({
            'error': '組織が見つかりません。'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 編集権限をチェック
    perm_error = check_api_permission(request, organization, 'edit')
    if perm_error:
        return perm_error
    
    data = request.data
    
    if 'status' not in data:
        return Response({
            'error': '必須フィールド "status" が指定されていません。'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # 有効なステータスかチェック
    valid_statuses = ['ordered', 'delivered', 'cancelled']
    if data['status'] not in valid_statuses:
        return Response({
            'error': f'無効なステータスです。有効な値: {", ".join(valid_statuses)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    order = get_object_or_404(
        Order.objects.select_related('item'),
        id=order_id,
        item__organization=organization
    )
    
    try:
        old_status = order.status
        order.status = data['status']
        
        # 納品済みの場合は納品日を設定し、在庫を更新
        if data['status'] == 'delivered' and old_status != 'delivered':
            from django.utils import timezone
            order.delivery_date = timezone.now()
            
            # 在庫を自動更新
            with db_transaction.atomic():
                order.save()
                
                inventory, created = Inventory.objects.get_or_create(
                    item=order.item,
                    defaults={'current_stock': 0}
                )
                
                old_stock = inventory.current_stock
                inventory.current_stock += order.ordered_quantity
                inventory.save()
                
                # 入庫トランザクション記録を自動作成
                Transaction.objects.create(
                    item=order.item,
                    transaction_type='in',
                    quantity=order.ordered_quantity,
                    user=request.user,
                    notes=f'発注納品 (発注ID: {order.id})'
                )
                
                # 監査ログを記録
                create_audit_log(
                    user=request.user,
                    organization=organization,
                    action='order_update',
                    target_obj=order,
                    description=f"発注ステータス更新: {old_status} → {order.status}, 在庫更新: {old_stock} → {inventory.current_stock}",
                    old_values={'status': old_status, 'stock': old_stock},
                    new_values={'status': order.status, 'stock': inventory.current_stock},
                    request=request
                )
        else:
            order.save()
            
            # 監査ログを記録
            log_model_change(
                user=request.user,
                organization=organization,
                action='order_update',
                instance=order,
                old_values={'status': old_status},
                request=request
            )
        
        return Response({
            'message': f'発注ステータスを "{order.get_status_display()}" に更新しました。',
            'order_id': order.id,
            'old_status': old_status,
            'new_status': order.status,
            'delivery_date': order.delivery_date.isoformat() if order.delivery_date else None
        })
        
    except Exception as e:
        return Response({
            'error': f'ステータス更新中にエラーが発生しました: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)