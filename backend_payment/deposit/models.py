import datetime
import logging
import re

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.transaction import atomic
from django.dispatch import receiver

from django.db.models.signals import post_delete, post_save, pre_save
from django.utils.html import format_html

from payment.models import Payment

logger = logging.getLogger(__name__)
err_log = logging.getLogger('error_log')

# User = get_user_model()


class TrashIncoming(models.Model):

    register_date = models.DateTimeField('Время добавления в базу', auto_now_add=True)
    text = models.CharField('Текст сообщения', max_length=1000)
    worker = models.CharField(max_length=50, null=True)

    def __str__(self):
        string = f'Мусор {self.id} {self.register_date} {self.text[:20]}'
        return string


class Setting(models.Model):
    name = models.CharField('Наименование параметра', unique=True)
    value = models.CharField('Значение параметра', default='')

    def __str__(self):
        return f'Setting({self.name} = {self.value})'


class Incoming(models.Model):

    register_date = models.DateTimeField('Время добавления в базу', auto_now_add=True)
    response_date = models.DateTimeField('Распознанное время', null=True, blank=True)
    recipient = models.CharField('Получатель', max_length=50, null=True, blank=True)
    sender = models.CharField('Отравитель/карта', max_length=50, null=True, blank=True)
    pay = models.FloatField('Платеж')
    balance = models.FloatField('Баланс', null=True, blank=True)
    transaction = models.BigIntegerField('Транзакция', null=True, unique=True, blank=True)
    type = models.CharField(max_length=20, default='unknown')
    worker = models.CharField(max_length=50, null=True, default='manual')
    # image = models.ImageField(upload_to='screens/',
    #                           verbose_name='скрин', null=True, blank=True)
    confirmed_time = models.DateTimeField('Время подтверждения', null=True, blank=True)
    change_time = models.DateTimeField('Время ручной корректировки', null=True, blank=True)
    confirmed_payment = models.OneToOneField('payment.Payment', null=True, blank=True, on_delete=models.SET_NULL,
                                             related_name='link_incoming')
    comment = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        ordering = ('-register_date',)
        permissions = [
            # ("can_hand_edit", "Может делать ручные корректировки"),
            # ("can_see_bad_warning", "Видит уведомления о новых BadScreen"),
        ]

    def __iter__(self):
        for field in self._meta.fields:
            yield field.verbose_name, field.value_to_string(self)

    def __str__(self):
        string = f'Платеж {self.id}. Сумма: {self.pay}'
        return string


@receiver(pre_save, sender=Incoming)
def pre_save_incoming(sender, instance: Incoming, raw, using, update_fields, *args, **kwargs):
    print(f'pre_save_incoming: {instance}')
    if not instance.id:
        # Проверим есть ли заявки с данной карты где карта оканчивается на 4 цифры c такой-же суммой
        last_4_digit_recipient = instance.recipient[-4:]
        target_payments = Payment.objects.filter(
            pay_type='card-to-card',
            pay_requisite__card__card_number__endswith=last_4_digit_recipient,
            amount=instance.pay
        )
        if target_payments.count() == 1:
            # Если такой платеж 1 то сделаем привязку
            target_payment = target_payments.first()
            instance.confirmed_payment = target_payment
            # И подтвердим его и освободим реквизиты уже в payment

            target_payment.status = 9
            # target_payment.pay_requisite = None
            target_payment.save()


@receiver(post_save, sender=Incoming)
def post_save_incoming(sender, instance: Incoming, created, raw, using, update_fields, *args, **kwargs):
    print(f'post_save_incoming: {instance}. created: {created}')
    # if created:
    #     # Проверим есть ли заявки с данной карты
    #     last_4_digit_recipient = instance.recipient[-4:]
    #     target_payments = Payment.objects.filter(pay_requisite__card__card_number__endswith=last_4_digit_recipient)
    #     if target_payments.count() == 1:
    #         target_payments.first()
