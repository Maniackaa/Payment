import asyncio
import datetime
import json
import time

import structlog
from asgiref.sync import async_to_sync
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from requests import request

import payment.models as models
from core.global_func import send_message_tg
from users.models import SupportOptions

logger = structlog.get_logger('payment')
User = get_user_model()


@shared_task(priority=3)
def send_payment_webhook(url, data: dict, dump_data=True) -> HttpResponse:
    """Отправка вебхука принятия или отклонения заявки payment"""
    log = logger.bind(payment_id=data['id'])
    try:
        start = time.perf_counter()
        logger.info(f'Отправка payment webhook на {url}: {data}.')
        headers = {"Content-Type": "application/json"}
        if dump_data:
            response = request(url=url, method='POST', json=json.dumps(data), headers=headers, timeout=10)
        else:
            response = request(url=url, method='POST', json=data, headers=headers, timeout=10)
        log.info(f'status_code {url}: {response.status_code}')
        payment_id = data['id']
        payment = models.Payment.objects.filter(pk=payment_id).first()
        if payment:
            payment.response_status_code = response.status_code
            payment.save()
        log.debug(
            f'Полный лог {payment_id} {url} {data}; '
            f'status_code: {response.status_code}; '
            f'reason: {response.reason}; '
            f'text: {response.text}; '
            f'url: {response.url}; '
            f'time: {round(time.perf_counter() - start, 2)}; '
        )
        content = (
            f'status_code: {response.status_code}; <br>'
            f'reason: {response.reason}; <br>'
            f'text: {response.text}; <br>'
            f'url: {response.url}; <br>'
            f'time: {round(time.perf_counter() - start, 2)}; '
        )
        return HttpResponse(status=200, content_type='text/plain', content=content, charset='utf-8')
    except Exception as err:
        logger.error(err)
        return str(err)


@shared_task(priority=3)
def send_withdraw_webhook(url, data: dict, dump_data=True) -> HttpResponse:
    log = logger.bind(payment_id=data['id'])
    try:
        start = time.perf_counter()

        logger.info(f'Отправка withdraw webhook на {url}: {data}')
        headers = {"Content-Type": "application/json"}
        if dump_data:
            response = request(url=url, method='POST', json=json.dumps(data), headers=headers, timeout=10)
        else:
            response = request(url=url, method='POST', json=data, headers=headers, timeout=10)
        log.info(response.status_code)
        withdraw_id = data['id']
        withdraw = models.Withdraw.objects.filter(pk=withdraw_id).first()
        if withdraw:
            withdraw.response_status_code = response.status_code
            withdraw.save()

        content = (
            f'status_code: {response.status_code}; <br>'
            f'reason: {response.reason}; <br>'
            f'text: {response.text}; <br>'
            f'url: {response.url}; <br>'
            f'time: {round(time.perf_counter() - start, 2)}; '
        )
        log.debug(f'time withdraw webhook: {round(time.perf_counter() - start, 2)}; ')
        return HttpResponse(status=200, content_type='text/plain', content=content, charset='utf-8')
    except Exception as err:
        log.error(err)


@shared_task(priority=2)
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


@shared_task(priority=3)
def send_message_tg_task(message: str, chat_ids: list = settings.ADMIN_IDS):
    logger.debug(f'Запуск send_message_tg_task: {message} to {chat_ids}')
    send_message_tg(message, chat_ids)


@shared_task(priority=1)
def send_payment_to_work_oper(instance_id):
    # Задача распределение платежа операм на смене
    log = logger.bind(payment_id=instance_id)
    try:
        log.debug(f'send_payment_to_work_oper: {instance_id}')
        instance = models.Payment.objects.get(pk=instance_id)
        log.debug(instance)

        # Свободные боты на смене
        bots = User.objects.filter(profile__is_bot=True, profile__on_work=True)
        free_bots = bots.filter(profile__bot_max_amount=0) | bots.filter(profile__bot_max_amount__gt=0,
                                                                         profile__bot_max_amount__gte=instance.amount)
        log.debug(f'free_bots: {free_bots}')

        bank_bots = free_bots.filter(
            profile__is_bot=True,
            profile__on_work=True,
            profile__banks__in=[instance.bank],
        )
        log.debug(f'bank_bots: {bank_bots}')
        for bot in bank_bots:
            bot_limit = bot.profile.limit_to_work
            bot_payments = bot.oper_payments.exclude(status__in=[-1, 9]).count()
            # Если есть резерв - назначаем боту
            if bot_limit > bot_payments:
                instance.work_operator = bot
                instance.status = 4
                instance.save()
                log.debug(f' {instance} work_operator bot: {bot}')
                return

        operators_on_work: list = SupportOptions.load().operators_on_work
        log.debug(f'start operators_on_work: {operators_on_work}')
        operators_to_remove = []
        for oper_id in operators_on_work:
            oper: User = User.objects.get(pk=oper_id)
            log.debug(f'{oper} on_work: {oper.profile.on_work}')
            if oper and not oper.profile.on_work or oper.profile.is_bot:
                log.debug(f'Опер {oper} не на смене или бот - удаляем из распределения')
                operators_to_remove.append(oper_id)

        operators_on_work = list(set(operators_on_work) ^ set(operators_to_remove))
        operators_on_work.sort()
        log.debug(f'operators_on_work: {operators_on_work}')

        if operators_on_work:
            order_num = instance.counter % len(operators_on_work)
            work_operator = User.objects.get(pk=operators_on_work[order_num])
            instance.work_operator = work_operator
            instance.status = 4
            instance.save()
            log.debug(f'on_work: {operators_on_work}. order_num: {order_num}. work_operator: {work_operator}')
    except Exception as err:
        log.error(err)
        raise err


def test_job(value):
    start = time.perf_counter()
    logger.info(f'Началось выполнение {value}')
    time.sleep(5)
    delta = round(time.perf_counter() - start, 2)
    logger.info(f'Закончилось выполнение {value} за {delta} с')


@shared_task()
def low_priority_task():
    test_job(str(timezone.now()))


@shared_task()
def high_priority_task():
    logger.info(f'!!!!!!!!!!!!!!!!!ШТЫКОВАЯ ЗАДАЧА!!!!!!!!!!!!!!!!')