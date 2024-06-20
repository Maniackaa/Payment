import django_filters
from django import forms
from django.contrib.auth import get_user_model

from payment.models import Payment, Withdraw

User = get_user_model()


class PaymentFilter(django_filters.FilterSet):
    id = django_filters.CharFilter(lookup_expr='icontains')
    order_id = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.MultipleChoiceFilter(choices=Payment.PAYMENT_STATUS)
    class Meta:
        model = Payment
        fields = ['id', 'order_id', 'status', 'pay_type', 'amount']


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



class MyDateInput(forms.DateInput):
    input_type = 'date'
    format = '%Y-%m-%d'


class PaymentMerchStatFilter(django_filters.FilterSet):
    create_start = django_filters.DateFilter(field_name='create_at', lookup_expr='gte',
                                             widget=MyDateInput({'class': 'form-control'})
                                             )
    create_end = django_filters.DateFilter(field_name='create_at', lookup_expr='lte',
                                             widget=MyDateInput({'class': 'form-control'})
                                             )

    class Meta:
        model = Payment
        fields = ['create_start']