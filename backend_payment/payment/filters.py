import django_filters

from payment.models import Payment


class PaymentFilter(django_filters.FilterSet):
    id = django_filters.CharFilter(lookup_expr='icontains')
    order_id = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.MultipleChoiceFilter(choices=Payment.PAYMENT_STATUS)
    class Meta:
        model = Payment
        fields = ['id', 'order_id', 'status', 'pay_type']