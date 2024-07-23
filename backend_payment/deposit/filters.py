import django_filters
from django import forms

from deposit.models import Incoming


class MyDateInput(forms.DateInput):
    input_type = 'date'
    format = '%Y-%m-%d'


class IncomingFilter(django_filters.FilterSet):
    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            for name, f in self.base_filters.items():
                initial = f.extra.get('initial')
                if not data.get(name) and initial:
                    data[name] = initial
        super().__init__(data, *args, **kwargs)

    register_date = django_filters.DateFilter(label='create_at', lookup_expr='contains',
                                             widget=MyDateInput({'class': 'form-control'}))
    m10 = django_filters.ChoiceFilter(label='m10', method='my_custom_filter', choices=[(1, 'Только М10'), ('2', 'Только смс')])

    def my_custom_filter(self, queryset, name, value):
        print(name, value)
        if value == '1':
            return queryset.filter(transaction__isnull=False)
        elif value == '2':
            return queryset.filter(transaction__isnull=True)
        else:
            return queryset

    @property
    def qs(self):
        parent = super(IncomingFilter, self).qs
        return parent.filter()

    class Meta:
        model = Incoming
        fields = ['register_date', 'transaction']

