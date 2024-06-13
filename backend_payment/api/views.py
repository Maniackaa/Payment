import json

import structlog
from django.http import JsonResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse, extend_schema_view, \
    extend_schema_serializer, extend_schema_field, inline_serializer

from rest_framework import viewsets, status, generics, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action, api_view
from rest_framework.generics import GenericAPIView, get_object_or_404, CreateAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated

from rest_framework.response import Response
from rest_framework import mixins
from rest_framework.views import APIView

from rest_framework_simplejwt.authentication import JWTAuthentication

from api.permissions import PaymentOwnerOrStaff, IsStaff, IsStaffOrReadOnly
from api.serializers import PaymentCreateSerializer, PaymentInputCardSerializer, \
    PaymentInputSmsCodeSerializer, PaymentStaffSerializer, PaymentTypesSerializer, WithdrawCreateSerializer, \
    WithdrawSerializer
from core.global_func import hash_gen
from payment.models import Payment, PayRequisite, Withdraw
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
        serializer = self.get_serializer(instance)
        return Response(data={'id': instance.id, 'status': instance.status}, status=status.HTTP_200_OK)

    @extend_schema(tags=['API Payment process'], request=PaymentCreateSerializer, summary="Создание платежа",
                   description='Отправка данных для создания платежа',

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
                                   "Good example",
                                   value={
    "sms_required": False,
    "instruction": "Ödənişi təstiqləmək üçün Leobank mobil tədbiqində Sizə bildiriş gələcək. Zəhmət olmasa, Leobank mobil tədbiqinə keçid edin və köçürməni təstiq edin.",
    "bank_icon": "http://127.0.0.1:8000/media/bank_icons/leo_C6uBNoS.jpg",
    "signature": "1bc6b5702f4fdce1f93590dc9a561aafbb227307b988ffd1c5e564ebef7ee9f6"
},
                                   status_codes=[200],
                                   response_only=False,
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
            payment.save()
            return Response(data={
                'sms_required': sms_required,
                'instruction': bank.instruction,
                'bank_icon': url,
                'signature': payment.get_hash()
            }, status=status.HTTP_200_OK)
        return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=['API Payment process'],
                   request=PaymentInputSmsCodeSerializer,
                   summary="Отправка кода подтверждения (For pay_type ['card_2]')",
                   description="Необходим если sms_required=True. После ввода предоставленных данных карты будет отправлен информирующий post-запрос:<br>{'order_id': 'string', 'id': '4caed007-2d31-489c-9f3d-a2af6ccf07e4', 'status': 5,  'signature': hash('sha256', 'card_number' + 'secret_key')}",
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
        serializer = PaymentInputSmsCodeSerializer(data=request.data)
        if serializer.is_valid():
            card_data = json.loads(payment.card_data)
            card_data['sms_code'] = serializer.validated_data.get('sms_code')
            payment.card_data = json.dumps(card_data)
            payment.save()
            return Response(data={'status': 'success'}, status=status.HTTP_200_OK)
        return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentInputCard(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentInputCardSerializer
    queryset = Payment.objects.all()
    permission_classes = [PaymentOwnerOrStaff]
    http_method_names = ['put']


class PaymentInputSmsCode(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentInputSmsCodeSerializer
    queryset = Payment.objects.all()
    permission_classes = [PaymentOwnerOrStaff]
    http_method_names = ['put']


# class CsrfExemptSessionAuthentication(SessionAuthentication):
#     def enforce_csrf(self, request):
#         return None


class PaymentStatusView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentStaffSerializer
    queryset = Payment.objects.all()
    permission_classes = [IsStaffOrReadOnly]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        if request.user.is_staff and instance.card_data:
            sms = json.loads(instance.card_data).get('sms_code')
            data.update({'sms_code': sms})
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


signature_text = """<p><b>signature</b>* - required field (string)<br><br></p>
<p>Расчет signature:<br></p>
<p>string = merchant + card_number + amount + secret_key (encoding UTF-8)</p>
<p>signature = hash('sha256', $string)</p>
В примере string = "2111122223333444430secret_key"
"""


@extend_schema(tags=['Withdraw'], summary='Заявки на выводы')
class WithdrawViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = WithdrawCreateSerializer
    queryset = Withdraw.objects.all()
    authentication_classes = [JWTAuthentication]
    permission_classes = [PaymentOwnerOrStaff]

    @extend_schema(tags=['Withdraw'],
                   summary='Создание withdraw',
                   description=signature_text,
                   examples=[OpenApiExample(
                       request_only=True, name='Good Example',
                       value={
                               "merchant": "2",
                               "withdraw_id": "your_withdraw_id-aaaa15320",
                               "card_data": {
                                   "owner_name": "Vasya Pupkin",
                                   "card_number": "1111222233334444",
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
                   )],
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
        print(request.data)
        if "signature" not in request.data:
            return Response({"non_field_errors": ["Wrong signature"]},
                            status=status.HTTP_400_BAD_REQUEST)
        signature = request.data.pop("signature")
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            data = serializer.validated_data
            shop = data["merchant"]
            signature_string = f'{shop.id}{data["card_data"]["card_number"]}{data["amount"]}'
            hash_s = hash_gen(signature_string, shop.secret)
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
        instance = self.get_object()
        serializer = WithdrawSerializer(instance)
        return Response(serializer.data)
