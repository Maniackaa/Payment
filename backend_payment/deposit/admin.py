from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin
from django_better_admin_arrayfield.forms.fields import DynamicArrayField
from django_better_admin_arrayfield.forms.widgets import DynamicArrayWidget

from deposit.models import Incoming
from payment.models import CreditCard, PayRequisite, Payment, Merchant, PhoneScript, Bank, Withdraw, BalanceChange


class CreditCardAdmin(admin.ModelAdmin):
    pass


class IncomingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'register_date', 'response_date', 'recipient', 'sender', 'pay', 'balance',
    )
    list_filter = ('register_date', 'response_date',
                   # ("register_date", DateRangeFilterBuilder()),
                   # ("response_date", DateRangeQuickSelectListFilterBuilder()),
                   # ("response_date", DateTimeRangeFilterBuilder()),
                   'worker', 'type')
    list_per_page = 1000


admin.site.register(Incoming, IncomingAdmin)
