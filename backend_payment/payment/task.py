import datetime
import json

import structlog
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from requests import request

import payment.models as models
from core.global_func import send_message_tg
from users.models import SupportOptions

logger = structlog.get_logger(__name__)
User = get_user_model()

@shared_task()
def send_payment_webhook(url, data: dict, dump_data=True):
    """Отправка вебхука принятия или отклонения заявки payment"""
    try:
        logger.info(f'Отправка payment webhook на {url}: {data}.')
        headers = {"Content-Type": "application/json"}
        if dump_data:
            response = request(url=url, method='POST', json=json.dumps(data), headers=headers, timeout=5)
        else:
            response = request(url=url, method='POST', json=data, headers=headers, timeout=5)
        logger.info(f'status_code {url}: {response.status_code}')
        payment_id = data['id']
        payment = models.Payment.objects.filter(pk=payment_id).first()
        if payment:
            payment.response_status_code = response.status_code
            payment.save()
        logger.debug(
            f'Полный лог {payment_id} {data};'
            f'status_code: {response.status_code};'
            f'reason: {response.reason};'
            f'text: {response.text};'
            f'url: {response.url}'
        )
        return response.status_code
    except Exception as err:
        logger.error(err)


@shared_task()
def send_withdraw_webhook(url, data: dict, dump_data=True):
    try:
        logger.info(f'Отправка withdraw webhook на {url}: {data}')
        headers = {"Content-Type": "application/json"}
        if dump_data:
            response = request(url=url, method='POST', json=json.dumps(data), headers=headers, timeout=10)
        else:
            response = request(url=url, method='POST', json=data, headers=headers, timeout=10)
        logger.info(response.status_code)
        withdraw_id = data['id']
        withdraw = models.Withdraw.objects.get(pk=withdraw_id)
        if withdraw:
            withdraw.response_status_code = response.status_code
            withdraw.save()
        return response.status_code
    except Exception as err:
        logger.error(err)


@shared_task()
def automatic_decline_expired_payment():
    """
    Автоматическое отклонение заявок
    :return:
    """
    PAYMENT_EXPIRED = 11 * 60
    expired_time = timezone.now() - datetime.timedelta(seconds=PAYMENT_EXPIRED)
    logger.debug(f'Удаляем payment ранее {expired_time}')
    expired_payment = models.Payment.objects.filter(create_at__lt=expired_time, status__range=(0, 8))
    logger.debug(f'Найдено для отклонения: {expired_payment}')
    for p in expired_payment:
        p.status = -1
        p.pay_requisite = None
        p.save()
    # expired_payment.update(status=-1, pay_requisite=None)
    # Особождаем реквизиты
    not_free_req = models.Payment.objects.filter(status__in=[-1, 9], pay_requisite__isnull=False)
    # not_free_req.update(pay_requisite=None)
    for p in not_free_req:
        p.pay_requisite = None
        p.save()


@shared_task()
def send_message_tg_task(message: str, chat_ids: list = settings.ADMIN_IDS):
    logger.debug(f'Запуск send_message_tg_task: {message} to {chat_ids}')
    send_message_tg(message, chat_ids)


@shared_task()
def send_payment_to_work_oper(instance_id):
    logger.debug(f'send_payment_to_work_oper: {instance_id}')
    instance = models.Payment.objects.get(pk=instance_id)
    logger.debug(instance)
    operators_on_work: list = SupportOptions.load().operators_on_work
    logger.debug(f'start operators_on_work: {operators_on_work}')
    operators_to_remove = []
    for oper_id in operators_on_work:
        oper: User = User.objects.get(pk=oper_id)
        logger.debug(f'{oper} on_work: {oper.profile.on_work}')
        if oper and not oper.profile.on_work:
            logger.debug(f'Опер {oper} не на смене - удаляем из распределения')
            operators_to_remove.append(oper_id)

    operators_on_work = list(set(operators_on_work) ^ set(operators_to_remove))
    operators_on_work.sort()

    my_username = 'Maniac'
    my = User.objects.get(username=my_username)
    my_pay = models.Payment.objects.filter(work_operator=my.id, status__in=[3, 4, 5, 6, 7, 8]).count()
    my_limit = my.profile.limit_to_work
    if operators_on_work:
        order_num = instance.counter % len(operators_on_work)
        if my.profile.on_work and str(my.id) in operators_on_work and my_pay < my_limit and instance.bank_name() == 'kapital':
            logger.debug('kapital')
            work_operator = str(my.id)
        else:
            if len(operators_on_work) > 1:
                if str(my.id) in operators_on_work:
                    operators_on_work.remove(str(my.id))
            order_num = instance.counter % len(operators_on_work)
            work_operator = operators_on_work[order_num]
        instance.work_operator = work_operator
        instance.status = 4
        instance.save()
        logger.debug(f'on_work: {operators_on_work}. order_num: {order_num}. work_operator: {work_operator}')