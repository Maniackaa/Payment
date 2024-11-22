import django_filters
from django_filters import rest_framework as filters

from payment.models import BalanceChange, Payment, Withdraw


class BalanceChangeFilter(filters.FilterSet):
    start = filters.IsoDateTimeFilter(label='create_at gte', field_name="create_at", lookup_expr='gte')
    end = filters.IsoDateTimeFilter(label="create_at lte", field_name="create_at", lookup_expr='lte')
    min_amount = filters.NumberFilter(field_name="amount", lookup_expr='gte')
    max_amount = filters.NumberFilter(field_name="amount", lookup_expr='lte')
    comment = filters.CharFilter(field_name="comment", lookup_expr='icontains')

    class Meta:
        model = BalanceChange
        fields = []


class PaymentsArchiveFilter(django_filters.FilterSet):

    create_at_gte = django_filters.DateTimeFilter(field_name='create_at', lookup_expr='gte')
    create_at_lt = django_filters.DateTimeFilter(field_name='create_at', lookup_expr='lt')

    class Meta:
        model = Payment
        fields = ['create_at_gte', 'create_at_lt', 'status', 'pay_type', 'merchant']


class WithdrawFilter(django_filters.FilterSet):

    create_at_gte = django_filters.DateTimeFilter(field_name='create_at', lookup_expr='gte')
    create_at_lt = django_filters.DateTimeFilter(field_name='create_at', lookup_expr='lt')

    class Meta:
        model = Withdraw
        fields = ['create_at_gte', 'create_at_lt', 'status', 'merchant']
