from django.conf.urls.static import static
from django.urls import path, include

from backend_payment import settings
from . import views

app_name = 'payment'

urlpatterns = [

    path('support_options/', views.SupportOptionsView.as_view(), name='support_options'),
    path('show_log/<str:pk>/', views.show_log, name='show_log'),

    path('', views.menu, name='menu'),
    path('invoice/', views.invoice, name='pay_check'),
    path('pay_to_card_create/', views.pay_to_card_create, name='pay_to_card_create'),  # card-to-card
    path('pay_to_m10_create/', views.pay_to_m10_create, name='pay_to_m10_create'),  # card_2
    path('pay_to_m10_wait_work/', views.pay_to_m10_wait_work, name='pay_to_m10_wait_work'),
    path('pay_to_m10_sms_input/', views.pay_to_m10_sms_input, name='pay_to_m10_sms_input'),
    path('m10_to_m10_create/', views.m10_to_m10_create, name='m10_to_m10_create'),  # m10_to_m10
    path('pay_result/<str:pk>/', views.PayResultView.as_view(), name='pay_result'),
    path('payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('payments_stats/', views.PaymentStatListView.as_view(), name='payments_stats'),
    path('payments_summary/', views.PaymentListSummaryView.as_view(), name='payments_summary'),
    path('payments_count/', views.PaymentListCount.as_view(), name='payment_count'),
    path('payments/<str:pk>/', views.PaymentEdit.as_view(), name='payment_edit'),
    path('payments_input/<str:pk>/', views.PaymentInput.as_view(), name='payment_input'),
    path('withdraws/', views.WithdrawListView.as_view(), name='withdraw_list'),
    path('withdraws/<str:pk>/', views.WithdrawEdit.as_view(), name='withdraw_edit'),
    path('balance_history/', views.BalanceHistoryListView.as_view(), name='balance_history_list'),
    # path('merch_stat/<int:pk>', views.MerchStatView.as_view(), name='merch_stats'),
    path('merchowners/<int:pk>/', views.MerchOwnerDetail.as_view(), name='merch_owner_detail'),
    path('merchowners/', views.MerchOwnerList.as_view(), name='merch_owner_list'),
    path('on_work/', views.on_work, name='on_work'),

    path('wait_requisite/<str:pk>/', views.wait_requisite, name='wait_requisite'),
    path('payment_type_not_worked/', views.payment_type_not_worked, name='payment_type_not_worked'),


    path('invoice_test_start/', views.invoice_test, name='invoice_test'),
    path('get_bank/<str:bin_num>/', views.get_bank, name='get_bank'),

    # Merh
    path('create_merchant/', views.MerchantCreate.as_view(), name='create_merchant'),
    path('merchant/<str:pk>/', views.MerchantDetail.as_view(), name='merchant_detail'),  # Shop
    path('merchant_delete/<str:pk>/', views.MerchantDelete.as_view(), name='merchant_delete'),
    path('merchant_orders/', views.MerchantOrders.as_view(), name='merchant_orders'),
    path('merchant_test_webhook/', views.merchant_test_webhook, name='merchant_test_webhook'),
    # path('export_payments/', views.export_payments, name='export_payments'),
    path('balance/', views.BalanceListView.as_view(), name='balance_list'),

    path('receive_webhook/', views.WebhookReceive.as_view(), name='receive_webhook'),
    path('repeat_webhook/<str:pk>', views.PaymentWebhookRepeat.as_view(), name='repeat_webhook'),
    path('withdraw_repeat_webhook/<str:pk>', views.WithdrawWebhookRepeat.as_view(), name='withdraw_repeat_webhook'),

    # path('test/', views.Test.as_view(), name='test'),

    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
