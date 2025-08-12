#!/usr/bin/env python
"""
在庫管理API機能のテストスクリプト

使用方法:
1. Djangoサーバーを起動: python manage.py runserver
2. 別ターミナルで実行: python test_api.py
"""

import os
import sys

# Django設定の初期化（importの前に実行）
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')

import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from shift_management.models import Organization, Staff

def setup_test_data():
    """テスト用データの作成"""
    print("=== テスト用データを作成中... ===")
    
    # 組織作成
    org, created = Organization.objects.get_or_create(
        code='TEST_ORG',
        defaults={
            'name': 'テスト組織',
            'description': 'API テスト用の組織',
            'contact_email': 'test@example.com'
        }
    )
    print(f"組織: {org.name} {'作成' if created else '既存'}")
    
    # テストユーザー作成
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'testuser@example.com',
            'first_name': 'Test',
            'last_name': 'User'
        }
    )
    if created:
        user.set_password('testpass123')
        user.save()
    print(f"ユーザー: {user.username} {'作成' if created else '既存'}")
    
    # スタッフ作成（在庫管理権限付き）
    staff, created = Staff.objects.get_or_create(
        user=user,
        organization=org,
        defaults={
            'name': 'テストユーザー',
            'email': 'testuser@example.com',
            'approval_status': 'approved',
            'inventory_permission': 'admin',  # 管理者権限
            'is_active': True
        }
    )
    print(f"スタッフ: {staff.name} {'作成' if created else '既存'} (権限: {staff.get_inventory_permission_display()})")
    
    return org, user, staff

def test_inventory_apis():
    """在庫管理APIのテスト"""
    print("\n=== 在庫管理API機能テスト ===")
    
    # テストデータ準備
    org, user, staff = setup_test_data()
    
    # Djangoテストクライアントを使用（セッション認証対応）
    client = Client()
    
    # ログイン
    login_success = client.login(username='testuser', password='testpass123')
    if not login_success:
        print("❌ ログイン失敗")
        return False
    print("✅ ログイン成功")
    
    # セッションに組織IDを設定
    session = client.session
    session['current_organization_id'] = org.id
    session['current_organization_name'] = org.name
    session.save()
    
    # 1. 品目一覧API テスト
    print("\n--- 1. 品目一覧API テスト ---")
    response = client.get('/api/items/')
    print(f"ステータスコード: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 品目一覧取得成功: {data.get('total_count', 0)}件")
    else:
        print(f"❌ 品目一覧取得失敗: {response.content}")
        
    # 2. 品目作成API テスト
    print("\n--- 2. 品目作成API テスト ---")
    item_data = {
        'item_code': 'TEST001',
        'item_name': 'テスト品目1',
        'unit': '個',
        'threshold': 10,
        'initial_stock': 50,
        'order_url': 'https://example.com/order'
    }
    
    response = client.post('/api/items/create/', item_data, content_type='application/json')
    print(f"ステータスコード: {response.status_code}")
    if response.status_code == 201:
        data = response.json()
        item_id = data.get('item_id')
        print(f"✅ 品目作成成功: ID={item_id}, 名前={data.get('item_name')}")
        
        # 3. 品目詳細API テスト
        print("\n--- 3. 品目詳細API テスト ---")
        response = client.get(f'/api/items/{item_id}/')
        print(f"ステータスコード: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 品目詳細取得成功: {data.get('item_name')} (在庫: {data.get('current_stock')}{data.get('unit')})")
        else:
            print(f"❌ 品目詳細取得失敗: {response.content}")
            
        # 4. 出庫API テスト
        print("\n--- 4. 出庫API テスト ---")
        outbound_data = {
            'item_id': item_id,
            'quantity': 10,
            'notes': 'APIテスト用出庫'
        }
        
        response = client.post('/api/inventory/outbound/', outbound_data, content_type='application/json')
        print(f"ステータスコード: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 出庫処理成功: {data.get('old_stock')} → {data.get('new_stock')}")
        else:
            print(f"❌ 出庫処理失敗: {response.content}")
            
        # 5. 入庫API テスト
        print("\n--- 5. 入庫API テスト ---")
        inbound_data = {
            'item_id': item_id,
            'quantity': 20,
            'notes': 'APIテスト用入庫'
        }
        
        response = client.post('/api/inventory/inbound/', inbound_data, content_type='application/json')
        print(f"ステータスコード: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 入庫処理成功: {data.get('old_stock')} → {data.get('new_stock')}")
        else:
            print(f"❌ 入庫処理失敗: {response.content}")
            
        # 6. 在庫一覧API テスト
        print("\n--- 6. 在庫一覧API テスト ---")
        response = client.get('/api/inventory/')
        print(f"ステータスコード: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 在庫一覧取得成功: {data.get('summary', {}).get('total_items', 0)}品目")
            for inv in data.get('inventory', []):
                status = "⚠️在庫不足" if inv.get('is_low_stock') else "✅充足"
                print(f"  - {inv.get('item_name')}: {inv.get('current_stock')}{inv.get('unit')} {status}")
        else:
            print(f"❌ 在庫一覧取得失敗: {response.content}")
            
        # 7. 発注作成API テスト
        print("\n--- 7. 発注作成API テスト ---")
        order_data = {
            'item_id': item_id,
            'ordered_quantity': 30,
            'supplier_url': 'https://supplier.example.com',
            'notes': 'APIテスト用発注'
        }
        
        response = client.post('/api/orders/create/', order_data, content_type='application/json')
        print(f"ステータスコード: {response.status_code}")
        if response.status_code == 201:
            data = response.json()
            order_id = data.get('order_id')
            print(f"✅ 発注作成成功: ID={order_id}, 数量={data.get('ordered_quantity')}")
            
            # 8. 発注ステータス更新API テスト
            print("\n--- 8. 発注ステータス更新API テスト ---")
            status_data = {
                'status': 'delivered'
            }
            
            response = client.put(f'/api/orders/{order_id}/status/', status_data, content_type='application/json')
            print(f"ステータスコード: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ ステータス更新成功: {data.get('old_status')} → {data.get('new_status')}")
                print(f"   納品日: {data.get('delivery_date')}")
            else:
                print(f"❌ ステータス更新失敗: {response.content}")
                
            # 9. 発注一覧API テスト
            print("\n--- 9. 発注一覧API テスト ---")
            response = client.get('/api/orders/')
            print(f"ステータスコード: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 発注一覧取得成功: {data.get('total_count', 0)}件")
                for order in data.get('orders', []):
                    print(f"  - {order.get('item', {}).get('item_name')}: {order.get('ordered_quantity')}個 ({order.get('status_display')})")
            else:
                print(f"❌ 発注一覧取得失敗: {response.content}")
        else:
            print(f"❌ 発注作成失敗: {response.content}")
    else:
        print(f"❌ 品目作成失敗: {response.content}")
    
    return True

if __name__ == '__main__':
    try:
        print("🚀 在庫管理システムAPI機能テスト開始")
        test_inventory_apis()
        print("\n✅ APIテスト完了")
        
        # 監査ログの確認
        from shift_management.models import InventoryAuditLog
        recent_logs = InventoryAuditLog.objects.all().order_by('-timestamp')[:10]
        
        print(f"\n=== 最近の監査ログ ({recent_logs.count()}件) ===")
        for log in recent_logs:
            print(f"  {log.timestamp.strftime('%H:%M:%S')} - {log.user.username}: {log.get_action_display()}")
            if log.description:
                print(f"    → {log.description}")
                
    except Exception as e:
        print(f"❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()