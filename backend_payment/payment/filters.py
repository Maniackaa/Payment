import datetime

import django_filters
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import F, Value
from django.db.models.functions import Extract
from django.forms import DateTimeInput
from django.utils import timezone
from django_currentuser.middleware import get_current_authenticated_user

from payment.models import Payment, Withdraw, BalanceChange, Bank
from users.models import SupportOptions

User = get_user_model()


class MyDateInput(forms.DateInput):
    input_type = 'date'
    format = '%Y-%m-%d'


class BalanceStaffFilter(django_filters.FilterSet):
    # История баланса для персонала
    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            for name, f in self.base_filters.items():
                initial = f.extra.get('initial')
                if not data.get(name) and initial:
                    data[name] = initial
        super().__init__(data, *args, **kwargs)

    create_at = django_filters.DateFilter(field_name='create_at', lookup_expr='contains',
                                             widget=MyDateInput({'class': 'form-control'}))

    @property
    def qs(self):
        parent = super(BalanceStaffFilter, self).qs
        return parent.filter()

    class Meta:
        model = BalanceChange
        fields = ['create_at', 'user']


class BalanceFilter(django_filters.FilterSet):
    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            for name, f in self.base_filters.items():
                initial = f.extra.get('initial')
                if not data.get(name) and initial:
                    data[name] = initial
        super().__init__(data, *args, **kwargs)

    create_at = django_filters.DateFilter(field_name='create_at', lookup_expr='contains',
                                             widget=MyDateInput({'class': 'form-control'}))

    @property
    def qs(self):
        parent = super(BalanceFilter, self).qs
        return parent.filter()

    class Meta:
        model = BalanceChange
        fields = ['create_at']


class MerchPaymentFilter(django_filters.FilterSet):

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
    create_at = django_filters.DateFilter(label='За день', field_name='create_at', lookup_expr='contains',
                                             widget=MyDateInput({'class': 'form-control'}))

    create_start = django_filters.DateFilter(label='От', field_name='create_at', lookup_expr='gte',
                                             widget=MyDateInput({'class': 'form-control'})
                                             )
    create_end = django_filters.DateFilter(label='До', field_name='create_at', lookup_expr='lt',
                                             widget=MyDateInput({'class': 'form-control'})
                                             )
    user_login = django_filters.CharFilter(lookup_expr='icontains')
    owner_name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Payment
        fields = ['id', 'order_id', 'status', 'pay_type', 'amount', 'create_at',]

    @property
    def qs(self):
        parent = super(MerchPaymentFilter, self).qs
        return parent.filter()


class MyTimeInput(forms.DateInput):
    input_type = 'datetime-local'


class PaymentStatFilter(django_filters.FilterSet):
    # Фильтр для статы

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            for name, f in self.base_filters.items():
                initial = f.extra.get('initial')
                if not data.get(name) and initial:
                    data[name] = initial
        super().__init__(data, *args, **kwargs)
    from_initial = '2024-10-01T00:00'

    now = timezone.now()
    year = now.year
    month = (now.month + 1)
    if month > 12:
        month = month % 12
        year += 1
    to_initial = datetime.datetime(year, month, 1, 0, 0).isoformat()[:16]

    create_at_from = django_filters.DateTimeFilter(
        label='От',
        field_name='create_at',
        lookup_expr='gte',
        widget=MyTimeInput({'class': 'form-control', 'value': from_initial})
    )
    create_at_to = django_filters.DateTimeFilter(
        label='до',
        field_name='create_at',
        lookup_expr='lt',
        widget=MyTimeInput({'class': 'form-control', 'value': to_initial})
                                                 )

    class Meta:
        model = Payment
        fields = ['pay_type', 'merchant', 'merchant__owner', 'bank']

    @property
    def qs(self):
        parent = super(PaymentStatFilter, self).qs
        return parent.filter()


class PaymentFilter(django_filters.FilterSet):
    # Фильтр где весь список заявок для оперов

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            for name, f in self.base_filters.items():
                initial = f.extra.get('initial')
                if not data.get(name) and initial:
                    data[name] = initial
        # profile = get_current_authenticated_user().profile
        # data['on_work'] = profile.on_work
        super().__init__(data, *args, **kwargs)

    id = django_filters.CharFilter(lookup_expr='icontains')
    order_id = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.MultipleChoiceFilter(choices=Payment.PAYMENT_STATUS)
    # oper1 = django_filters.NumberFilter(label='Оператор №', method='my_custom_filter', initial=1)
    # oper2 = django_filters.NumberFilter(label='из', method='my_custom_filter2', initial=1)
    create_at = django_filters.DateFilter(field_name='create_at', lookup_expr='contains',
                                          widget=MyDateInput({'class': 'form-control'}))
    on_work = django_filters.BooleanFilter(method='operators_filter',
                                           widget=forms.CheckboxInput(attrs={'disabled': False}),
                                           label='Только твои', )

    class Meta:
        model = Payment
        fields = ['id', 'order_id', 'status', 'pay_type', 'amount', 'merchant', 'merchant__owner', 'bank']

    @property
    def qs(self):
        parent = super(PaymentFilter, self).qs
        return parent.filter()


    # def my_custom_filter(self, queryset, name, value):
    #     y = int(self.form['oper2'].value())
    #     start = 60 / y * (int(value) - 1)
    #     return queryset.annotate(minute=Extract('create_at', 'minute')).filter(minute__gte=start)
    #
    # def my_custom_filter2(self, queryset, name, value):
    #     x = int(self.form['oper1'].value())
    #     end = 60 / int(value) * x
    #     return queryset.annotate(minute=Extract('create_at', 'minute')).filter(minute__lt=end)

    def operators_filter(self, queryset, name, value):
        if value is True:
            # Работает фильтр по операм
            operators_on_work = SupportOptions.load().operators_on_work
            user_id = str(get_current_authenticated_user().id)
            return queryset.filter(pay_type='card_2').filter(status__in=[3, 4, 5, 6, 7]).filter(
                    work_operator=user_id).order_by('counter')
        return queryset


class WithdrawFilter(django_filters.FilterSet):
    id = django_filters.CharFilter(lookup_expr='icontains')
    withdraw_id = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.MultipleChoiceFilter(choices=Withdraw.WITHDRAW_STATUS)
    create_at = django_filters.DateFilter(label='За день', field_name='create_at', lookup_expr='contains',
                                          widget=MyDateInput({'class': 'form-control'}))

    create_start = django_filters.DateFilter(label='От', field_name='create_at', lookup_expr='gte',
                                             widget=MyDateInput({'class': 'form-control'})
                                             )
    create_end = django_filters.DateFilter(label='До', field_name='create_at', lookup_expr='lt',
                                             widget=MyDateInput({'class': 'form-control'})
                                             )

    class Meta:
        model = Payment
        fields = ['id', 'withdraw_id', 'status', 'create_at']


class BalanceChangeFilter(django_filters.FilterSet):
    user = django_filters.ModelChoiceFilter(queryset=User.objects.filter(role='merchant'))
    class Meta:
        model = Payment
        fields = ['user']


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