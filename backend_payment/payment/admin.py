from django import forms
from django.conf import settings
from django.contrib import admin
from django.db.models import TextField
from django.utils.html import format_html
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin
from django_better_admin_arrayfield.forms.fields import DynamicArrayField
from django_better_admin_arrayfield.forms.widgets import DynamicArrayWidget
from django.forms import widgets
from django.db import models
from payment.models import CreditCard, PayRequisite, Payment, Merchant, PhoneScript, Bank, Withdraw, BalanceChange
from users.models import SupportOptions


class CreditCardAdmin(admin.ModelAdmin):
    pass


class PayReqForm(forms.ModelForm):
  info = forms.CharField(widget=forms.Textarea(attrs={'rows': 10, 'cols': 80}), required=False)
  class Meta:
    model = PayRequisite
    fields = ('__all__')


class PayRequisiteAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'card', 'is_active', 'pay_type',
    )
    list_editable = ('is_active',)
    form = PayReqForm


class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'create_at', 'merchant', 'order_id', 'amount',
        'status', 'card_number', 'sms_code', 'bank_name', 'response_status_code'
    )
    list_filter = ('merchant', 'pay_requisite', 'response_status_code', 'pay_type', 'work_operator')
    list_select_related = ['merchant', 'pay_requisite', 'bank', 'work_operator',
                           'confirmed_incoming', 'confirmed_user', 'merchant__owner']

    # Кастомное поле
    # def card_number(self, obj):
    #     return obj.id
    # order_number.short_description = 'Номер заказа'


class WithdrawAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'merchant', 'withdraw_id', 'amount', 'status', 'confirmed_time', 'response_status_code', 'comment'
    )
    list_filter = ('merchant', 'status', 'response_status_code')


class BalanceChangeAdmin(admin.ModelAdmin):
    list_display = (
        'create_at', 'user', 'comment', 'amount', 'current_balance'
    )
    list_filter = ('user',)


class MerchantAdmin(admin.ModelAdmin, DynamicArrayMixin):
    list_display = (
        'id', 'name', 'owner', 'host', 'is_new'
    )


class PhoneScriptAdmin(admin.ModelAdmin, DynamicArrayMixin):
    list_display = (
        'id', 'name', 'step_2_required', 'step_2_x', 'step_2_y', 'step_3_x', 'step_3_y'
    )


class BankAdmin(admin.ModelAdmin, DynamicArrayMixin):
    list_display = (
        'id', 'name', 'script', 'pic'
    )
    list_display_links = ('id', 'name')

    def pic(self, obj):  # receives the instance as an argument
        return format_html('<img height="50" src="{host}{thumb}"/>'.format(
            host='https://asu-payme.com', thumb=obj.image.url,
        ))
    pic.allow_tags = True
    pic.short_description = 'sometext'


class SupportOptionsAdmin(admin.ModelAdmin):
    list_display = (
        'operators_on_work',
    )


admin.site.register(SupportOptions, SupportOptionsAdmin)
admin.site.register(CreditCard, CreditCardAdmin)
admin.site.register(PayRequisite, PayRequisiteAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(BalanceChange, BalanceChangeAdmin)
admin.site.register(Withdraw, WithdrawAdmin)
admin.site.register(Merchant, MerchantAdmin)
admin.site.register(PhoneScript, PhoneScriptAdmin)
admin.site.register(Bank, BankAdmin)
