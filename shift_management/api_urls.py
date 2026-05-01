"""
在庫管理システム API URLルーティング

MD仕様書4.4節のAPI設計に基づいて実装
"""
from django.urls import path
from . import api_views

app_name = 'shift_management_api'

urlpatterns = [
    # ===== 品目管理API =====
    path('items/', api_views.api_items_list, name='api_items_list'),
    path('items/<int:item_id>/', api_views.api_item_detail, name='api_item_detail'),
    path('items/create/', api_views.api_item_create, name='api_item_create'),
    path('items/<int:item_id>/update/', api_views.api_item_update, name='api_item_update'),
    path('items/<int:item_id>/delete/', api_views.api_item_delete, name='api_item_delete'),
    
    # ===== 在庫管理API =====
    path('inventory/', api_views.api_inventory_list, name='api_inventory_list'),
    path('inventory/<int:item_id>/', api_views.api_inventory_detail, name='api_inventory_detail'),
    path('inventory/inbound/', api_views.api_inventory_inbound, name='api_inventory_inbound'),
    path('inventory/outbound/', api_views.api_inventory_outbound, name='api_inventory_outbound'),
    path('inventory/<int:item_id>/adjust/', api_views.api_inventory_adjust, name='api_inventory_adjust'),
    
    # ===== 発注管理API =====
    path('orders/', api_views.api_orders_list, name='api_orders_list'),
    path('orders/<int:order_id>/', api_views.api_order_detail, name='api_order_detail'),
    path('orders/create/', api_views.api_order_create, name='api_order_create'),
    path('orders/<int:order_id>/status/', api_views.api_order_update_status, name='api_order_update_status'),

    # ===== 請求書API（閲覧・ステータス変更） =====
    path('invoices/', api_views.api_invoices_list, name='api_invoices_list'),
    path('invoices/<int:invoice_id>/', api_views.api_invoice_detail, name='api_invoice_detail'),
    path('invoices/<int:invoice_id>/status/', api_views.api_invoice_change_status, name='api_invoice_change_status'),

    # ===== 納品書API（閲覧・ステータス変更） =====
    path('delivery-notes/', api_views.api_delivery_notes_list, name='api_delivery_notes_list'),
    path('delivery-notes/<int:delivery_note_id>/', api_views.api_delivery_note_detail, name='api_delivery_note_detail'),
    path('delivery-notes/<int:delivery_note_id>/status/', api_views.api_delivery_note_change_status, name='api_delivery_note_change_status'),
]
