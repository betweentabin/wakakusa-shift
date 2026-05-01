"""
cultivation アプリのAPI URL設定
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

# DRFのRouterを使用してViewSetのURLを自動生成
router = DefaultRouter()
router.register(r'schedules', api_views.CultivationScheduleViewSet, basename='schedule')
router.register(r'processes', api_views.CropProcessViewSet, basename='process')
router.register(r'templates', api_views.CropTemplateViewSet, basename='template')
router.register(r'shelf-crops', api_views.ShelfCropViewSet, basename='shelf-crop')

# ガントチャート用のViewSet
router.register(r'gantt/schedules', api_views.ProcessScheduleViewSet, basename='gantt-schedule')
router.register(r'gantt/lane-configs', api_views.LaneConfigViewSet, basename='lane-config')
router.register(r'gantt/holiday-configs', api_views.HolidayConfigViewSet, basename='holiday-config')
router.register(r'gantt/holidays', api_views.HolidayViewSet, basename='holiday')

urlpatterns = [
    # Routerで生成されたURLを含める
    path('', include(router.urls)),

    # カスタムアクション: テンプレートからスケジュールを作成
    path('schedules/from-template/',
         api_views.create_schedule_from_template,
         name='schedule-from-template'),

    # ガントチャート統合データAPI
    path('gantt/data/', api_views.GanttDataAPIView.as_view(), name='gantt-data'),
]
