from django.urls import path
from . import views

app_name = 'shift_management'

urlpatterns = [
    # シフト管理のメイン画面（カレンダー表示）
    path('', views.shift_calendar, name='calendar'),
    
    # スタッフ管理
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/create/', views.staff_create, name='staff_create'),
    path('staff/<int:pk>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<int:pk>/delete/', views.staff_delete, name='staff_delete'),
    
    # シフト管理
    path('shift/create/', views.shift_create, name='shift_create'),
    path('shift/<int:pk>/edit/', views.shift_edit, name='shift_edit'),
    path('shift/<int:pk>/delete/', views.shift_delete, name='shift_delete'),
    
    # シフト種別管理
    path('shift-type/', views.shift_type_list, name='shift_type_list'),
    path('shift-type/create/', views.shift_type_create, name='shift_type_create'),
    path('shift-type/<int:pk>/edit/', views.shift_type_edit, name='shift_type_edit'),
    path('shift-type/<int:pk>/delete/', views.shift_type_delete, name='shift_type_delete'),
    
    # シフトテンプレート管理
    path('template/', views.template_list, name='template_list'),
    path('template/create/', views.template_create, name='template_create'),
    path('template/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('template/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('template/<int:pk>/apply/', views.template_apply, name='template_apply'),
    
    # API エンドポイント（AJAX用）
    path('api/shifts/', views.api_shifts, name='api_shifts'),
] 