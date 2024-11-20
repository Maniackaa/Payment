import json

import structlog
from django.contrib.auth import get_user_model
from django.core.validators import EmailValidator, MinValueValidator
from django.db import transaction
from django.utils.http import urlsafe_base64_encode
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample, extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import as_serializer_error
from rest_framework import validators

from core.global_func import hash_gen, get_client_ip
from payment.models import Payment, Merchant, CreditCard, PayRequisite, Withdraw, BalanceChange
from payment.views import get_pay_requisite

logger = structlog.get_logger(__name__)


User = get_user_model()


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Создание payment"""
    amount = serializers.DecimalField(required=True, max_digits=8, decimal_places=2)
    confirmed_amount = serializers.DecimalField(read_only=True, max_digits=8, decimal_places=2)
    create_at = serializers.DateTimeField(read_only=True)

    def validate(self, data):
        merchant = data.get('merchant')  # Номер магазина
        user = self.context['request'].user
        if merchant.owner != user:
            raise ValidationError('Is not your merchant')
        pay_type = data.get('pay_type')
        amount = data.get('amount')
        if user.profile.payment_limit_per_minute and not user.profile.limit_check():
            raise ValidationError({'warning': 'exceeded the limit'})

        all_pay_requisite = PayRequisite.objects.filter(pay_type=pay_type).first()
        if not all_pay_requisite:
            raise ValidationError(f'Sorry, service not available in this moment.')
        pay_requisite = get_pay_requisite(pay_type, amount)
        if not pay_requisite:
            raise ValidationError({'warning': 'Try again after 5 seconds'})
        if amount < pay_requisite.min_amount or amount > pay_requisite.max_amount:
            raise ValidationError(f'Amount must be from {pay_requisite.min_amount} to {pay_requisite.max_amount}')
        data['pay_requisite'] = pay_requisite
        request = self.context["request"]
        if merchant.white_ip:
            ip = get_client_ip(request)
            if ip not in merchant.ip_list():
                raise ValidationError(f'Your ip {ip} not in white list')
        return data

    def save(self, **kwargs):
        return super().save(**kwargs)

    class Meta:
        model = Payment
        fields = (
            'id',
            'create_at',
            'merchant',
            'order_id',
            'amount',
            'confirmed_amount',
            'pay_type',
            'user_login',
            'owner_name',
            'status',
            'mask'
        )
        read_only_fields = ('status', 'mask')
        validators = [
            validators.UniqueTogetherValidator(
                queryset=Payment.objects.all(),
                fields=('merchant', 'order_id'),
                message="order_id must be Unique from user"
            ),
        ]


class CardSerializer(serializers.ModelSerializer):
    cvv = serializers.CharField(required=False, min_length=3, max_length=4)

    class Meta:
        model = CreditCard
        fields = (
            'card_number',
            'owner_name',
            'expired_month',
            'expired_year',
            'cvv'
        )

    def validate_card_number(self, data):
        card_number = ''.join([x for x in data if x.isdigit()])
        if all(
                (card_number.isdigit(), len(card_number) == 16)
        ):
            return card_number
        raise ValidationError('card_number must be 16 digits')

    def validate_cvv(self, data):
        if data.isdigit():
            return data
        else:
            raise ValidationError('cvv must be 3-4 digits')


class PaymentInputCardSerializer(serializers.ModelSerializer):
    """Передача данных карты для оплаты"""

    def validate_card_number(self, data):
        card_number = ''.join([x for x in data if x.isdigit()])
        # print(card_number, card_number.isdigit(), len(card_number))
        if all(
                (card_number.isdigit(), len(card_number) == 16)
        ):
            return card_number
        raise ValidationError('card_number must be 16 digits')

    class Meta:
        model = CreditCard
        fields = (
            'card_number',
            'owner_name',
            'expired_month',
            'expired_year',
            'cvv'
        )


class PaymentInputSmsCodeSerializer(serializers.ModelSerializer):
    """Передача кода подтверждения из смс"""
    sms_code = serializers.CharField(min_length=4, max_length=6)

    class Meta:
        model = Payment
        fields = (
            'sms_code',
        )


class PaymentInputPhoneSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate_phone(self, data):
        phone = ''.join([x for x in data if x.isdigit() or x in ['+']])
        if all(
                (phone.startswith('+994'), len(phone) == 13)
        ):
            return phone
        raise ValidationError('Phone format must be +994555001122')


class DummyDetailSerializer(serializers.Serializer):
    status = serializers.IntegerField()
    amount = serializers.CharField()


class PaymentFullSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ('id', 'amount', 'card_data', 'phone_script_data', 'work_operator', 'counter', 'bank_name')
        model = Payment


class PaymentGuestSerializer(serializers.ModelSerializer):
    # phone_name = serializers.CharField(required=False, allow_null=True)

    class Meta:
        fields = ('id', 'status', 'confirmed_amount', 'mask')
        model = Payment

    def validate_status(self, value):
        if self.instance.status in (-1, 9):
            logger.debug(f'Платеж уже обработан: status {self.instance.status}')
            raise serializers.ValidationError("Платеж уже обработан")
        return value

    def save(self, **kwargs):
        phone_name = self.initial_data.get('phone_name')
        if phone_name:
            card_data = json.loads(self.instance.card_data)
            card_data['phone_name'] = phone_name
            self.instance.card_data = json.dumps(card_data)
        return super().save(**kwargs)


class PaymentTypesSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayRequisite
        fields = ('pay_type', 'min_amount', 'max_amount', 'method_info')



class WithdrawCardSerializer(serializers.ModelSerializer):
    cvv = serializers.CharField(required=False, max_length=4, allow_blank=True)
    expired_month = serializers.CharField(required=False, allow_blank=True)
    expired_year = serializers.CharField(required=False, allow_blank=True)
    card_number = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = CreditCard
        fields = (
            'card_number',
            'owner_name',
            'expired_month',
            'expired_year',
            'cvv'
        )

    def validate_card_number(self, data):
        if not data:
            return ''
        card_number = ''.join([x for x in data if x.isdigit()])
        if all(
                (card_number.isdigit(), len(card_number) == 16)
        ):
            return card_number
        raise ValidationError('card_number must be 16 digits')

    def validate_cvv(self, data):
        if not data:
            return ''
        if data.isdigit():
            return data
        else:
            raise ValidationError('cvv must be 3-4 digits')



class WithdrawSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdraw
        fields = ('id', 'withdraw_id', 'amount', 'status', 'payload')


class WithdrawCreateSerializer(serializers.ModelSerializer):
    """Создание заявки на вывод"""
    card_data = WithdrawCardSerializer(required=False, allow_null=True)
    # signature = serializers.CharField()

    class Meta:
        model = Withdraw
        fields = (
            'id',
            'merchant',
            'withdraw_id',
            'card_data',
            'target_phone',
            'amount',
            'payload',
        )
        validators = [
            validators.UniqueTogetherValidator(
                queryset=Withdraw.objects.all(),
                fields=('merchant', 'withdraw_id'),
                message="withdraw_id must be Unique from user"
            ),
        ]

    def validate(self, data):
        merchant = data.get('merchant')
        request = self.context["request"]
        if merchant.white_ip:
            ip = get_client_ip(request)
            if ip not in merchant.ip_list():
                raise ValidationError(f'Your ip {ip} not in white list')
        user = self.context['request'].user
        if merchant.owner != user:
            raise ValidationError('Is not your merchant')
        if merchant.check_balance:
            amount = data.get('amount')
            if amount > user.balance:
                raise ValidationError('Not enough balance')
        if not data.get('card_data', {}).get('card_number') and not data.get('target_phone'):
            raise ValidationError('Нет данных для оплаты')
        return data


class BalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalanceChange
        fields = ('create_at', 'amount', 'current_balance', 'comment')


class PaymentArchiveSerializer(serializers.ModelSerializer):

    class Meta:
        model = Payment
        fields = ("id", "order_id", "pay_type", "create_at", 'merchant', "amount", "confirmed_amount", "comission",
                  "status", "user_login", "owner_name", "bank_str", "mask", "referrer", "confirmed_time",
                  "response_status_code", "comment"
                  )