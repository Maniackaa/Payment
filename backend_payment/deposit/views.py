import datetime
import logging
import re
from http import HTTPStatus

import pytz
import structlog
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, UpdateView
from rest_framework.decorators import api_view
from rest_framework.request import Request

from backend_payment.settings import TIME_ZONE
from core.global_func import send_message_tg
from deposit.filters import IncomingFilter
from deposit.forms import IncomingForm

from deposit.models import  Incoming, TrashIncoming

from deposit.text_response_func import response_sms1, response_sms2, response_sms3, response_sms4, response_sms5, \
    response_sms6, response_sms7, response_sms8, response_sms9, response_sms10, response_sms11, response_sms12, \
    response_sms13, response_sms14, response_sms15
from payment.models import Payment
from payment.permissions import StaffOnlyPerm

logger = structlog.getLogger(__name__)
TZ = pytz.timezone(TIME_ZONE)

patterns = {
    'sms1': r'^Imtina:(.*)\nKart:(.*)\nTarix:(.*)\nMercant:(.*)\nMebleg:(.*) .+\nBalans:(.*) ',
    'sms2': r'.*Mebleg:\s*(.*?) AZN.*\n*Kart:(.*)\n*Tarix:(.*)\n*Merchant:(.*)\n*Balans:(.*) .*',
    'sms3': r'^.+[medaxil|mexaric] (.+?) AZN (.*)(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d).+Balance: (.+?) AZN.*',
    'sms4': r'^Amount:(.+?) AZN[\n]?.*\nCard:(.*)\nDate:(.*)\nMerchant:(.*)[\n]*Balance:(.*) .*',
    'sms5': r'.*Mebleg:(.+) AZN.*\n.*(\*\*\*.*)\nUnvan: (.*)\n(.*)\nBalans: (.*) AZN',
    'sms6': r'.*Mebleg:(.+) AZN.*\nHesaba medaxil: (.*)\nUnvan: (.*)\n(.*)\nBalans: (.*) AZN',
    'sms7': r'(.+) AZN.*\n(.+)\nBalans (.+) AZN\nKart:(.+)',
    'sms8': r'.*Mebleg: (.+) AZN.*Merchant: (.*)\sBalans: (.*) AZN',
    'sms9': r'(.*)\n(\d\d\d\d\*\*\d\d\d\d)\nMedaxil\n(.*) AZN\n(\d\d:\d\d \d\d\.\d\d.\d\d)\nBALANCE\n(.*)AZN',
    'sms10': r'(.*)\n(\d\d\d\d\*\*\d\d\d\d)\nMedaxil (.*) AZN\nBALANCE\n(.*) AZN\n(\d\d:\d\d \d\d\.\d\d.\d\d)',
    'sms11': r'Odenis\n(.*) AZN \n(.*\n.*)\n(\d\d\d\d\*\*\d\d\d\d).*\n(\d\d:\d\d \d\d\.\d\d.\d\d)\nBALANCE\n(.*) AZN',
    'sms12': r'(\d\d\.\d\d\.\d\d \d\d:\d\d)(.*)AZ Card: (.*) amount:(.*)AZN.*Balance:(.*)AZN',
    'sms13': r'[Odenis|Legv Edilme]: (.*) AZN\n(.*)\n(\d\d\d\d\*\*\d\d\d\d).*\n(\d\d:\d\d \d\d\.\d\d.\d\d)\nBALANCE\n(.*)',
    'sms14': r'^.+[medaxil|mexaric]: (.+?) AZN\n(.*)\n(\d\d:\d\d \d\d\.\d\d\.\d\d)\nBALANCE\n(.+?) AZN.*',
    'sms15': r'Medaxil C2C: (.+?) AZN\n(.*)\n(.*)\n(\d\d:\d\d \d\d\.\d\d\.\d\d)\nBALANCE\n(.+?) AZN.*'
}

response_func = {
    'sms1': response_sms1,
    'sms2': response_sms2,
    'sms3': response_sms3,
    'sms4': response_sms4,
    'sms5': response_sms5,
    'sms6': response_sms6,
    'sms7': response_sms7,
    'sms8': response_sms8,
    'sms9': response_sms9,
    'sms10': response_sms10,
    'sms11': response_sms11,
    'sms12': response_sms12,
    'sms13': response_sms13,
    'sms14': response_sms14,
    'sms15': response_sms15,
}


def save_incoming(responsed_pay) -> str:
    """
    Сохранение поступления Incoming в базу
    :param responsed_pay:
    :return: 'duplicate' / 'created' / None
    """
    save_status = None
    try:
        logger.info(f'Сохраняем в базу: {responsed_pay}')
        if responsed_pay.get('sms_type') in ['sms8', 'sms7']:
            # Шаблоны без времени
            logger.debug('Шаблоны без времени')
            threshold = datetime.datetime.now(tz=TZ) - datetime.timedelta(hours=12)
            is_duplicate = Incoming.objects.filter(
                sender=responsed_pay.get('sender'),
                pay=responsed_pay.get('pay'),
                balance=responsed_pay.get('balance'),
                register_date__gte=threshold
            ).exists()
        else:
            logger.debug('Шаблоны со временем')
            is_duplicate = Incoming.objects.filter(
                response_date=responsed_pay.get('response_date'),
                sender=responsed_pay.get('sender'),
                pay=responsed_pay.get('pay'),
                balance=responsed_pay.get('balance')
            ).exists()
        logger.debug(f'is_duplicate: {is_duplicate}')
        if is_duplicate:
            # logger.info('Дубликат sms:\n\n{text}')
            # msg = f'Дубликат sms:\n\n{text}'
            # send_message_tg(message=msg, chat_ids=settings.ALARM_IDS)
            save_status = 'duplicate'
        else:
            logger.debug(f'Создаем {responsed_pay}')
            created = Incoming.objects.create(**responsed_pay)
            logger.info(f'Создан: {created}')
            save_status = 'created'
        return save_status
    except Exception as err:
        logger.error(err)


def find_text_sms_type(text):
    text_sms_type = None
    for sms_type, pattern in patterns.items():
        search_result = re.findall(pattern, text)
        if search_result:
            logger.debug(f'Найдено: {sms_type}: {search_result}')
            text_sms_type = sms_type
            break
    return text_sms_type


def analyse_sms_text_and_save(text, params=None, *args, **kwargs):
    """
    Распознает текст и преобразует в dict responsed_pay, затем сохраняет в базу
    :param text:
    :param params:
    :param args:
    :param kwargs:
    :return: {'save_result': 'duplicate' / 'created' / 'trash', 'response_errors': response_errors}
    """
    if params is None:
        params = {}
    response_errors = []
    fields = ['response_date', 'recipient', 'sender', 'pay', 'balance',
              'transaction',
              'type']

    text_sms_type = find_text_sms_type(text)
    logger.debug(f'text_sms_type: {text_sms_type}')
    if text_sms_type:
        search_result = re.findall(patterns[text_sms_type], text)
        responsed_pay: dict = response_func[text_sms_type](fields, search_result[0])
        logger.debug(f'responsed_pay: {responsed_pay}')
        response_errors = responsed_pay.pop('errors')
        # Добавим получателя если его нет
        if not responsed_pay.get('recipient'):
            responsed_pay['recipient'] = params.get('imei')
        responsed_pay['worker'] = params.get('worker') or params.get('imei')
        # Обработка валидной смс
        logger.debug(f'responsed_pay added: {responsed_pay}')
        save_result = save_incoming(responsed_pay)

    else:
        logger.info(f'Неизвестный шаблон\n{text}')
        new_trash = TrashIncoming.objects.create(text=text, worker=params.get('worker') or params.get('imei'))
        logger.info(f'Добавлено в мусор: {new_trash}')
        save_result = 'trash'
    if not save_result:
        response_errors.append(f'Смс не сохранилась в базу!')
    return {'save_result': save_result, 'response_errors': response_errors}


@api_view(['POST'])
def create_copy_screen(request: Request):

    data = request.data
    logger.debug(data)
    Incoming.objects.get_or_create(**data)
    return HttpResponse(status=HTTPStatus.OK, content='ok')


@api_view(['POST'])
def sms(request: Request):
    """
    Прием sms
    {'id': ['b1899338-2314-400c-a4ff-a9ef3d890c79'], 'from': ['icard'], 'to': [''], 'message': ['Mebleg:+50.00 AZN '], 'res_sn': ['111'], 'imsi': ['400055555555555'], 'imei': ['123456789000000'], 'com': ['COM39'], 'simno': [''], 'sendstat': ['0']}>, host: asu-payme.com, user_agent: None, path: /sms/, forwarded: 91.201.000.000
    """
    errors = []
    text = ''
    try:
        host = request.META["HTTP_HOST"]  # получаем адрес сервера
        user_agent = request.META.get("HTTP_USER_AGENT")  # получаем данные бразера
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        path = request.path
        logger.info(f'request.data: {request.data},'
                     f' host: {host},'
                     f' user_agent: {user_agent},'
                     f' path: {path},'
                     f' forwarded: {forwarded}')

        post = request.POST
        text = post.get('message')
        sms_id = post.get('id')
        imei = post.get('imei')
        params = {'sms_id': sms_id, 'imei': imei}
        logger.info(f'Получена смс:\n{text}\nparams: {params}')
        result = analyse_sms_text_and_save(text, params)
        logger.debug(f'analyse result: {result}')
        save_result = result.get('save_result')
        logger.debug(f'save_result : {save_result}')
        errors = result.get('errors')

        if save_result == 'created':
            response = HttpResponse(status=HTTPStatus.CREATED, content=sms_id)
        elif save_result == 'duplicate':
            response = HttpResponse(status=HTTPStatus.OK, content=sms_id)
        else:
            # Мусор
            new_trash = TrashIncoming.objects.create(text=text, worker=params.get('worker') or params.get('imei'))
            send_message_tg(message=f'Добавлено в мусор:\n{text}', chat_ids=settings.ALARM_IDS)
            logger.info(f'Добавлено в мусор так как не удалось сохранить: {new_trash}')
            response = HttpResponse(status=HTTPStatus.OK, content=sms_id)
        return response

    except Exception as err:
        msg = f'Неизвестная ошибка при распознавании сообщения: {err}'
        logger.info(msg)
        logger.error(f'{msg}', exc_info=True)
        send_message_tg(message=msg, chat_ids=settings.ALARM_IDS)
        return HttpResponse(status=HTTPStatus.BAD_REQUEST)

    finally:
        if errors:
            msg = f'Ошибки при распознавании Payment sms:\n{errors}\n\n{text}'
            send_message_tg(message=msg, chat_ids=settings.ALARM_IDS)


# @api_view(['POST'])
# def sms_forwarder(request: Request):
#     """
#     Прием sms_forwarder
#     """
#     errors = []
#     text = ''
#     try:
#         host = request.META["HTTP_HOST"]  # получаем адрес сервера
#         user_agent = request.META.get("HTTP_USER_AGENT")  # получаем данные бразера
#         forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
#         path = request.path
#         logger.info(f'request.data: {request.data},'
#                      f' host: {host},'
#                      f' user_agent: {user_agent},'
#                      f' path: {path},'
#                      f' forwarded: {forwarded}')
#         post = request.POST
#         text = post.get('message')
#         sms_id = post.get('id')
#         imei = post.get('imei')
#         result = analyse_sms_text_and_save(text, imei, sms_id)
#         response = result.get('response')
#         errors = result.get('errors')
#         return response
#
#     except Exception as err:
#         logger.info(f'Неизвестная ошибка при распознавании сообщения: {err}')
#         logger.error(f'Неизвестная ошибка при распознавании сообщения: {err}\n', exc_info=True)
#         raise err
#     finally:
#         if errors:
#             msg = f'Ошибки при распознавании sms:\n{errors}\n\n{text}'
#             send_message_tg(message=msg, chat_ids=settings.ALARM_IDS)


class IncomingListView(StaffOnlyPerm, ListView, ):
    """Спиcок платежей"""
    template_name = 'deposit/incomings_list.html'
    model = Incoming
    paginate_by = settings.PAGINATE
    filter = IncomingFilter

    def get_queryset(self):
        return IncomingFilter(self.request.GET, queryset=Incoming.objects).qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # form = PaymentListConfirmForm()
        # context['form'] = form
        filter = IncomingFilter(self.request.GET, queryset=self.get_queryset())
        context['filter'] = filter
        return context

    def post(self, request):
        print('post')
        print(request.POST)
        for key, val in request.POST.dict().items():
            if 'incoming_id:' in key:
                incoming_id = int(key.split('incoming_id:')[1])
                input_payment_id = val
        print(incoming_id, input_payment_id)
        incoming = Incoming.objects.get(pk=incoming_id)
        payment = Payment.objects.filter(pk=input_payment_id).first()
        if payment:
            incoming.confirmed_payment = payment
            incoming.save()

        return redirect(reverse('deposit:incomings'))


class IncomingEdit(StaffOnlyPerm, UpdateView, ):
    # Ручная корректировка платежа
    model = Incoming
    form_class = IncomingForm
    success_url = reverse_lazy('deposit:incomings')
    template_name = 'deposit/incoming_edit.html'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.user.has_perm('deposit.can_hand_edit'):
            self.object = self.get_object()
            return super().post(request, *args, **kwargs)
        return HttpResponseForbidden('У вас нет прав делать ручную корректировку')

    def get_context_data(self, **kwargs):
        context = super(IncomingEdit, self).get_context_data(**kwargs)
        # history = self.object.history.order_by('-id').all()
        # context['history'] = history
        return context

    def form_valid(self, form):
        if form.is_valid():
            old_incoming = Incoming.objects.get(pk=self.object.id)
            incoming: Incoming = self.object
            # # Сохраняем историю
            # IncomingChange().save_incoming_history(old_incoming, incoming, self.request.user)
            return super(IncomingEdit, self).form_valid(form)


class IncomingTrashList(StaffOnlyPerm, ListView):
    # Мусор
    model = Incoming
    template_name = 'deposit/trash_list.html'
    paginate_by = settings.PAGINATE

    def get_queryset(self, *args, **kwargs):
        # if not self.request.user.is_staff:
        #     raise PermissionDenied('Недостаточно прав')
        trash_list = TrashIncoming.objects.order_by('-id').all()
        return trash_list