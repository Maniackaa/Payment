from django.conf.urls.static import static
from django.urls import path, include

from backend_payment import settings
from . import views

app_name = 'payment'

urlpatterns = [

    path('', views.menu, name='menu'),
    path('invoice/', views.invoice, name='pay_check'),
    path('pay_to_card_create/', views.pay_to_card_create, name='pay_to_card_create'),
    path('pay_to_m10_create/', views.pay_to_m10_create, name='pay_to_m10_create'),
    path('pay_result/<str:pk>/', views.PayResultView.as_view(), name='pay_result'),
    path('payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('payments/<str:pk>/', views.PaymentEdit.as_view(), name='payment_edit'),
    path('withdraws/', views.WithdrawListView.as_view(), name='withdraw_list'),
    path('withdraws/<str:pk>/', views.WithdrawEdit.as_view(), name='withdraw_edit'),
    path('balance/', views.BalanceListView.as_view(), name='balance_list'),
    # path('merch_stat/<int:pk>', views.MerchStatView.as_view(), name='merch_stats'),

    path('payment_type_not_worked/', views.payment_type_not_worked, name='payment_type_not_worked'),


    # path('invoice_test_start/', views.invoice_test, name='invoice_test'),
    path('get_bank/<str:bin_num>/', views.get_bank, name='get_bank'),

    # Merh
    path('create_merchant/', views.MerchantCreate.as_view(), name='create_merchant'),
    path('merchant/<str:pk>/', views.MerchantDetail.as_view(), name='merchant_detail'), # Shop
    path('merchant_delete/<str:pk>/', views.MerchantDelete.as_view(), name='merchant_delete'),
    path('merchant_orders/', views.MerchantOrders.as_view(), name='merchant_orders'),
    path('merchant_test_webhook/', views.merchant_test_webhook, name='merchant_test_webhook'),

    path('receive_webhook/', views.WebhookReceive.as_view(), name='receive_webhook'),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
