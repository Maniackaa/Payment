from django.conf import settings
from django.contrib import admin
from django.core.mail import send_mail
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin, Group
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from users.managers import UserManager


class WhiteListMerchant(models.Model):
    name = models.CharField('Наименование', unique=True)
    email = models.EmailField(unique=True)


class User(AbstractBaseUser, PermissionsMixin):
    username_validator = UnicodeUsernameValidator()

    USER = "user"
    STAFF = "staff"
    ADMIN = "admin"
    MODERATOR = "editor"
    MERCHANT = "merchant"
    ROLES = (
        (USER, "Пользователь"),
        (ADMIN, "Администратор"),
        (STAFF, "Оператор"),
        (MODERATOR, "Корректировщик"),
        (MERCHANT, "Мерчант"),
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

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.username

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
    print(WhiteListMerchant.objects.all())
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

    @staticmethod
    def all_message_count():
        return Message.objects.exclude(type='macros').count()

    def read_message_count(self):
        res = self.user.messages_read.all().exclude(message__type='macros').count()
        return res

    def __str__(self):
        return f'{self.user.username}'

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"
