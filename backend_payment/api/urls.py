from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api import views


app_name = "api"

v1_router = DefaultRouter()
v1_router.register("payment", views.PaymentViewSet, basename='payment'),
v1_router.register("payment_status", views.PaymentStatusView, basename='payment_status'),
v1_router.register("payment_types", views.PaymentTypesView, basename='payment_types'),

v1_router.register("withdraw", views.WithdrawViewSet, basename='withdraw'),

urlpatterns = [
    path("", include(v1_router.urls)),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
