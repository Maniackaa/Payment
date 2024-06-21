import django_filters
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import F, Value
from django.db.models.functions import Extract

from payment.models import Payment, Withdraw

User = get_user_model()


class PaymentFilter(django_filters.FilterSet):

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            for name, f in self.base_filters.items():
                initial = f.extra.get('initial')
                if not data.get(name) and initial:
                    data[name] = initial
        super().__init__(data, *args, **kwargs)

    id = django_filters.CharFilter(lookup_expr='icontains')
    order_id = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.MultipleChoiceFilter(choices=Payment.PAYMENT_STATUS)
    oper1 = django_filters.CharFilter(label='Оператор №', method='my_custom_filter', initial=1, max_length=3)
    oper2 = django_filters.CharFilter(label='из', method='my_custom_filter2', initial=1)

    class Meta:
        model = Payment
        fields = ['id', 'order_id', 'status', 'pay_type', 'amount']

    @property
    def qs(self):
        parent = super(PaymentFilter, self).qs
        # result = parent.filter().all()
        # x = result.values('minute')
        # minutes = []
        # for a in x:
        #     minutes.append(a['minute'])
        # print(f'set(minutes): {len(set(minutes))} {sorted(set(minutes))}')
        return parent.filter()

    def my_custom_filter(self, queryset, name, value):
        y = int(self.form['oper2'].value())
        start = 60 / y * (int(value) - 1)
        print(f'start: {start}')
        return queryset.annotate(minute=Extract('create_at', 'minute')).filter(minute__gte=start)

    def my_custom_filter2(self, queryset, name, value):
        x = int(self.form['oper1'].value())
        end = 60 / int(value) * x
        print(f'end: {end}')
        return queryset.annotate(minute=Extract('create_at', 'minute')).filter(minute__lt=end)


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