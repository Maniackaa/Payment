from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin
from django_better_admin_arrayfield.forms.fields import DynamicArrayField
from django_better_admin_arrayfield.forms.widgets import DynamicArrayWidget

from payment.models import CreditCard, PayRequisite, Payment, Merchant, PhoneScript, Bank, Withdraw


class CreditCardAdmin(admin.ModelAdmin):
    pass


class PayRequisiteAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'card', 'is_active', 'pay_type',
    )
    list_editable = ('is_active',)


class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'merchant', 'order_id', 'amount', 'confirmed_amount', 'confirmed_time', 'pay_requisite',  'screenshot',
        'create_at', 'status', 'change_time', 'confirmed_time',
    )


class WithdrawAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'merchant', 'withdraw_id', 'amount', 'status', 'confirmed_time', 'comment'
    )


class MerchantAdmin(admin.ModelAdmin):
    pass


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


admin.site.register(CreditCard, CreditCardAdmin)
admin.site.register(PayRequisite, PayRequisiteAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(Withdraw, WithdrawAdmin)
admin.site.register(Merchant, MerchantAdmin)
admin.site.register(PhoneScript, PhoneScriptAdmin)
admin.site.register(Bank, BankAdmin)
