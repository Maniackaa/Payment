import datetime
import json

import django_filters
import structlog
from django.http import JsonResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse, extend_schema_view, \
    extend_schema_serializer, extend_schema_field, inline_serializer

from rest_framework import viewsets, status, generics, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action, api_view
from rest_framework.filters import SearchFilter
from rest_framework.generics import GenericAPIView, get_object_or_404, CreateAPIView, UpdateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer

from rest_framework.response import Response
from rest_framework import mixins
from rest_framework.views import APIView

from rest_framework_simplejwt.authentication import JWTAuthentication

from api.filters import BalanceChangeFilter, PaymentsArchiveFilter, WithdrawFilter
from api.permissions import PaymentOwnerOrStaff, IsStaff, IsStaffOrReadOnly
from api.serializers import PaymentCreateSerializer, PaymentInputCardSerializer, \
    PaymentInputSmsCodeSerializer, PaymentTypesSerializer, WithdrawCreateSerializer, \
    WithdrawSerializer, PaymentGuestSerializer, BalanceSerializer, PaymentInputPhoneSerializer, PaymentFullSerializer, \
    PaymentArchiveSerializer
from core.global_func import hash_gen, get_client_ip, export_payments_func
from payment.models import Payment, PayRequisite, Withdraw, BalanceChange
from payment.views import get_phone_script, get_bank_from_bin


logger = structlog.get_logger(__name__)


class ResponseCreate(serializers.Serializer):
    status = serializers.CharField()
    id = serializers.CharField()


class BadResponse(serializers.Serializer):
    errors = serializers.DictField()


class ResponseInputCard(serializers.Serializer):
    sms_required = serializers.BooleanField()
    instruction = serializers.CharField()
    bank_icon = serializers.URLField()
    signature = serializers.CharField(help_text='hash("sha256", $card_number+$secret_key)')


class ResponseInputSms(serializers.Serializer):
    status = serializers.CharField()


@extend_schema(tags=['Payment check'], summary='Информация о доступных типах оплаты',
               responses={
                   status.HTTP_200_OK: OpenApiResponse(
                       description='Created',
                       response=PaymentTypesSerializer,
                       examples=[
                           OpenApiExample(
                               "Good example",
                               value={"id": "4caed007-2d31-489c-9f3d-a2af6ccf07e4"},
                               status_codes=[201],
                               response_only=False,
                           ),
                       ]),

                   status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                       response=BadResponse,
                       description='Some errors',
                       examples=[
                           OpenApiExample(
                               "Bad response",
                               value={
    "detail": "Given token not valid for any token type",
    "code": "token_not_valid",
    "messages": [
        {
            "token_class": "AccessToken",
            "token_type": "access",
            "message": "Token is invalid or expired"
        }
    ]
},
                               status_codes=[401],
                               response_only=False,
                           ),
                       ]),
               },)
class PaymentTypesView(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentTypesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        active_pay_types = PayRequisite.objects.values('pay_type').distinct().all()
        result = []
        for pay_type in active_pay_types:
            name = pay_type['pay_type']
            result.append(PayRequisite.objects.filter(pay_type=name).first())
        return result


# class LargeResultsSetPagination(PageNumberPagination):
#     page_size = 100
#     page_size_query_param = 'page_size'
#     max_page_size = 200



@extend_schema(tags=['Payment check'], summary='Просмотр архива',
               description=f'/api/v1/payments_archive/?limit=1000&create_at_gte=2024-05-31T00&create_at_lt=2024-06-01&status=9&pay_type=card_2&search=ab'
               )
class PaymentsArchive(generics.ListAPIView):
    serializer_class = PaymentArchiveSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PaymentOwnerOrStaff]
    # pagination_class = LargeResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = PaymentsArchiveFilter
    search_fields = ['id', 'order_id']

    def get_queryset(self):
        # return Payment.objects.all()
        threshold = timezone.now() - datetime.timedelta(days=365)
        return Payment.objects.filter(merchant__owner=self.request.user, create_at__gte=threshold).all()


class PaymentViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentCreateSerializer
    queryset = Payment.objects.all()
    authentication_classes = [JWTAuthentication]
    permission_classes = [PaymentOwnerOrStaff]

    # def get_serializer_class(self):
    #     pay_type = self.request.data.get('pay_type')
    #     if pay_type == 'card_2':
    #         return PaymentCreateSerializer
    #     if pay_type == 'card-to-card':
    #         return PaymentToCardCreateSerializer
    #     raise serializers.ValidationError({'error': f'Type {pay_type} is not present'})

    @extend_schema(tags=['Payment check'], summary='Просмотр данных о платеже',
                   request=[
                       OpenApiExample(
                           "Bad response",
                           value={
                               "amount": ["Ensure this value is greater than or equal to 1."]},
                           status_codes=[400],
                           response_only=False,
                       ),
                   ])
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance=instance)
        # return Response(data={'id': instance.id,
        #                       'oreder_id': instance.order_id,
        #                       'status': instance.status,
        #                       'amount': instance.amount,
        #                       'confirmed_amount': instance.confirmed_amount,
        #                       'mask': instance.mask,
        #                       }, status=status.HTTP_200_OK)
        return Response(serializer.data)

    @extend_schema(tags=['API Payment process'], request=PaymentCreateSerializer, summary="Создание платежа",
                   description="""<p><strong><span style="text-decoration: underline;">Порядок очередности передачи данных:</span></strong></p>
<p><strong>1. Создание платежа:</strong> <span class="opblock-summary-path" data-path="/api/v1/payment/"><a class="nostyle" href="https://asu-payme.com/api/v1/docs/#/API%20Payment%20process/payment_create">/api<wbr />/v1<wbr />/payment<wbr />/</a></span></p>
<p><span class="opblock-summary-path" data-path="/api/v1/payment/">status = 0</span></p>
<p><span class="opblock-summary-path" data-path="/api/v1/payment/"><strong>2а. Отправка данных карты</strong> (метод card_2): <a class="nostyle" href="https://asu-payme.com/api/v1/docs/#/API%20Payment%20process/payment_send_card_data_update">/api<wbr />/v1<wbr />/payment<wbr />/{id}<wbr />/send_card_data<wbr />/</a></span></p>
<p><span class="opblock-summary-path" data-path="/api/v1/payment/">status = 3</span></p>
<p><span class="opblock-summary-path" data-path="/api/v1/payment/">Через 20-30 секунд статус изменяется на status = 5 и отправляется вэбхук об изменении статуса на 5, что говорит о готовности принять смс-код или ожидание подтверждения транзакции в мобильном банке клиента.</span></p>
<p><span class="opblock-summary-path" data-path="/api/v1/payment/"><strong>2b. Отправка телефона отправителя</strong> (метод m10_to_m10): <a class="nostyle" href="https://asu-payme.com/api/v1/docs/#/API%20Payment%20process/payment_send_phone_update">/api<wbr />/v1<wbr />/payment<wbr />/{id}<wbr />/send_phone<wbr />/</a></span></p>
<p><span class="opblock-summary-path" data-path="/api/v1/payment/">status = 3</span></p>
<p><span class="opblock-summary-path" data-path="/api/v1/payment/"><strong>3. Отправка смс-кода:</strong> <a class="nostyle" href="https://asu-payme.com/api/v1/docs/#/API%20Payment%20process/payment_send_sms_code_update">/api<wbr />/v1<wbr />/payment<wbr />/{id}<wbr />/send_sms_code<wbr />/</a></span></p>
<div class="opblock-summary-description">&nbsp;</div>
<div class="opblock-summary-description">После обработки платежа отправляется вэбхук со статусом -1 при отклонении или 9 при подтверждении платежа.</div>""",

                   responses={
                       status.HTTP_201_CREATED: OpenApiResponse(
                           description='Created',
                           response=ResponseCreate,
                           examples=[
                               OpenApiExample(
                                   "Good example card_2",
                                   value={"status": "success", "id": "4caed007-2d31-489c-9f3d-a2af6ccf07e4",
                                          },
                                   status_codes=[201],
                                   response_only=False,
                               ),
                               OpenApiExample(
                                   "Good example m10_to_m10",
                                   value={"status": "success",
                                          "id": "4caed007-2d31-489c-9f3d-a2af6ccf07e4",
                                          "m10_phone": "+994513467642",
                                          "m10_link": "https://link.api.m10.az/arrHkAGFAnC3efBp8"
                                          },
                                   status_codes=[201],
                                   response_only=False,
                               ),
                               OpenApiExample(
                                   "Good example card-to-card",
                                   value={"status": "success", "id": "4caed007-2d31-489c-9f3d-a2af6ccf07e4",
                                          "pay_data": {
                                              "card_number": "1111111111119999",
                                              "card_bank": "Kapital Bank",
                                              "expired_month": 12,
                                              "expired_year": 25
                                          }
                                          },

                                   status_codes=[201],
                                   response_only=False,
                               ),
                           ]),


                       status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                           response=BadResponse,
                           description='Some errors',
                           examples=[
                               OpenApiExample(
                                   "Bad response",
                                   value={
                                       "amount": ["Ensure this value is greater than or equal to 1."]},
                                   status_codes=[400],
                                   response_only=False,
                               ),
                           ]),
                   },
                   )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            if serializer.data['pay_type'] == 'card-to-card':
                payment: Payment = serializer.instance
                card_data = payment.get_pay_data()
                return Response({'status': 'success',
                                 'id': serializer.data['id'],
                                 'pay_data': card_data
                                 },
                                status=status.HTTP_201_CREATED,
                                headers=headers)
            elif serializer.data['pay_type'] == 'm10_to_m10':
                payment: Payment = serializer.instance
                return Response(data={
                    'status': 'success',
                    'id': serializer.data['id'],
                    'm10_phone': payment.pay_requisite.info,
                    'm10_link': payment.pay_requisite.info2,
                }, status=status.HTTP_201_CREATED)

            return Response({'status': 'success', 'id': serializer.data['id']},
                            status=status.HTTP_201_CREATED,
                            headers=headers)
        return Response({'status': 'error'}, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        serializer.save(source='api')

    @extend_schema(tags=['API Payment process'], summary="Отправка даных карты (For pay_type ['card_2]')",
                   # description="После ввода предоставленных данных карты будет отправлен post-запрос: {'order_id': , 'id': id, 'status': 5,  'signature': }",
                   request=PaymentInputCardSerializer,
                   responses={status.HTTP_200_OK: OpenApiResponse(
                           response=PaymentInputCardSerializer,
                           examples=[
                               OpenApiExample(
                                   "Good example1",
                                   value={
                                       "sms_required": True,
                                       "instruction": None,
                                       "bank_icon": "http://127.0.0.1:8000/media/bank_icons/leo_C6uBNoS.jpg",
                                       "signature": "1bc6b5702f4fdce1f93590dc9a561aafbb227307b988ffd1c5e564ebef7ee9f6"
                                   },
                                   status_codes=[200],
                                   response_only=False,
                                   description="""string = card_number + secret_key (encoding UTF-8)<br>
signature = hash('sha256', $string)""",
                               ),
                               OpenApiExample(
                                   "Good example2",
                                   value={
    "sms_required": False,
    "instruction": "Ödənişi təstiqləmək üçün Leobank mobil tədbiqində Sizə bildiriş gələcək. Zəhmət olmasa, Leobank mobil tədbiqinə keçid edin və köçürməni təstiq edin.",
    "bank_icon": "http://127.0.0.1:8000/media/bank_icons/leo_C6uBNoS.jpg",
    "signature": "1bc6b5702f4fdce1f93590dc9a561aafbb227307b988ffd1c5e564ebef7ee9f6"
},
                                   status_codes=[200],
                                   response_only=False,
                                   description="""string = card_number + secret_key (encoding UTF-8)<br>
    signature = hash('sha256', $string)""",
                               ),
                           ]),

                       status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                           response=BadResponse,
                           description='Some errors',
                           examples=[
                               OpenApiExample(
                                   "Bad response",
                                   value={"expired_month": ["Ensure this value is less than or equal to 12."]},
                                   status_codes=[400],
                                   response_only=False,
                               ),
                           ]),

                   }
                   )
    @action(detail=True,
            methods=["PUT"],
            permission_classes=[PaymentOwnerOrStaff],)
    def send_card_data(self, request, *args, **kwargs):
        payment = get_object_or_404(Payment, id=self.kwargs.get("pk"))
        merchant = payment.merchant
        if merchant.white_ip:
            ip = get_client_ip(request)
            if ip not in merchant.ip_list():
                raise serializers.ValidationError(f'Your ip {ip} not in white list')
        if payment.status == -1:
            raise serializers.ValidationError({'status': 'payment Declined!'})
        serializer = PaymentInputCardSerializer(data=request.data)
        if serializer.is_valid():
            card_data = serializer.validated_data
            card_number = serializer.validated_data.get('card_number')
            phone_script = get_phone_script(card_number)
            payment.phone_script_data = phone_script.data_json()
            payment.status = 3
            bank = get_bank_from_bin(card_number[:6])
            url = request.build_absolute_uri(bank.image.url)
            sms_required = phone_script.step_2_required
            payment.card_data = json.dumps(card_data)
            payment.cc_data_input_time = timezone.now()
            payment.save()
            return Response(data={
                'sms_required': sms_required,
                'instruction': bank.instruction,
                'bank_icon': url,
                'signature': payment.get_hash()
            }, status=status.HTTP_200_OK)
        return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=['API Payment process'],
                   request=PaymentInputPhoneSerializer,
                   summary="Отправка номера телефона (For pay_type ['m10_to_m10]')",
                   description="Телефон в формате +994555001122",
                   responses={status.HTTP_200_OK: OpenApiResponse(
                       response=PaymentInputPhoneSerializer,
                       description='Ok',
                       examples=[
                           OpenApiExample(
                               "example1",
                               value={
                                   "phone": "+994555001122",
                                   "m10_phone": "+994 51 55 55 55",
                                   "m10_link": "https://link.api.m10.az/US7bLKooe8AE3Pxr5"
                               },
                               status_codes=[200],
                               response_only=False,
                           ),]),
                       status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                           response=BadResponse,
                           description='Bad number',
                           examples=[
                               OpenApiExample(
                                   "Bad number",
                                   value={"phone": ["Phone format must be +994555001122"]},
                                   status_codes=[400],
                                   response_only=False,
                               ),
                           ])
                   },
                   )
    @action(detail=True,
            methods=["PUT"],
            permission_classes=[PaymentOwnerOrStaff],)
    def send_phone(self, request, *args, **kwargs):
        payment = get_object_or_404(Payment, id=self.kwargs.get("pk"))
        merchant = payment.merchant
        if merchant.white_ip:
            ip = get_client_ip(request)
            if ip not in merchant.ip_list():
                raise serializers.ValidationError(f'Your ip {ip} not in white list')
        if payment.status in [-1, 9]:
            raise serializers.ValidationError({'error': f'payment finished: {payment.status}'})
        if payment.phone_send_counter > 3:
            raise serializers.ValidationError({'error': f'phone change limit'})
        serializer = PaymentInputPhoneSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            payment.phone = phone
            payment.status = 3
            data = serializer.data
            if payment.pay_requisite:
                data.update({'m10_phone': payment.pay_requisite.info,
                             'm10_link': payment.pay_requisite.info2
                             })
            payment.save()
            return Response(data=data, status=status.HTTP_200_OK)
        return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=['API Payment process'],
                   request=PaymentInputSmsCodeSerializer,
                   summary="Отправка кода подтверждения (For pay_type ['card_2]')",
                   description="Необходим если в шаге 'Отправка даных карты' sms_required=True.",
                   responses={status.HTTP_200_OK: OpenApiResponse(
                       response=ResponseInputSms,
                       examples=[
                           OpenApiExample(
                               "example1",
                               value={
                                   "status": "success",
                               },
                               status_codes=[200],
                               response_only=False,
                           ),
                           OpenApiExample(
                               "Bad response",
                               value={"sms_code": ["Ensure this field has no more than 6 characters."]},
                               status_codes=[400],
                               response_only=False,
                           ),
                       ])},
                   )
    @action(detail=True,
            methods=["PUT"],
            permission_classes=[PaymentOwnerOrStaff],)
    def send_sms_code(self, request, *args, **kwargs):
        payment = get_object_or_404(Payment, id=self.kwargs.get("pk"))
        merchant = payment.merchant
        if merchant.white_ip:
            ip = get_client_ip(request)
            if ip not in merchant.ip_list():
                raise serializers.ValidationError(f'Your ip {ip} not in white list')
        if payment.status == -1:
            raise serializers.ValidationError({'status': 'payment Declined!'})
        serializer = PaymentInputSmsCodeSerializer(data=request.data)
        if serializer.is_valid():
            card_data = json.loads(payment.card_data)
            card_data['sms_code'] = serializer.validated_data.get('sms_code')
            payment.card_data = json.dumps(card_data)
            payment.status = 6
            payment.save()
            return Response(data={'status': 'success'}, status=status.HTTP_200_OK)
        return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False,
            methods=["GET"],
            permission_classes=[])
    def day_confirmed(self, request, *args, **kwargs):
        print(request.user)
        file = export_payments_func(Payment.objects.all()[:100])
        return file


class BalanceViewSet(viewsets.GenericViewSet, generics.ListAPIView):
    serializer_class = BalanceSerializer
    queryset = BalanceChange.objects.all()
    permission_classes = [IsAuthenticated]
    filterset_class = BalanceChangeFilter

    def get_queryset(self):
        return BalanceChange.objects.filter(user=self.request.user)


class WorkerPaymentsView(mixins.ListModelMixin, viewsets.GenericViewSet):

    serializer_class = PaymentFullSerializer
    queryset = Payment.objects.all()
    permission_classes = [IsStaff]

    def get_queryset(self):
        logger.debug(f'work_operator: {self.request.user}')
        banks = self.request.user.profile.banks.all()
        print(banks)
        return Payment.objects.filter(status__in=[4],
                                      work_operator=self.request.user.id,
                                      bank__in=banks).order_by('counter')


class FullInfoView(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentFullSerializer
    queryset = Payment.objects.all()
    permission_classes = [IsStaff]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        return Response(data)


class PaymentStatusView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    # serializer_class = PaymentStaffSerializer
    serializer_class = PaymentGuestSerializer
    queryset = Payment.objects.all()
    permission_classes = [IsStaffOrReadOnly]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        if request.user.is_staff and instance.card_data:
            sms = json.loads(instance.card_data).get('sms_code')
            data.update({'sms_code': sms})
        return Response(data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


signature_text = """
<p>Передаются либо данные карты либо телефон для выплаты на m10</p>
<p><b>signature</b>* - required field (string)<br><br></p>
<p>Расчет signature:<br></p>
<p>string = merchant + card_number или target_phone + amount + secret_key (encoding UTF-8)</p>
<p>signature = hash('sha256', $string)</p>
В примере string = "2111122223333444430secret_key"
(card_number 16 цифр без лишних символов)
"""


@extend_schema(tags=['Withdraw'], summary='Заявки на выводы')
class WithdrawViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet, mixins.ListModelMixin):
    # serializer_class = WithdrawCreateSerializer
    # queryset = Withdraw.objects.all()
    authentication_classes = [JWTAuthentication]
    permission_classes = [PaymentOwnerOrStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = WithdrawFilter
    search_fields = ['id', 'withdraw_id']

    def get_queryset(self):
        threshold = timezone.now() - datetime.timedelta(days=365)
        return Withdraw.objects.filter(merchant__owner=self.request.user, create_at__gte=threshold).all()

    @extend_schema(tags=['Withdraw'],
                   summary='Создание withdraw',
                   description=signature_text,
                   examples=[OpenApiExample(
                       request_only=True, name='Example Card Data',
                       value={
                               "merchant": "2",
                               "withdraw_id": "your_withdraw_id-aaaa15320",
                               "card_data": {
                                   "owner_name": "Vasya Pupkin",
                                   "card_number": "1111-2222-3333-4444",
                                   "expired_month": "12",
                                   "expired_year": "26"
                               },
                               "amount": "30",
                               "signature": "218c2bbb12b28975f1db5ca8ff5fa740653a607896aa78308c7b7d29aaf30cd9",
                               "payload": {
                                   "field1": "data1",
                                   "field2": "data2"
                               }
                           },
                   ),
                       OpenApiExample(
                           request_only=True, name='Example M10',
                           value={
                               "merchant": "2",
                               "withdraw_id": "your_withdraw_id-aaaa15320",
                               "target_phone": "+994555001122",
                               "amount": "30",
                               "signature": "29fea979c5454a0014ff30de6e9c6210669b058e1556b1705f0e0e8938bdd28d",
                               "payload": {
                                   "field1": "data1",
                                   "field2": "data2"
                               }
                           },
                       )
                   ],
                   request=WithdrawCreateSerializer,
                   responses={
                       status.HTTP_201_CREATED: OpenApiResponse(
                           description='Created',
                           response=ResponseCreate,
                           examples=[
                               OpenApiExample(
                                   "Good example",
                                   value={"status": "success",
                                          "id": "f766758b-cb6a-4c4b-9d5d-342a97f7ac24"
                                          },
                                   status_codes=[201],
                                   response_only=True,
                               ),
                           ]),

                       status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                           response=BadResponse,
                           description='Some errors',
                           examples=[
                               OpenApiExample(
                                   "Bad response",
                                   value={
                                       "detail": "Given token not valid for any token type",
                                       "code": "token_not_valid",
                                       "messages": [
                                           {
                                               "token_class": "AccessToken",
                                               "token_type": "access",
                                               "message": "Token is invalid or expired"
                                           }
                                       ]
                                   },
                                   status_codes=[401],
                                   response_only=False,
                               ),
                           ]),
                   },
                   )
    def create(self, request, *args, **kwargs):
        if "signature" not in request.data:
            return Response({"non_field_errors": ["Wrong signature"]},
                            status=status.HTTP_400_BAD_REQUEST)
        signature = request.data.pop("signature")
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            data = serializer.validated_data
            shop = data["merchant"]
            target_data = data.get("card_data", {}).get("card_number") or data['target_phone']
            signature_string = f'{shop.id}{target_data}{int(data["amount"])}'
            logger.warning(f'{signature_string} + {shop.secret}')
            hash_s = hash_gen(signature_string, shop.secret)
            logger.warning(hash_s)
            if hash_s != signature:
                return Response({"non_field_errors": ["Wrong signature"]},
                                status=status.HTTP_400_BAD_REQUEST)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response({'status': 'success', 'id': serializer.data['id']},
                            status=status.HTTP_201_CREATED,
                            headers=headers)
        return Response({'status': 'error'}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=['Withdraw'],
                   summary='Просмотр статуса заяки на вывод',
                   # request=[
                   #     OpenApiExample(
                   #         "Bad response",
                   #         value={
                   #             "amount": ["Ensure this value is greater than or equal to 1."]},
                   #         status_codes=[400],
                   #         response_only=False,
                   #     ),
                   # ],
                   responses={
                       status.HTTP_200_OK: OpenApiResponse(
                           description='Ok',
                           response=ResponseCreate,
                           examples=[
                               OpenApiExample(
                                   "Good example",
                                   value={
                                            "id": "f766758b-cb6a-4c4b-9d5d-342a97f7ac24",
                                            "withdraw_id": "wddddda",
                                            "amount": 30,
                                            "status": 0,
                                            "payload": {
                                                "field1": "data1",
                                                "field2": "data2"
                                            }
                                   },
                                   status_codes=[200],
                                   response_only=False,
                               ),
                           ]),

                       status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                           response=BadResponse,
                           description='Some errors',
                           examples=[
                               OpenApiExample(
                                   "Bad response",
                                   value={
                                       "detail": "Given token not valid for any token type",
                                       "code": "token_not_valid",
                                       "messages": [
                                           {
                                               "token_class": "AccessToken",
                                               "token_type": "access",
                                               "message": "Token is invalid or expired"
                                           }
                                       ]
                                   },
                                   status_codes=[401],
                                   response_only=False,
                               ),
                           ]),
                   },
                   )
    def retrieve(self, request, *args, **kwargs):
        print('retrieve', args, kwargs)
        instance = self.get_object()
        serializer = WithdrawSerializer(instance)
        return Response(serializer.data)

    def get_serializer_class(self):
        if self.request.method == "POST":
            serializer_class = WithdrawCreateSerializer
        else:
            serializer_class = WithdrawSerializer
        return serializer_class


    # def get_queryset(self):
    #     print('get_queryset')
    #     print(self.serializer_class)
    #     return Withdraw.objects.filter(merchant__owner=self.request.user)
    #     # return super().get_queryset()
    #
    # def get_serializer(self):
    #     print('get_serializer')
    #     return super().get_serializer()

    # def list(self, request, *args, **kwargs):
    #     print(self.serializer_class)
    #     serializer = WithdrawSerializer()
    #     return Response(serializer.data)
