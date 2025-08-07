from django.contrib import admin
from django.urls import path, include
from shift_management.views import health_check, readiness_check, liveness_check
from django.contrib.auth import views as auth_views
from shift_management.views import user_login, user_logout
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    path('cultivation/', include('cultivation.urls')),
    path('', include('shift_management.urls')),
    # ヘルスチェックエンドポイント
    path('health/', health_check, name='health_check'),
    path('ready/', readiness_check, name='readiness_check'),
    path('live/', liveness_check, name='liveness_check'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
