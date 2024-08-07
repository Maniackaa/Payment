# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthtokenToken(models.Model):
    key = models.CharField(primary_key=True, max_length=40)
    created = models.DateTimeField()
    user = models.OneToOneField('UsersUser', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'authtoken_token'


class DepositIncoming(models.Model):
    id = models.BigAutoField(primary_key=True)
    register_date = models.DateTimeField()
    response_date = models.DateTimeField(blank=True, null=True)
    recipient = models.CharField(max_length=50, blank=True, null=True)
    sender = models.CharField(max_length=50, blank=True, null=True)
    pay = models.FloatField()
    balance = models.FloatField(blank=True, null=True)
    type = models.CharField(max_length=20)
    worker = models.CharField(max_length=50, blank=True, null=True)
    confirmed_time = models.DateTimeField(blank=True, null=True)
    change_time = models.DateTimeField(blank=True, null=True)
    comment = models.CharField(max_length=500, blank=True, null=True)
    transaction = models.BigIntegerField(unique=True, blank=True, null=True)
    confirmed_payment = models.OneToOneField('PaymentPayment', models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'deposit_incoming'


class DepositSetting(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(unique=True)
    value = models.CharField()

    class Meta:
        managed = False
        db_table = 'deposit_setting'


class DepositTrashincoming(models.Model):
    id = models.BigAutoField(primary_key=True)
    register_date = models.DateTimeField()
    text = models.CharField(max_length=1000)
    worker = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'deposit_trashincoming'


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.SmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey('UsersUser', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoCeleryBeatClockedschedule(models.Model):
    clocked_time = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_celery_beat_clockedschedule'


class DjangoCeleryBeatCrontabschedule(models.Model):
    minute = models.CharField(max_length=240)
    hour = models.CharField(max_length=96)
    day_of_week = models.CharField(max_length=64)
    day_of_month = models.CharField(max_length=124)
    month_of_year = models.CharField(max_length=64)
    timezone = models.CharField(max_length=63)

    class Meta:
        managed = False
        db_table = 'django_celery_beat_crontabschedule'


class DjangoCeleryBeatIntervalschedule(models.Model):
    every = models.IntegerField()
    period = models.CharField(max_length=24)

    class Meta:
        managed = False
        db_table = 'django_celery_beat_intervalschedule'


class DjangoCeleryBeatPeriodictask(models.Model):
    name = models.CharField(unique=True, max_length=200)
    task = models.CharField(max_length=200)
    args = models.TextField()
    kwargs = models.TextField()
    queue = models.CharField(max_length=200, blank=True, null=True)
    exchange = models.CharField(max_length=200, blank=True, null=True)
    routing_key = models.CharField(max_length=200, blank=True, null=True)
    expires = models.DateTimeField(blank=True, null=True)
    enabled = models.BooleanField()
    last_run_at = models.DateTimeField(blank=True, null=True)
    total_run_count = models.IntegerField()
    date_changed = models.DateTimeField()
    description = models.TextField()
    crontab = models.ForeignKey(DjangoCeleryBeatCrontabschedule, models.DO_NOTHING, blank=True, null=True)
    interval = models.ForeignKey(DjangoCeleryBeatIntervalschedule, models.DO_NOTHING, blank=True, null=True)
    solar = models.ForeignKey('DjangoCeleryBeatSolarschedule', models.DO_NOTHING, blank=True, null=True)
    one_off = models.BooleanField()
    start_time = models.DateTimeField(blank=True, null=True)
    priority = models.IntegerField(blank=True, null=True)
    headers = models.TextField()
    clocked = models.ForeignKey(DjangoCeleryBeatClockedschedule, models.DO_NOTHING, blank=True, null=True)
    expire_seconds = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'django_celery_beat_periodictask'


class DjangoCeleryBeatPeriodictasks(models.Model):
    ident = models.SmallIntegerField(primary_key=True)
    last_update = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_celery_beat_periodictasks'


class DjangoCeleryBeatSolarschedule(models.Model):
    event = models.CharField(max_length=24)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        managed = False
        db_table = 'django_celery_beat_solarschedule'
        unique_together = (('event', 'latitude', 'longitude'),)


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class PaymentBalancechange(models.Model):
    id = models.BigAutoField(primary_key=True)
    create_at = models.DateTimeField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    comment = models.CharField(blank=True, null=True)
    user = models.ForeignKey('UsersUser', models.DO_NOTHING)
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payment_balancechange'


class PaymentBank(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(unique=True)
    bins = models.TextField()  # This field type is a guess.
    instruction = models.CharField(blank=True, null=True)
    image = models.CharField(max_length=100, blank=True, null=True)
    script = models.ForeignKey('PaymentPhonescript', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'payment_bank'


class PaymentCreditcard(models.Model):
    id = models.BigAutoField(primary_key=True)
    card_number = models.CharField(max_length=19)
    owner_name = models.CharField(max_length=100, blank=True, null=True)
    cvv = models.CharField(max_length=4, blank=True, null=True)
    card_type = models.CharField(max_length=100)
    card_bank = models.CharField(max_length=50)
    expired_month = models.IntegerField()
    expired_year = models.IntegerField()
    status = models.CharField()

    class Meta:
        managed = False
        db_table = 'payment_creditcard'


class PaymentMerchant(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    host = models.CharField(max_length=200)
    secret = models.CharField(max_length=1000)
    pay_success_endpoint = models.CharField(max_length=200, blank=True, null=True)
    owner = models.ForeignKey('UsersUser', models.DO_NOTHING)
    is_new = models.BooleanField()
    host_withdraw = models.CharField(max_length=200)

    class Meta:
        managed = False
        db_table = 'payment_merchant'


class PaymentPayment(models.Model):
    id = models.UUIDField(primary_key=True)
    order_id = models.CharField(max_length=36)
    amount = models.IntegerField(blank=True, null=True)
    user_login = models.CharField(max_length=36, blank=True, null=True)
    owner_name = models.CharField(max_length=100, blank=True, null=True)
    pay_type = models.CharField()
    screenshot = models.CharField(max_length=100, blank=True, null=True)
    create_at = models.DateTimeField()
    status = models.IntegerField()
    change_time = models.DateTimeField()
    cc_data_input_time = models.DateTimeField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    referrer = models.CharField(max_length=200, blank=True, null=True)
    card_data = models.JSONField()
    phone_script_data = models.JSONField()
    confirmed_amount = models.IntegerField(blank=True, null=True)
    confirmed_time = models.DateTimeField(blank=True, null=True)
    comment = models.CharField(max_length=1000, blank=True, null=True)
    response_status_code = models.IntegerField(blank=True, null=True)
    source = models.CharField(max_length=5, blank=True, null=True)
    confirmed_user = models.ForeignKey('UsersUser', models.DO_NOTHING, blank=True, null=True)
    merchant = models.ForeignKey(PaymentMerchant, models.DO_NOTHING)
    pay_requisite = models.ForeignKey('PaymentPayrequisite', models.DO_NOTHING, blank=True, null=True)
    confirmed_incoming = models.OneToOneField(DepositIncoming, models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payment_payment'


class PaymentPaymentlog(models.Model):
    id = models.BigAutoField(primary_key=True)
    create_at = models.DateTimeField()
    changes = models.JSONField()
    payment = models.ForeignKey(PaymentPayment, models.DO_NOTHING)
    user = models.ForeignKey('UsersUser', models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payment_paymentlog'


class PaymentPayrequisite(models.Model):
    id = models.BigAutoField(primary_key=True)
    pay_type = models.CharField()
    is_active = models.BooleanField()
    info = models.CharField(blank=True, null=True)
    min_amount = models.IntegerField()
    max_amount = models.IntegerField()
    card = models.OneToOneField(PaymentCreditcard, models.DO_NOTHING, blank=True, null=True)
    method_info = models.CharField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payment_payrequisite'


class PaymentPhonescript(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(unique=True)
    step_1 = models.BooleanField()
    step_2_required = models.BooleanField()
    step_2_x = models.IntegerField(blank=True, null=True)
    step_2_y = models.IntegerField(blank=True, null=True)
    step_3_x = models.IntegerField(blank=True, null=True)
    step_3_y = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payment_phonescript'


class PaymentWithdraw(models.Model):
    id = models.UUIDField(primary_key=True)
    amount = models.IntegerField()
    create_at = models.DateTimeField()
    status = models.IntegerField()
    change_time = models.DateTimeField()
    card_data = models.JSONField()
    payload = models.JSONField(blank=True, null=True)
    comment = models.CharField(max_length=1000, blank=True, null=True)
    response_status_code = models.IntegerField(blank=True, null=True)
    confirmed_user = models.ForeignKey('UsersUser', models.DO_NOTHING, blank=True, null=True)
    merchant = models.ForeignKey(PaymentMerchant, models.DO_NOTHING)
    withdraw_id = models.CharField(max_length=36)
    confirmed_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payment_withdraw'


class UsersProfile(models.Model):
    id = models.BigAutoField(primary_key=True)
    first_name = models.CharField(max_length=30, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    my_filter = models.JSONField()
    my_filter2 = models.JSONField()
    my_filter3 = models.JSONField()
    view_bad_warning = models.BooleanField()
    user = models.OneToOneField('UsersUser', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'users_profile'


class UsersUser(models.Model):
    id = models.BigAutoField(primary_key=True)
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    username = models.CharField(unique=True, max_length=150)
    email = models.CharField(max_length=254)
    role = models.CharField(max_length=20)
    balance = models.DecimalField(max_digits=18, decimal_places=2)
    tax = models.FloatField()
    withdraw_tax = models.FloatField()
    is_superuser = models.BooleanField()
    is_staff = models.BooleanField()
    is_active = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'users_user'


class UsersUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(UsersUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'users_user_groups'
        unique_together = (('user', 'group'),)


class UsersUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(UsersUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'users_user_user_permissions'
        unique_together = (('user', 'permission'),)


class UsersWhitelistmerchant(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(unique=True)
    email = models.CharField(unique=True, max_length=254)

    class Meta:
        managed = False
        db_table = 'users_whitelistmerchant'
