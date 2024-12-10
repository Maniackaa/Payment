from django.contrib import admin

from balance_checker.models import Wallet, WalletTransaction


class WalletAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'balance', 'currency_code', 'balance_i'
    )


class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'create_at', 'wallet_from', 'wallet_to', 'info'
    )


admin.site.register(Wallet, WalletAdmin)
admin.site.register(WalletTransaction, WalletTransactionAdmin)
