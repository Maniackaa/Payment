import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from django.core.management import call_command

from core.global_func import hash_gen
from payment.models import Merchant, Payment, PayRequisite, Withdraw, BalanceChange

User = get_user_model()

urls = ['/api/v1/payment/', '/api/v1/payment_status/']


class TestAPI(APITestCase):

    @classmethod
    def setUpTestData(cls):
        call_command('import_bins')
        cls.guest_client = APIClient()
        cls.client = APIClient()
        user = User.objects.create_user(username='user', password='test', email='email1@mail.ru')
        merch_user = User.objects.create_user(username='merch_test', password='test', email='email2'
                                                                                            '@mail.ru',
                                              is_active=1, role='merchant')
        merch_user2 = User.objects.create_user(username='merch_test2', password='test2', email='email22@mail.ru',
                                               is_active=1, role='merchant')
        operator = User.objects.create_user(username='operator1', password='test', email='oper1@mail.ru',
                                            is_staff=True, is_active=1, role='operator')
        admin = User.objects.create_superuser(username='admin', password='admin', email='email3@mail.ru')
        payment = Payment.objects.create(merchant_id=merch_user.id, order_id='payorderid1')
        cls.user = user
        cls.merch_user = merch_user
        cls.merch_user2 = merch_user2
        cls.admin = admin
        cls.operator = operator
        cls.payment = payment

        cls.shop = Merchant.objects.create(name='shop', secret='secret1', host='localhost', owner=merch_user)
        cls.shop2 = Merchant.objects.create(name='shop2', secret='secret2', host='localhost', owner=merch_user2)
        cls.shop_user = Merchant.objects.create(name='shop_user', secret='secret4', host='localhost', owner=user)
        cls.pay_type = PayRequisite.objects.create(pay_type='card_2', min_amount=10, max_amount=3000, is_active=True)

    def test_api_create_payment(self):
        # Тест создания платежа по api
        url = '/api/v1/payment/'

        # ПРоверка неавторизованного
        good_data = {"merchant": "1", "order_id": "testorder", "amount": "10", "pay_type": "card_2"},
        response = self.client.post(url, good_data)
        assert response.status_code >= 400
        self.client.force_authenticate(user=self.user)
        response = self.client.post(url, good_data)
        assert response.status_code >= 400

        # ПРоверка авторизованного c плохими данными
        self.client.force_authenticate(user=self.merch_user)
        bad_data = [
            {"merchant": "2", "order_id": "", "amount": "10", "pay_type": "card_2"},
            {"merchant": "1", "order_id": "testorder3", "amount": "", "pay_type": ""},
            {"merchant": "", "order_id": "testorder4", "amount": "10", "pay_type": "card_2"},
            {"merchant": "1", "amount": "10", "pay_type": "card_2"},
            {"merchant": "1", "order_id": "testorder5", "pay_type": "card_2"},
            {"merchant": "1", "order_id": "testorder6", "amount": "10"},
            {"order_id": "testorder7", "amount": "10", "pay_type": "card_2"},
            {"merchant": "2", "order_id": "testorder8", "amount": "10", "pay_type": "card_2"},
        ]

        for data in bad_data:
            response = self.client.post(url, data)
            assert response.status_code == 400, f'Cоздается платеж который не должен создаваться: {data}'

        # ПРоверка других методов кроме post
        data = {"merchant": "2", "order_id": "testorder33", "amount": "10", "pay_type": "card_2"}
        response = self.client.get(url, data)
        assert response.status_code == 405
        response = self.client.put(url, data)
        assert response.status_code == 405
        response = self.client.patch(url, data)
        assert response.status_code == 405
        response = self.client.delete(url, data)
        assert response.status_code == 405

        # Проверка авторизованного мерча
        self.client.force_authenticate(user=self.merch_user)
        good_data = [
            {"merchant": "1", "order_id": "testorder", "amount": "10", "pay_type": "card_2"},
            {"merchant": "1", "order_id": "testorder2", "amount": "10", "pay_type": "card_2"},
        ]
        start_count = Payment.objects.count()
        for data in good_data:
            response = self.client.post(url, data)
            assert response.status_code == 201, 'Не создается платеж зарегистрированного мерча'
        self.assertEqual(Payment.objects.count(), start_count + len(good_data), 'Не создается 2 платежа')

        # Проверка авторизованного но юзером
        self.client.force_authenticate(user=self.user)
        good_data = [
            {"merchant": "3", "order_id": "testorderu", "amount": "10", "pay_type": "card_2"},
            {"merchant": "3", "order_id": "testorderu1", "amount": "10", "pay_type": "card_2"},
        ]
        start_count = Payment.objects.count()
        for data in good_data:
            response = self.client.post(url, data)
            assert response.status_code >= 400, 'Создается платеж простым юзером'
        self.assertEqual(Payment.objects.count(), start_count, 'Создается платеж простым юзером')

        self.client.force_authenticate(user=self.merch_user2)
        good_data = [
            {"merchant": "2", "order_id": "testorder22", "amount": "10", "pay_type": "card_2"},
            {"merchant": "2", "order_id": "testorder23", "amount": "10", "pay_type": "card_2"},
        ]
        for data in good_data:
            response = self.client.post(url, data)
            assert response.status_code == 201, 'Не создается платеж зарегистрированного мерча'

        # ПРоверка на дубль
        data = {"merchant": "1", "order_id": "testorder", "amount": "10", "pay_type": "card_2"},
        response = self.client.post(url, data)
        assert response.status_code == 400

    def test_full_steps(self):
        start_url = '/api/v1/payment/'
        self.client.force_authenticate(user=self.merch_user)
        data = {"merchant": "1", "order_id": "testorder1", "amount": "10", "pay_type": "card_2"}
        start_count = Payment.objects.count()
        response = self.client.post(start_url, data)
        assert response.status_code == 201, f'Не создается платеж зарегистрированного мерча: {data}'
        pk = response.data.get('id')
        self.assertEqual(Payment.objects.count(),start_count + 1, 'Количество платежей не увеличилось')

        payment = Payment.objects.get(pk=pk)
        self.assertEqual(payment.status, 0, 'Payment оздался со статусом не 0')

        url = start_url + f'{pk}/send_card_data/'
        data = {
                "card_number": "4098582233334444",
                "expired_month": "12",
                "expired_year": "26",
                "cvv": "2131"}

        response = self.client.put(url, data)
        assert response.status_code == 200, f'Не верный прием данных карты: {data}'
        payment = Payment.objects.get(pk=pk)
        self.assertEqual(payment.status, 3, 'Payment статус не 3')

        url = start_url + f'{pk}/send_sms_code/'
        data = {"sms_code": "134q"}
        response = self.client.put(url, data)
        assert response.status_code == 200, f'Не верный прием смс: {data}'

        # Просмотр платежа
        url = f'/api/v1/payment_status/{pk}/'
        print(url)
        data = {'id': pk}

        response = self.guest_client.get(url, data)
        self.assertEqual(response.status_code, 200, 'Не показывается статус платежа')
        self.assertEqual(response.json(),  {'id': pk, 'status': 3}, 'Не верный ответ статуса платежа анонимом')

        payment = Payment.objects.get(pk=pk)
        self.assertEqual(payment.status, 3, 'После передачи данных карты статус не 3')

        # Подтверждение платежа
        response = self.client.put(url, data={'status': 9})
        self.assertEqual(response.status_code, 403, 'Меняется статус мерчем. Ответ не 403')
        self.client.force_authenticate(user=self.operator)
        response = self.client.put(url, data={'status': 9})
        self.assertEqual(response.status_code, 200, 'Не меняется статус оператором')

        payment = Payment.objects.get(pk=pk)
        self.assertEqual(payment.status, 9, 'Не подтверждается платеж оператором по API')

    def test_create_withdraw(self):
        # Тест создание вывода"
        url = '/api/v1/withdraw/'
        self.assertIsInstance(self.payment, Payment)
        self.client.force_authenticate(self.merch_user)
        card_data = {
            "owner_name": "Vasya Pupkin",
            "card_number": "1111222233334444",
            "expired_month": "12",
            "expired_year": "26"
        }
        amount = 30
        signature_string = f'{self.shop.id}{card_data["card_number"]}{amount}'
        data = {
            "merchant": self.shop.id,
            "withdraw_id": "test_idee4rde4eee4errr3",
            "card_data": card_data,
            "amount": "30.0",
            "signature": hash_gen(signature_string, self.shop.secret),
            "payload": {
                "field1": "data1",
                "field2": "data2"
            }
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 201, 'Не создается вывод')

    def test_withdraw_confirm(self):
        self.test_create_withdraw()
        self.assertEqual(Withdraw.objects.count(), 1)
        withdraw = Withdraw.objects.last()
        # ПРи подтверждении вывода меняется баланс на сумму + комиссию.
        shop = withdraw.merchant
        self.assertEqual(shop.name, 'shop')
        owner = shop.owner
        self.assertEqual(owner.username, 'merch_test')
        self.assertIsInstance(shop, Merchant)
        self.assertIsInstance(owner, User)
        withdraw.status = 9
        withdraw.confirmed_user = self.operator
        withdraw.save()
        owner = User.objects.get(username=owner.username)
        self.assertEqual(owner.balance, -30.9, 'Не верно меняетя баланс')
        self.assertNotEqual(withdraw.confirmed_time, None)
        # Сохраняется изменение баланса
        last_log = BalanceChange.objects.last()
        self.assertEqual(last_log.amount, -30.9)
        self.assertEqual(last_log.user, owner)