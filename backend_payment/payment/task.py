import json

import structlog
from celery import shared_task
from requests import request

import payment.models as models
logger = structlog.get_logger(__name__)


@shared_task()
def send_payment_webhook(url, data: dict):
    try:
        logger.info(f'Отправка webhook на {url}: {json.dumps(data)}')
        headers = {"Content-Type": "application/json"}
        response = request(url=url, method='POST', json=json.dumps(data), headers=headers, timeout=5)
        logger.info(response.status_code)
        payment_id = data['id']
        payment = models.Payment.objects.get(pk=payment_id)
        if payment:
            payment.response_status_code = response.status_code
            payment.save()
        return response.status_code
    except Exception as err:
        logger.error(err)


@shared_task()
def send_withdraw_webhook(url, data: dict):
    try:
        logger.info(f'Отправка webhook на {url}: {json.dumps(data)}')
        headers = {"Content-Type": "application/json"}
        response = request(url=url, method='POST', json=json.dumps(data), headers=headers, timeout=5)
        logger.info(response.status_code)
        withdraw_id = data['id']
        withdraw = models.Withdraw.objects.get(pk=withdraw_id)
        if withdraw:
            withdraw.response_status_code = response.status_code
            withdraw.save()
        return response.status_code
    except Exception as err:
        logger.error(err)