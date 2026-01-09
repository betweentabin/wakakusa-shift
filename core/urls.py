from django.contrib import admin
from django.urls import path, include
from shift_management.views import health_check, readiness_check, liveness_check

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('shift_management.urls')),
    # ヘルスチェックエンドポイント
    path('health/', health_check, name='health_check'),
    path('ready/', readiness_check, name='readiness_check'),
    path('live/', liveness_check, name='liveness_check'),
]
