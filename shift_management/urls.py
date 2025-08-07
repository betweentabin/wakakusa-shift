from django.urls import path
from . import views

app_name = 'shift_management'

urlpatterns = [
    # 基本画面
    path('', views.shift_calendar, name='calendar'),
    path('staff-view/', views.staff_shift_view, name='staff_view'),
    
    # 認証関連
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # 組織管理
    path('organizations/', views.organization_list, name='organization_list'),
    path('organizations/create/', views.organization_create, name='organization_create'),
    path('organizations/<int:pk>/', views.organization_detail, name='organization_detail'),
    path('organizations/<int:pk>/edit/', views.organization_edit, name='organization_edit'),
    path('organization-select/', views.organization_select, name='organization_select'),
    path('organization-admin-login/', views.organization_admin_login, name='organization_admin_login'),
    
    # スタッフ管理
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/create/', views.staff_create, name='staff_create'),
    path('staff/<int:pk>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<int:pk>/delete/', views.staff_delete, name='staff_delete'),
    
    # シフト種別管理
    path('shift-types/', views.shift_type_list, name='shift_type_list'),
    path('shift-types/create/', views.shift_type_create, name='shift_type_create'),
    path('shift-types/<int:pk>/edit/', views.shift_type_edit, name='shift_type_edit'),
    path('shift-types/<int:pk>/delete/', views.shift_type_delete, name='shift_type_delete'),
    
    # シフト管理
    path('shifts/create/', views.shift_create, name='shift_create'),
    path('shifts/<int:pk>/edit/', views.shift_edit, name='shift_edit'),
    path('shifts/<int:pk>/delete/', views.shift_delete, name='shift_delete'),
    path('shifts/staff-create/', views.staff_shift_create, name='staff_shift_create'),
    path('shifts/<int:pk>/staff-edit/', views.staff_shift_edit, name='staff_shift_edit'),
    path('shifts/<int:pk>/staff-delete/', views.staff_shift_delete, name='staff_shift_delete'),
    path('shifts/bulk-create/', views.bulk_shift_create, name='bulk_shift_create'),
    path('shifts/traditional-bulk-create/', views.traditional_bulk_shift_create, name='traditional_bulk_shift_create'),
    path('calendar/bulk-shift-create/', views.calendar_bulk_shift_create, name='calendar_bulk_shift_create'),
    path('shifts/advanced-bulk-create/', views.advanced_bulk_shift_create, name='advanced_bulk_shift_create'),
    path('shifts/reason-create/', views.shift_reason_create, name='shift_reason_create'),
    
    # シフトテンプレート管理
    path('templates/', views.template_list, name='shift_template_list'),
    path('template-list/', views.template_list, name='template_list'),  # 別名追加
    path('templates/create/', views.template_create, name='shift_template_create'),
    path('templates/<int:pk>/edit/', views.template_edit, name='shift_template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='shift_template_delete'),
    path('templates/<int:pk>/apply/', views.template_apply, name='apply_template'),
    
    # 時間チャート
    path('time-chart/', views.time_chart, name='time_chart'),
    
    # レポート・エクスポート
    path('export/', views.shift_export, name='shift_export'),
    
    # API エンドポイント
    path('api/shifts/', views.api_shifts, name='api_shifts'),
    path('api/pending-shifts/', views.api_pending_shifts, name='api_pending_shifts'),
    path('api/staff-shifts/', views.staff_api_shifts, name='staff_api_shifts'),
    path('api/shift-update/', views.api_shift_update, name='update_shift_ajax'),
    path('api/shift-delete/', views.api_shift_delete, name='delete_shift_ajax'),
    path('api/approve-shift/', views.api_approve_shift, name='approve_shift_ajax'),
    path('api/reject-shift/', views.api_reject_shift, name='reject_shift_ajax'),
    path('api/bulk-approve-shifts/', views.api_bulk_approve_shifts, name='bulk_approve_shifts'),
    
    # wakakusa-shift-2から統合された新機能のURL
    
    # 休暇・申請管理
    path('leave-requests/', views.leave_request_list, name='leave_request_list'),
    path('leave-requests/create/', views.leave_request_create, name='leave_request_create'),
    path('api/approve-leave-request/', views.api_approve_leave_request, name='api_approve_leave_request'),
    path('api/reject-leave-request/', views.api_reject_leave_request, name='api_reject_leave_request'),
    
    # 組織切り替えAPI
    path('organization-switch/', views.organization_switch, name='organization_switch'),
    
    # シフト打診機能
    path('shift-proposals/', views.shift_proposal_list, name='shift_proposal_list'),
    path('shift-proposals/create/', views.shift_proposal_create, name='shift_proposal_create'),
    path('shift-proposals/<int:pk>/respond/', views.shift_proposal_respond, name='shift_proposal_respond'),
    
    # 通知機能
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/<int:pk>/read/', views.notification_mark_read, name='notification_mark_read'),
    path('api/notifications/mark-all-read/', views.api_mark_all_notifications_read, name='api_mark_all_notifications_read'),
]
