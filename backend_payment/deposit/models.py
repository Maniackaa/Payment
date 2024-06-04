import datetime
import logging
import re

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.transaction import atomic
from django.dispatch import receiver

from django.db.models.signals import post_delete, post_save
from django.utils.html import format_html


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


SITE_VAR = {
    'last_message_time': datetime.datetime.now(),
    'last_good_screen_time': datetime.datetime.now(),
}


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
    image = models.ImageField(upload_to='screens/',
                              verbose_name='скрин', null=True, blank=True)
    birpay_confirm_time = models.DateTimeField('Время подтверждения', null=True, blank=True)
    birpay_edit_time = models.DateTimeField('Время ручной корректировки', null=True, blank=True)
    confirmed_deposit = models.OneToOneField('Deposit', null=True, blank=True, on_delete=models.SET_NULL)
    birpay_id = models.CharField('id платежа с birpay', max_length=15, null=True, blank=True)
    comment = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        permissions = [
            ("can_hand_edit", "Может делать ручные корректировки"),
            # ("can_see_bad_warning", "Видит уведомления о новых BadScreen"),
        ]

    def __iter__(self):
        for field in self._meta.fields:
            yield field.verbose_name, field.value_to_string(self)

    def __str__(self):
        string = f'Платеж {self.id}. Сумма: {self.pay} ({self.balance}). {self.transaction}.  Депозит: {self.confirmed_deposit.id if self.confirmed_deposit else "-"}'
        return string

    def phone_serial(self):
        """Достает серийные номер из пути изображения"""
        if not self.image:
            return None
        from_part = self.image.name.split('_from_')
        if len(from_part) == 2:
            return from_part[1][:-4]
        return 'unknown'
