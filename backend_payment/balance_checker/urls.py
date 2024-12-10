from django.conf.urls.static import static
from django.urls import path, include

from . import views

app_name = 'balance_checker'

urlpatterns = [
    path('wallets/', views.WalletListView.as_view(), name='payment_list'),
]