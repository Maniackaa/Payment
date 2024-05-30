import django_filters
from django.contrib.auth import get_user_model

from payment.models import Payment, Withdraw

User = get_user_model()


class PaymentFilter(django_filters.FilterSet):
    id = django_filters.CharFilter(lookup_expr='icontains')
    order_id = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.MultipleChoiceFilter(choices=Payment.PAYMENT_STATUS)
    class Meta:
        model = Payment
        fields = ['id', 'order_id', 'status', 'pay_type']


class WithdrawFilter(django_filters.FilterSet):
    id = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.MultipleChoiceFilter(choices=Withdraw.WITHDRAW_STATUS)
    class Meta:
        model = Payment
        fields = ['id', 'status']


class BalanceChangeFilter(django_filters.FilterSet):
    user = django_filters.ModelChoiceFilter(queryset=User.objects.filter(role='merchant'))
    class Meta:
        model = Payment
        fields = ['user']