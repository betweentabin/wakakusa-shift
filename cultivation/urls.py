from django.urls import path
from . import views

app_name = 'cultivation'

urlpatterns = [
    path('', views.cultivation_top, name='cultivation_top'),
    path('layouts/', views.layout_list, name='layout_list'),
    path('layouts/new/', views.layout_create, name='layout_create'),
    path('layouts/new/simple/', views.layout_create_simple, name='layout_create_simple'),
    path('layouts/<int:layout_id>/', views.layout_detail, name='layout_detail'),
    path('layouts/<int:layout_id>/floor-plan/', views.layout_floor_plan, name='layout_floor_plan'),
    path('layouts/<int:layout_id>/delete/', views.layout_delete, name='layout_delete'),
    path('layouts/<int:layout_id>/sections/new/', views.section_create, name='section_create'),
    path('layouts/<int:layout_id>/sections/bulk/', views.bulk_section_create, name='bulk_section_create'),
    path('layouts/<int:layout_id>/sections/visual/', views.visual_section_create, name='visual_section_create'),
    path('sections/<int:section_id>/', views.section_detail, name='section_detail'),
    path('sections/<int:section_id>/edit/', views.section_edit, name='section_edit'),
    path('sections/<int:section_id>/delete/', views.section_delete, name='section_delete'),
    path('sections/<int:section_id>/plot/edit/', views.section_edit_plot, name='section_edit_plot'),
    path('sections/<int:section_id>/level/<int:level>/crop/', views.section_crop_manage, name='section_crop_manage'),
    path('sections/<int:section_id>/plan/new/', views.plan_create, name='plan_create'),
    path('plans/<int:plan_id>/edit/', views.plan_edit, name='plan_edit'),
    path('plans/<int:plan_id>/logs/new/', views.log_create, name='log_create'),
    
    # 作物名管理機能
    path('crops/', views.crop_list, name='crop_list'),
    path('crops/new/', views.crop_create_form, name='crop_create_form'),
    path('crops/<int:crop_id>/edit/', views.crop_edit_form, name='crop_edit_form'),
    path('crops/<int:crop_id>/delete/', views.crop_delete, name='crop_delete'),
    
    # 棚管理機能
    path('plots/', views.plot_management, name='plot_management'),
    path('plots/floor-plan/<int:layout_id>/', views.plot_floor_plan_with_layout, name='plot_floor_plan_with_layout'),
    path('plots/floor-plan/', views.plot_floor_plan, name='plot_floor_plan'),
    path('plots/new/', views.plot_create, name='plot_create'),
    path('plots/<int:plot_id>/', views.plot_detail_view, name='plot_detail'),
    path('plots/<int:plot_id>/edit/', views.plot_edit, name='plot_edit'),
    path('plots/<int:plot_id>/delete/', views.plot_delete, name='plot_delete'),
    path('plots/<int:plot_id>/update-position/', views.plot_update_position, name='plot_update_position'),
    
    # 作物管理機能
    path('plots/<int:plot_id>/crops/new/', views.crop_create, name='crop_create'),
    path('plots/<int:plot_id>/level/<int:level>/crops/new/', views.crop_create_for_level, name='crop_create_for_level'),
    path('shelf-crops/<int:crop_id>/edit/', views.crop_edit, name='crop_edit'),
    path('shelf-crops/<int:crop_id>/delete/', views.crop_delete_from_level, name='crop_delete_from_level'),
    path('shelf-crops/<int:crop_id>/upload/', views.crop_image_upload_view, name='crop_image_upload'),
    
    # OCR機能
    path('layouts/create-ocr/', views.layout_create_with_ocr, name='layout_create_ocr'),
    path('ocr/preview/', views.ocr_preview, name='ocr_preview'),
    path('layouts/<int:layout_id>/preview/', views.layout_preview_with_layout, name='layout_preview_with_layout'),
    
    # 新しいOCRワークフロー
    path('layouts/new/ocr/step1/', views.layout_create_ocr_step1, name='layout_create_ocr_step1'),
    path('layouts/new/ocr/step2/', views.layout_create_ocr_step2, name='layout_create_ocr_step2'),
    path('layouts/new/ocr/step3/', views.layout_create_ocr_step3, name='layout_create_ocr_step3'),
    path('api/ocr/process/', views.ocr_process_step3, name='ocr_process_step3'),
    path('api/ocr/create-layout/', views.ocr_create_layout, name='ocr_create_layout'),
] 