import json
import threading
import uuid
from decimal import Decimal
from typing import Any

import pytz
import structlog
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import F, Sum, Model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django_better_admin_arrayfield.models.fields import ArrayField
from django_currentuser.middleware import get_current_user, get_current_authenticated_user

from core.global_func import hash_gen, TZ
from deposit.text_response_func import tz
from payment.task import send_payment_webhook, send_withdraw_webhook, send_message_tg_task

logger = structlog.get_logger(__name__)

User = get_user_model()


class Merchant(models.Model):
    is_new = models.BooleanField(verbose_name='Новенький', default=1)
    name = models.CharField('Название', max_length=100)
    owner = models.ForeignKey(to=User, related_name='merchants', on_delete=models.CASCADE)
    host = models.URLField('Адрес для отправки вэбхук')
    host_withdraw = models.URLField('Вэбхук для отправки withdraw.', default='')
    secret = models.CharField('Your secret key', max_length=1000)
    # Endpoints
    pay_success_endpoint = models.URLField('Default Url for redirect user back to your site', null=True, blank=True)

    def stat(self):
        confirmed_payments = self.payments.filter(status=9)
        count = confirmed_payments.count()
        result = confirmed_payments.aggregate(total_sum=Sum('confirmed_amount'))
        print(result)
        return {
            'count': count,
            'total_sum': result['total_sum']}

    def __str__(self):
        return f'Shop {self.id}. ({self.owner}) {self.name}'

    class Meta:
        ordering = ('id',)


@receiver(post_save, sender=Merchant)
def after_save_shop(sender, instance: Merchant, created, raw, using, update_fields, *args, **kwargs):
    logger.debug(f'after_save_shop {created}')
    if created:
        text = (f'Создан новый магазин id {instance.id}:\n'
                f'{instance.name}\n'
                f'{instance.owner}')
        send_message_tg_task.delay(text, settings.ADMIN_IDS)


class BalanceChange(models.Model):
    create_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='balance_history')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Изменение баланса')
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Текущий баланс', null=True)
    comment = models.CharField(null=True, blank=True)

    class Meta:
        ordering = ('-create_at',)

    def __str__(self):
        return f'{self.id}. {self.create_at} {self.comment} {self.amount}: {self.current_balance}'


class CreditCard(models.Model):
    card_number = models.CharField('Номер карты', max_length=19)
    owner_name = models.CharField('Имя владельца', max_length=100, null=True, blank=True)
    cvv = models.CharField(max_length=4, null=True, blank=True)
    card_type = models.CharField('Система карты', max_length=100)
    card_bank = models.CharField('Название банка', max_length=50, default='Bank')
    expired_month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    expired_year = models.IntegerField(validators=[MinValueValidator(20), MaxValueValidator(40)])
    status = models.CharField('Статус карты',
                              default='not_active',
                              choices=[
                                  ('active', 'Активна'),
                                  ('not_active', 'Не активна'),
                                  ('blocked', 'Заблокирована')
                              ])

    def __repr__(self):
        string = f'{self.__class__.__name__} ({self.id}){self.card_number}'
        return string

    def __str__(self):
        string = f'СС {self.id}. {self.card_number}'
        return string


PAY_TYPE = (
        ('card-to-card', 'card-to-card'),
        ('card_2', 'card_2'),
    )


class PayRequisite(models.Model):

    pay_type = models.CharField('Тип платежа', choices=PAY_TYPE)
    card = models.OneToOneField(to=CreditCard, on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=False)
    info = models.CharField('Инструкция для пользователя', null=True, blank=True)
    method_info = models.CharField('Описание метода', null=True, blank=True)
    min_amount = models.IntegerField(default=0)
    max_amount = models.IntegerField(default=10000)

    def __repr__(self):
        string = f'{self.__class__.__name__}({self.id})'
        return string

    def __str__(self):
        string = f'{self.pay_type} {self.id}. {self.card}'
        return string


class Withdraw(models.Model):
    WITHDRAW_STATUS = (
        (-1, '-1. Decline'),
        (0, '0. Created'),
        (9, '9. Confirmed'),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cached_status = self.status

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, max_length=36, db_index=True,
                          unique=True, )
    merchant = models.ForeignKey('Merchant', verbose_name='Shop', on_delete=models.CASCADE, related_name='withdraws')
    withdraw_id = models.CharField(max_length=36, db_index=True)
    amount = models.IntegerField('Сумма заявки', validators=[MinValueValidator(30), MaxValueValidator(10000)])
    payload = models.JSONField(default=str, blank=True, null=True)
    create_at = models.DateTimeField('Время добавления в базу', auto_now_add=True)
    status = models.IntegerField('Статус заявки',
                                 default=0,
                                 choices=WITHDRAW_STATUS)
    change_time = models.DateTimeField('Время изменения в базе', auto_now=True)
    card_data = models.JSONField(default=str, blank=True)
    confirmed_time = models.DateTimeField('Время подтверждения', null=True, blank=True)
    confirmed_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.CharField('Комментарий', max_length=1000, null=True, blank=True)
    response_status_code = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ('-create_at',)

    def status_str(self):
        for status_num, status_str in self.WITHDRAW_STATUS:
            if status_num == self.status:
                return status_str

    def balance(self):
        return self.merchant.owner.balance

    def webhook_data(self):
        if self.status == 9:
            data = {
                "id": str(self.id),
                "withdraw_id": self.withdraw_id,
                "amount": self.amount,
                "create_at": self.create_at.isoformat(),
                "status": self.status,
                "confirmed_time": self.confirmed_time.isoformat(),
            }
        elif self.status == -1:
            data = {
                'withdraw_id': self.withdraw_id,
                'id': str(self.id),
                'status': -1,
            }
        else:
            data = {}
        return data


class Payment(models.Model):
    PAYMENT_STATUS = (
        (-1, '-1. Decline'),
        (0, '0. Created'),
        (3, '3. CardData input.'),
        (4, '4. Send to work'),
        (5, '5. Wait Sms'),
        (6, '6. Sms input'),
        (7, '7. Await confirm'),
        (9, '9. Confirmed'),
    )

    def __init__(self, *args, **kwargs) -> None:
        # logger.debug(f'__init__ Payment {args} {kwargs}')
        super().__init__(*args, **kwargs)
        self.cached_status = self.status

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, max_length=36, db_index=True, unique=True,)
    merchant = models.ForeignKey('Merchant', on_delete=models.CASCADE, related_name='payments')
    order_id = models.CharField(max_length=36, db_index=True)
    amount = models.IntegerField('Сумма заявки', null=True)

    user_login = models.CharField(max_length=36, null=True, blank=True)
    owner_name = models.CharField(max_length=100, null=True, blank=True)
    pay_requisite = models.ForeignKey('PayRequisite', on_delete=models.CASCADE, null=True, blank=True)
    pay_type = models.CharField('Тип платежа', choices=PAY_TYPE)
    screenshot = models.ImageField(upload_to='uploaded_pay_screens/',
                      verbose_name='Ваша квитанция', null=True, blank=True, help_text='Приложите скриншот квитанции после оплаты')
    create_at = models.DateTimeField('Время добавления в базу', auto_now_add=True)
    # create_at = models.DateTimeField('Время добавления в базу', auto_now_add=False)
    status = models.IntegerField('Статус заявки',
                                 default=0,
                                 choices=PAYMENT_STATUS)
    change_time = models.DateTimeField('Время изменения в базе', auto_now=True)
    cc_data_input_time = models.DateTimeField('Время ввода данных карты', null=True, blank=True)

    # Данные отправителя
    phone = models.CharField('Телефон отправителя', max_length=20, null=True, blank=True)
    referrer = models.URLField('Ссылка для возврата', null=True, blank=True)
    card_data = models.JSONField(default=str, blank=True)
    phone_script_data = models.JSONField(default=str, blank=True)

    # Подтверждение:
    confirmed_amount = models.IntegerField('Подтвержденная сумма заявки', null=True, blank=True)
    confirmed_time = models.DateTimeField('Время подтверждения', null=True, blank=True)
    confirmed_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    confirmed_incoming = models.OneToOneField(
        verbose_name='Связанное смс Incoming', to='deposit.Incoming', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='link_payment')
    comment = models.CharField('Комментарий', max_length=1000, null=True, blank=True)
    response_status_code = models.IntegerField(null=True, blank=True)
    source = models.CharField(max_length=5, default='form', null=True, blank=True)

    def __str__(self):
        string = f'{self.__class__.__name__} {self.id}'
        return string

    def get_pay_data(self):
        card = self.pay_requisite.card
        return {
            'card_number': card.card_number,
            'card_bank': card.card_bank,
            'expired_month': card.expired_month,
            'expired_year': card.expired_year,
        }

    def status_str(self):
        for status_num, status_str in self.PAYMENT_STATUS:
            if status_num == self.status:
                return status_str

    def card_data_str(self):
        if not self.card_data:
            return ''
        data = json.loads(self.card_data)
        result = ''
        for k, v in data.items():
            result += f'{v} '
        return result

    def operator(self):
        if not self.card_data:
            return ''
        return json.loads(self.card_data).get('operator')

    def card_number(self):
        if not self.card_data:
            return ''
        data = json.loads(self.card_data)
        return data.get('card_number')

    def bank_name(self) -> str:
        card_num = self.card_number()

        if card_num:
            bank = Bank.objects.filter(bins__contains=[card_num[:6]]).first()
            if bank:
                return bank.name
        return 'default'

    def expired_month(self):
        if not self.card_data:
            return ''
        data = json.loads(self.card_data)
        return data.get('expired_month')

    def expired_year(self):
        if not self.card_data:
            return ''
        data = json.loads(self.card_data)
        return data.get('expired_year')

    def sms_code(self):
        if not self.card_data:
            return ''
        data = json.loads(self.card_data)
        return data.get('sms_code')

    def cvv(self):
        if not self.card_data:
            return ''
        data = json.loads(self.card_data)
        return data.get('cvv')

    def card_data_url(self):
        import urllib.parse
        if not self.card_data:
            return ''
        data = json.loads(self.card_data)
        query = urllib.parse.urlencode(data)
        return query

    def phone_script_data_url(self):
        import urllib.parse
        if not self.phone_script_data:
            return ''
        data = json.loads(self.phone_script_data)
        query = urllib.parse.urlencode(data)
        return query

    def short_id(self):
        return f'{str(self.id)[-6:]}'

    def get_hash(self):
        if self.status == -1:
            return hash_gen(f'{str(self.id)}{self.order_id}{self.status}', self.merchant.secret)
        if self.status == 9:
            return hash_gen(f'{str(self.id)}{self.order_id}{self.confirmed_amount}{self.status}', self.merchant.secret)
        if self.status in [3, 5]:
            card_data = json.loads(self.card_data)
            return hash_gen(f'{card_data["card_number"]}', self.merchant.secret)

    def webhook_data(self):
        if self.status == 9:
            data = {
                "id": str(self.id),
                "order_id": self.order_id,
                "user_login": self.user_login,
                "amount": self.amount,
                "create_at": self.create_at.isoformat(),
                "status": self.status,
                "confirmed_time": self.confirmed_time.isoformat(),
                "confirmed_amount": self.confirmed_amount,
                "signature": self.get_hash()
            }
        elif self.status == 5:
            data = {
                'order_id': self.order_id,
                'id': str(self.id),
                'status': 5,
                'signature': self.get_hash()
            }
        elif self.status == -1:
            data = {
                'order_id': self.order_id,
                'id': str(self.id),
                'status': -1,
                'signature': self.get_hash()
            }
        else:
            data = {}
        return data

    class Meta:
        ordering = ('-create_at',)


class PaymentLog(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(to=User, null=True, blank=True, on_delete=models.CASCADE)
    create_at = models.DateTimeField('Время добавления в базу', auto_now_add=True)
    changes = models.JSONField()

    def __str__(self):
        return f'{self.create_at.astimezone(tz=TZ)} {self.user} {self.changes}'


class PhoneScript(models.Model):
    name = models.CharField('Наименование', unique=True)
    step_1 = models.BooleanField('Шаг 1. Ввод карты', default=1)
    step_2_required = models.BooleanField('Нужен ли ввод смс', default=1)
    step_2_x = models.IntegerField('Тап x для ввода смс', null=True, blank=True)
    step_2_y = models.IntegerField('Тап y для ввода смс', null=True, blank=True)
    # auto_step_3 = models.BooleanField('Шаг 3 авто', default=0)
    step_3_x = models.IntegerField('Тап x для подтверждения смс', null=True, blank=True)
    step_3_y = models.IntegerField('Тап y для подтверждения смс', null=True, blank=True)
    # bins = ArrayField(base_field=models.IntegerField(), default=list, blank=True)

    def data_json(self):
        data = {}
        keys = ['name', 'step_1', 'step_2_required', 'step_2_x', 'step_2_y', 'step_3_x', 'step_3_y']
        for k, v in self.__dict__.items():
            if k in keys and v:
                data[k] = v
        return json.dumps(data, ensure_ascii=False)

    def __str__(self):
        return f'PhoneScript("{self.name}")'

    def __repr__(self):
        return f'PhoneScript("{self.name}")'


class Bank(models.Model):
    name = models.CharField('Наименование', unique=True)
    bins = ArrayField(base_field=models.IntegerField(), default=list, blank=True)
    script = models.ForeignKey('PhoneScript', on_delete=models.CASCADE)
    instruction = models.CharField('Инструкция', null=True, blank=True)
    image = models.ImageField('Иконка банка', upload_to='bank_icons', null=True, blank=True)


@receiver(pre_save, sender=Withdraw)
def pre_save_withdraw(sender, instance: Withdraw, raw, using, update_fields, *args, **kwargs):
    logger.debug(f'pre_save_status = {instance.status} cashed: {instance.cached_status}')
    # Если статус изменился на 9 (потвержден):
    if instance.status == 9 and instance.cached_status != 9:
        if not instance.confirmed_time:
            instance.confirmed_time = timezone.now()


@receiver(post_save, sender=Withdraw)
def after_save_withdraw(sender, instance: Withdraw, created, raw, using, update_fields, *args, **kwargs):
    try:
        logger.debug(f'post_save_status = {instance.status}  cashed: {instance.cached_status}')
        # Если статус изменился на 9 (потвержден):
        if instance.status == 9 and instance.cached_status != 9:
            logger.info('Выполняем действие после подтверждения выплаты')
            # Минусуем баланс
            with transaction.atomic():
                user = User.objects.get(pk=instance.merchant.owner.id)
                tax = round(instance.amount * user.withdraw_tax / 100, 2)
                logger.info(f'user: {user}. {user.balance} -> {user.balance - Decimal(f"{instance.amount}") - Decimal(f"{tax}")}')
                user.balance = F('balance') - Decimal(f"{instance.amount}") - Decimal(f"{tax}")
                user.save()
                user = User.objects.get(pk=instance.merchant.owner.id)
                logger.info(f'New balance: {user.balance}')
                # Фиксируем историю
                new_log = BalanceChange.objects.create(
                    user=user,
                    amount=- instance.amount - tax,
                    comment=f'Withdraw {instance.amount} ₼: {instance.id}. {-instance.amount - tax} ₼. (Tax: {tax} ₼)',
                    current_balance=user.balance
                )
                new_log.save()

            # Отправляем вэбхук
            data = instance.webhook_data()
            result = send_withdraw_webhook.delay(url=instance.merchant.host_withdraw or instance.merchant.host, data=data)
            logger.info(f'answer: {result}')

        # Если статус изменился на -1 (Отклонен):
        if instance.status == -1 and instance.cached_status != -1:
            logger.info('Выполняем действие после отклонения платежа')
            data = instance.webhook_data()
            result = send_withdraw_webhook.delay(url=instance.merchant.host_withdraw or instance.merchant.host, data=data)
            logger.info(f'answer: {result}')
    except Exception as err:
        logger.error(f'Ошибка при сохранении Withdraw: {err}')


@receiver(pre_save, sender=Payment)
def pre_save_pay(sender, instance: Payment, raw, using, update_fields, *args, **kwargs):
    logger.debug(f'pre_save_status = {instance.status} cashed: {instance.cached_status}')
    # Если статус изменился на 9 (потвержден):
    if instance.status == 9 and instance.cached_status != 9:
        if not instance.confirmed_time:
            # instance.confirmed_time = datetime.datetime.now(tz=TZ)
            instance.confirmed_time = timezone.now()
        if not instance.confirmed_amount:
            instance.confirmed_amount = instance.amount
        # Осободим реквизиты
        instance.pay_requisite = None
        if not instance.confirmed_user:
            instance.confirmed_user = get_current_authenticated_user()

    # Если статус изменился на -1 (Отклонен):
    if instance.status == -1 and instance.cached_status != -1:
        # Осободим реквизиты
        instance.pay_requisite = None
        if not instance.confirmed_user:
            instance.confirmed_user = get_current_authenticated_user()

    # Сохранение лога
    try:
        logger.debug('Сохранение лога')
        old = Payment.objects.filter(pk=instance.id).first()
        if old:
            changes = {}
            fields = ['amount', 'confirmed_amount', 'status', 'comment']
            for field in fields:
                if hasattr(instance, field):
                    new_value = getattr(instance, field)
                    if new_value != getattr(old, field):
                        changes[field] = new_value
            logger.debug(f'Изменения {get_current_authenticated_user()}: {changes} ')
            if changes:
                user = get_current_authenticated_user()
                log = PaymentLog.objects.create(payment=instance, user=user, changes=json.dumps(changes))

    except Exception as err:
        logger.error(f'Ошибка сохранения лога: {err}')


@receiver(post_save, sender=Payment)
def after_save_pay(sender, instance: Payment, created, raw, using, update_fields, *args, **kwargs):
    logger.debug(f'post_save_status = {instance.status}  cashed: {instance.cached_status}')

    # Если статус изменился на 9 (потвержден):
    if instance.status == 9 and instance.cached_status != 9:
        logger.info('Выполняем действие полсле подтверждения платежа')
        # Плюсуем баланс
        with transaction.atomic():
            user = User.objects.get(pk=instance.merchant.owner.id)
            tax = round(instance.confirmed_amount * user.tax / 100)

            logger.info(f'user: {user}. {user.balance} -> {user.balance} + {instance.confirmed_amount} - {tax} = {user.balance + instance.confirmed_amount - tax}')
            user.balance = F('balance') + Decimal(str(instance.confirmed_amount)) - Decimal(str(tax))
            user.save()
            user.refresh_from_db()
            new_balance = user.balance
            # Фиксируем историю
            new_log = BalanceChange.objects.create(
                user=user,
                amount=instance.confirmed_amount - tax,
                comment=f'From payment {instance.confirmed_amount} ₼: {instance.id}. +{instance.confirmed_amount - tax} ₼. (Tax: {tax} ₼).',
                current_balance=new_balance
            )
            new_log.save()
            logger.debug(f'new_balance: {new_balance}')


        # Отправляем вэбхук
        data = instance.webhook_data()
        result = send_payment_webhook.delay(url=instance.merchant.host, data=data)
        logger.info(f'answer: {result}')
    
    # Отправка вэбхука если статус изменился на 5 - ожидание смс и api:
    if instance.source == 'api' and instance.status == 5 and instance.cached_status != 5:
        data = instance.webhook_data()
        result = send_payment_webhook.delay(url=instance.merchant.host, data=data)
        logger.info(f'answer: {result}')

    # Если статус изменился на -1 (Отклонен):
    if instance.status == -1 and instance.cached_status != -1:
        logger.info('Выполняем действие после отклонения платежа')
        data = instance.webhook_data()
        result = send_payment_webhook.delay(url=instance.merchant.host, data=data)
        logger.info(f'answer: {result}')

    if created:
        try:
            # if instance.merchant and instance.merchant.is_new is True:
            if instance.merchant:
                text = f'Новая заявка payment\nОт {instance.merchant}\nТип {instance.pay_type} на {instance.amount} ₼'
                send_message_tg_task.delay(text, settings.ALARM_IDS)
        except Merchant.DoesNotExist:
            pass
