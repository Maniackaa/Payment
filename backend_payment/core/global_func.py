import datetime
import hashlib
import logging

import pytz
import requests
from django.http import HttpResponse
from openpyxl.workbook import Workbook

from backend_payment import settings
from backend_payment.settings import TIME_ZONE
from deposit.text_response_func import tz

TZ = pytz.timezone(TIME_ZONE)
logger = logging.getLogger(__name__)


def send_message_tg(message: str, chat_ids: list = settings.ADMIN_IDS):
    """Отправка сообщений через чат-бот телеграмма"""
    for chat_id in chat_ids:
        try:
            logger.debug(f'Отправляем сообщение для {chat_id}')
            url = (f'https://api.telegram.org/'
                   f'bot{settings.BOT_TOKEN}/'
                   f'sendMessage?'
                   f'chat_id={chat_id}&'
                   f'text={message}')
            response = requests.get(url)
            if response.status_code == 200:
                logger.debug(f'Сообщение для {chat_id} отправлено')
            else:
                logger.debug(f'Ошибка при отправке сообщения для {chat_id}. Код {response.status_code}')
        except Exception as err:
            logger.error(f'Ошибка при отправки сообщений: {err}')


def hash_gen(text, salt):
    """
    merchant_id + amount + salt
    :param text:
    :param salt:
    :return:
    """
    formatted_string = f'{text}' + f'{salt}'
    m = hashlib.sha256(formatted_string.encode('UTF-8'))
    return m.hexdigest()


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def export_payments_func(products):
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="payments.xlsx"'
    wb = Workbook()
    ws = wb.active
    ws.title = "Payments"
    headers = ["id", "order_id", "pay_type", "create_at", 'merchant', "amount", "confirmed_amount", "comission",
               "status",
               "user_login", "owner_name", "bank", "mask", "referrer", "confirmed_time", "response_status_code", "comment"]
    ws.append(headers)
    for payment in products:
        row = []
        for field in headers:
            value = getattr(payment, field)
            if not value:
                value = ''
            if isinstance(value, datetime.datetime):
                value = value.astimezone(tz=tz)
            if field in ('id', 'order_id', 'merchant', 'create_at', 'confirmed_time', 'bank'):
                row.append(str(value))
            else:
                row.append(value)
        ws.append(row)
    wb.save(response)
    return response