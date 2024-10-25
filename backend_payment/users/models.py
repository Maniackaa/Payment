import datetime

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.core.mail import send_mail
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin, Group
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from users.managers import UserManager


class WhiteListMerchant(models.Model):
    name = models.CharField('Наименование', unique=True)
    email = models.EmailField(unique=True)


class User(AbstractBaseUser, PermissionsMixin):
    username_validator = UnicodeUsernameValidator()

    USER = "user"
    STAFF = "staff"
    STAFF_PLUS = "staff+"
    ADMIN = "admin"
    MODERATOR = "editor"
    MERCHANT = "merchant"
    MERCHVIEWER = "merchviewer"
    ROLES = (
        (USER, "Пользователь"),
        (ADMIN, "Администратор"),
        (STAFF, "Оператор"),
        (STAFF_PLUS, "Оператор+"),
        (MODERATOR, "Корректировщик"),
        (MERCHANT, "Мерчант"),
        (MERCHVIEWER, "Помощник мерча")
    )

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    # id = models.UUIDField(primary_key=True, default=uuid4, editable=False, db_index=True)

    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[username_validator],
    )

    email = models.EmailField(
        verbose_name="Email-адрес",
        null=False,
        blank=False
    )

    role = models.CharField(
        max_length=20,
        choices=ROLES,
        default=USER,
    )

    objects = UserManager()

    balance = models.DecimalField('Баланс', max_digits=18, decimal_places=2, default=0)
    tax = models.FloatField('Комиссия card_2', default=9)
    tax_m10 = models.FloatField('Комиссия m10_to_m10', default=7)
    tax_card = models.FloatField('Комиссия card-to-card', default=7)
    withdraw_tax = models.FloatField('Комиссия на вывод', default=2)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ('id',)

    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.id}. {self.username}'

    def get_short_name(self):
        return self.email

    def get_full_name(self):
        return self.username

    def email_user(self, subject, message, from_email=None, **kwargs):
        send_mail(subject, message, from_email, [self.email], **kwargs)

    def group(self):
        user_groups = self.groups.values('name')
        group_list = []
        for group in user_groups:
            group_list.append(group.get('name'))
        return group_list

    def is_white(self):
        print('WhiteListMerchant:', WhiteListMerchant.objects.all())
        print(self.email)
        return WhiteListMerchant.objects.filter(email=self.email).exists()

    @admin.display(boolean=True, description='Видит уведомления?')
    def bad_warning(self):
        return self.profile.view_bad_warning


@receiver(pre_save, sender=User)
def pre_save_user(sender, instance: User, raw, using, update_fields, *args, **kwargs):
    if instance.is_white():
        instance.is_active = 1
        instance.role = 'merchant'


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        instance.profile = Profile.objects.create(user=instance,
                                                  my_filter=[])
    instance.profile.save()


class Profile(models.Model):
    user = models.OneToOneField(
        verbose_name="Пользователь", to=User, on_delete=models.CASCADE
    )

    first_name = models.CharField(
        verbose_name="Имя",
        max_length=30,
        null=True,
        blank=True
    )
    last_name = models.CharField(
        verbose_name="Фамилия",
        max_length=150,
        null=True,
        blank=True
    )

    my_filter = models.JSONField('Фильтр по получателю', default=list, blank=True)
    my_filter2 = models.JSONField('Фильтр по получателю2', default=list, blank=True)
    my_filter3 = models.JSONField('Фильтр по получателю3', default=list, blank=True)
    view_bad_warning = models.BooleanField(default=False)
    on_work = models.BooleanField(default=False)
    limit_to_work = models.IntegerField(default=0)
    last_id = models.IntegerField(default=0)
    is_bot = models.BooleanField(default=False)
    banks = models.ManyToManyField(to='payment.Bank', blank=True)
    payment_limit_per_minute = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.user.username}'

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def limit_check(self) -> bool:
        Payment = apps.get_model('payment', 'Payment')
        limit = self.payment_limit_per_minute
        threshold = timezone.now() - datetime.timedelta(seconds=60)
        if limit:
            payments_count = Payment.objects.filter(merchant__owner__id=self.id, create_at__gte=threshold).count()
            if payments_count >= limit:
                return False
        return True

class SingletonModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.__class__.objects.exclude(id=self.id).delete()
        super(SingletonModel, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        try:
            return cls.objects.get()
        except cls.DoesNotExist:
            return cls()


class SupportOptions(SingletonModel):
    operators_on_work = models.JSONField(verbose_name='Операторы на смене', default=dict)

    def __str__(self):
        return f'Options({self.operators_on_work})'
