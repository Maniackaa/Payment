from django_filters import rest_framework as filters

from payment.models import BalanceChange


class BalanceChangeFilter(filters.FilterSet):
    start = filters.IsoDateTimeFilter(label='create_at gte', field_name="create_at", lookup_expr='gte')
    end = filters.IsoDateTimeFilter(label="create_at lte", field_name="create_at", lookup_expr='lte')
    min_amount = filters.NumberFilter(field_name="amount", lookup_expr='gte')
    max_amount = filters.NumberFilter(field_name="amount", lookup_expr='lte')
    comment = filters.CharFilter(field_name="comment", lookup_expr='icontains')

    class Meta:
        model = BalanceChange
        fields = []
