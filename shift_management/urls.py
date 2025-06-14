from django.urls import path
from . import views

app_name = 'shift_management'

urlpatterns = [
    # 認証関連
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # ホームページ（権限に応じてリダイレクト）
    path('', views.home_redirect, name='home'),
    
    # カレンダー表示（管理者用）
    path('calendar/', views.shift_calendar, name='calendar'),
    
    # スタッフ用シフト確認・管理
    path('staff-view/', views.staff_shift_view, name='staff_view'),
    path('staff-api/shifts/', views.staff_api_shifts, name='staff_api_shifts'),
    path('staff/shift/create/', views.staff_shift_create, name='staff_shift_create'),
    path('staff/shift/<int:pk>/edit/', views.staff_shift_edit, name='staff_shift_edit'),
    path('staff/shift/<int:pk>/delete/', views.staff_shift_delete, name='staff_shift_delete'),
    
    # スタッフ管理
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/create/', views.staff_create, name='staff_create'),
    path('staff/<int:pk>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<int:pk>/delete/', views.staff_delete, name='staff_delete'),
    
    # シフト管理
    path('shift/create/', views.shift_create, name='shift_create'),
    path('shift/<int:pk>/edit/', views.shift_edit, name='shift_edit'),
    path('shift/<int:pk>/delete/', views.shift_delete, name='shift_delete'),
    
    # 事由登録
    path('shift/reason/create/', views.shift_reason_create, name='shift_reason_create'),
    
    # 複数シフト一括登録（新規追加）
    path('shift/bulk-create/', views.bulk_shift_create, name='bulk_shift_create'),
    
    # シフト種別管理
    path('shift-type/', views.shift_type_list, name='shift_type_list'),
    path('shift-type/create/', views.shift_type_create, name='shift_type_create'),
    path('shift-type/<int:pk>/edit/', views.shift_type_edit, name='shift_type_edit'),
    path('shift-type/<int:pk>/delete/', views.shift_type_delete, name='shift_type_delete'),
    
    # テンプレート管理
    path('template/', views.template_list, name='template_list'),
    path('template/create/', views.template_create, name='template_create'),
    path('template/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('template/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('template/<int:pk>/apply/', views.template_apply, name='template_apply'),
    # シフトテンプレート詳細の削除（新規追加）
    path('template/detail/<int:pk>/delete/', views.template_detail_delete, name='template_detail_delete'),
    
    # シフト印刷・エクスポート（新規追加）
    path('export/', views.shift_export, name='shift_export'),
    
    # API
    path('api/shifts/', views.api_shifts, name='api_shifts'),
    # ドラッグ＆ドロップ用API（新規追加）
    path('api/shift-update/', views.api_shift_update, name='api_shift_update'),
    path('api/shift-delete/', views.api_shift_delete, name='api_shift_delete'),
    
    # 承認関連API（新規追加）
    path('api/pending-shifts/', views.api_pending_shifts, name='api_pending_shifts'),
    path('api/approve-shift/', views.api_approve_shift, name='api_approve_shift'),
    path('api/reject-shift/', views.api_reject_shift, name='api_reject_shift'),
    path('api/bulk-approve-shifts/', views.api_bulk_approve_shifts, name='api_bulk_approve_shifts'),
    
    # 時間チャート
    path('time-chart/', views.time_chart, name='time_chart'),
]
