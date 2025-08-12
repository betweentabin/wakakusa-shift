"""
Cultivation アプリケーションのリファクタリングされたURL設定
"""
from django.urls import path, include
from . import views

app_name = 'cultivation'

# レイアウト関連のURL
layout_patterns = [
    path('', views.LayoutListView.as_view(), name='layout_list'),
    path('create/', views.LayoutCreateView.as_view(), name='layout_create'),
    path('<int:pk>/', views.LayoutDetailView.as_view(), name='layout_detail'),
    path('<int:pk>/edit/', views.LayoutUpdateView.as_view(), name='layout_edit'),
    path('<int:pk>/delete/', views.LayoutDeleteView.as_view(), name='layout_delete'),
    path('<int:layout_id>/sections/', include([
        path('create/', views.SectionCreateView.as_view(), name='section_create'),
        path('bulk-create/', views.BulkSectionCreateView.as_view(), name='bulk_section_create'),
        path('visual-create/', views.VisualSectionCreateView.as_view(), name='visual_section_create'),
    ])),
    path('<int:layout_id>/export/', views.LayoutExportView.as_view(), name='layout_export'),
    path('<int:layout_id>/statistics/', views.LayoutStatisticsView.as_view(), name='layout_statistics'),
]

# 区画関連のURL
section_patterns = [
    path('', views.SectionListView.as_view(), name='section_list'),
    path('<int:pk>/', views.SectionDetailView.as_view(), name='section_detail'),
    path('<int:pk>/edit/', views.SectionUpdateView.as_view(), name='section_edit'),
    path('<int:pk>/delete/', views.SectionDeleteView.as_view(), name='section_delete'),
    path('<int:section_id>/plans/', include([
        path('create/', views.PlanCreateView.as_view(), name='plan_create'),
    ])),
]

# 栽培計画関連のURL
plan_patterns = [
    path('', views.PlanListView.as_view(), name='plan_list'),
    path('<int:pk>/', views.PlanDetailView.as_view(), name='plan_detail'),
    path('<int:pk>/edit/', views.PlanUpdateView.as_view(), name='plan_edit'),
    path('<int:pk>/delete/', views.PlanDeleteView.as_view(), name='plan_delete'),
    path('<int:plan_id>/logs/', include([
        path('create/', views.LogCreateView.as_view(), name='log_create'),
    ])),
    path('<int:pk>/harvest/', views.PlanHarvestView.as_view(), name='plan_harvest'),
    path('bulk-harvest/', views.BulkHarvestView.as_view(), name='bulk_harvest'),
    path('harvest-ready/', views.HarvestReadyListView.as_view(), name='harvest_ready_list'),
    path('overdue/', views.OverdueListView.as_view(), name='overdue_list'),
]

# 作物関連のURL
crop_patterns = [
    path('', views.CropListView.as_view(), name='crop_list'),
    path('create/', views.CropCreateView.as_view(), name='crop_create'),
    path('<int:pk>/', views.CropDetailView.as_view(), name='crop_detail'),
    path('<int:pk>/edit/', views.CropUpdateView.as_view(), name='crop_edit'),
    path('<int:pk>/delete/', views.CropDeleteView.as_view(), name='crop_delete'),
    path('recommendations/', views.CropRecommendationView.as_view(), name='crop_recommendations'),
    path('search/', views.CropSearchView.as_view(), name='crop_search'),
]

# 棚関連のURL
plot_patterns = [
    path('', views.PlotGridView.as_view(), name='plot_grid'),
    path('list/', views.PlotListView.as_view(), name='plot_list'),
    path('create/', views.PlotCreateView.as_view(), name='plot_create'),
    path('<int:pk>/', views.PlotDetailView.as_view(), name='plot_detail'),
    path('<int:pk>/edit/', views.PlotUpdateView.as_view(), name='plot_edit'),
    path('<int:pk>/delete/', views.PlotDeleteView.as_view(), name='plot_delete'),
    path('<int:plot_id>/crops/', include([
        path('create/', views.ShelfCropCreateView.as_view(), name='shelf_crop_create'),
    ])),
]

# 棚栽培作物関連のURL
shelf_crop_patterns = [
    path('', views.ShelfCropListView.as_view(), name='shelf_crop_list'),
    path('<int:pk>/', views.ShelfCropDetailView.as_view(), name='shelf_crop_detail'),
    path('<int:pk>/edit/', views.ShelfCropUpdateView.as_view(), name='shelf_crop_edit'),
    path('<int:pk>/delete/', views.ShelfCropDeleteView.as_view(), name='shelf_crop_delete'),
    path('<int:crop_id>/images/', include([
        path('upload/', views.CropImageUploadView.as_view(), name='crop_image_upload'),
    ])),
]

# ログ関連のURL
log_patterns = [
    path('', views.LogListView.as_view(), name='log_list'),
    path('<int:pk>/', views.LogDetailView.as_view(), name='log_detail'),
    path('<int:pk>/edit/', views.LogUpdateView.as_view(), name='log_edit'),
    path('<int:pk>/delete/', views.LogDeleteView.as_view(), name='log_delete'),
]

# API関連のURL
api_patterns = [
    path('layouts/<int:layout_id>/statistics/', views.LayoutStatisticsAPIView.as_view(), name='api_layout_statistics'),
    path('plans/search/', views.PlanSearchAPIView.as_view(), name='api_plan_search'),
    path('crops/suggestions/', views.CropSuggestionsAPIView.as_view(), name='api_crop_suggestions'),
    path('notifications/', views.NotificationAPIView.as_view(), name='api_notifications'),
]

# メインURLパターン
urlpatterns = [
    # ダッシュボード
    path('', views.CultivationDashboardView.as_view(), name='cultivation_top'),
    
    # 各モジュールのURL
    path('layouts/', include(layout_patterns)),
    path('sections/', include(section_patterns)),
    path('plans/', include(plan_patterns)),
    path('crops/', include(crop_patterns)),
    path('plots/', include(plot_patterns)),
    path('shelf-crops/', include(shelf_crop_patterns)),
    path('logs/', include(log_patterns)),
    
    # API
    path('api/', include(api_patterns)),
    
    # 管理機能
    path('import/', views.ImportView.as_view(), name='import'),
    path('export/', views.ExportView.as_view(), name='export'),
    path('statistics/', views.StatisticsView.as_view(), name='statistics'),
    path('reports/', views.ReportsView.as_view(), name='reports'),
    
    # 後方互換性のためのリダイレクト
    path('layouts/new/', views.redirect_to_layout_create, name='layout_create_old'),
    path('layouts/<int:layout_id>/', views.redirect_to_layout_detail, name='layout_detail_old'),
    path('crops/new/', views.redirect_to_crop_create, name='crop_create_form_old'),
]