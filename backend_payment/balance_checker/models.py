from django.db import models

from payment.models import CURRENCY_CHOICES



max_digits = 20
decimal_places = 8


class Wallet(models.Model):
    create_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField("Название", max_length=50, unique=True)
    description = models.CharField("Описание", max_length=1000, null=True, blank=True,)
    balance = models.DecimalField(max_digits=max_digits, decimal_places=decimal_places, verbose_name='Баланс', default=0)
    balance_i = models.DecimalField(max_digits=max_digits, decimal_places=decimal_places, null=True, blank=True,
                                    verbose_name='Баланс отображаемый')
    type = models.CharField(max_length=20,
                            choices=[
                                ('robo', 'Робот-скрипт'),
                                ('virtual', 'Виртуальный'),
                                ('digital', 'Цифровой'),
                                ('cash', 'Наличные')
                            ],
                            default='robo')
    exp = models.SmallIntegerField('Разрядность', default=2)
    currency_code = models.CharField(choices=CURRENCY_CHOICES, default='AZN')

    class Meta:
        ordering = ('-create_at',)

    def __str__(self):
        return f'{self.id}. {self.name}'


class WalletTransaction(models.Model):
    create_at = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=16, decimal_places=8, verbose_name='Сумма операции')
    wallet_from = models.ForeignKey(to=Wallet, on_delete=models.PROTECT, related_name='transactions_from')
    wallet_from_balance_before = models.DecimalField(max_digits=max_digits, decimal_places=decimal_places,
                                                     verbose_name='Баланс исходного кошелька до операции')
    wallet_from_balance_after = models.DecimalField(max_digits=max_digits, decimal_places=decimal_places,
                                                     verbose_name='Баланс исходного кошелька после операции')

    wallet_to = models.ForeignKey(to=Wallet, on_delete=models.PROTECT, related_name='transactions_to')
    wallet_to_balance_before = models.DecimalField(max_digits=max_digits, decimal_places=decimal_places,
                                                     verbose_name='Баланс конечного кошелька до операции')
    wallet_to_balance_after = models.DecimalField(max_digits=max_digits, decimal_places=decimal_places,
                                                     verbose_name='Баланс конечного кошелька после операции')
    info = models.CharField(max_length=1000)

    class Meta:
        ordering = ('-create_at',)

    def __str__(self):
        return f'{self.id}. {self.create_at} {self.wallet_from} -> {self.wallet_to}'