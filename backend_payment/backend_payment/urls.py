from django.contrib import admin
from django.urls import path, include

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('', include('payment.urls', namespace='payment')),
    path('', include('deposit.urls', namespace='deposit')),
    path('admin/', admin.site.urls),
    path('auth/', include('users.urls', namespace='users')),
    path('api/v1/', include('api.urls')),

    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='docs'),
    path(
        'api/v1/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc'
    ),
]


handler403 = 'core.views.permission_denied'
handler500 = 'core.views.server_error'
