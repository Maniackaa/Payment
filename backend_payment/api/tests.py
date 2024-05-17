from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.test import TestCase

from payment.models import Merchant, Payment

User = get_user_model()

urls = ['/api/payment/', '/api/payment_status/']


class TestAPI(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(username='user', password='test', email='email1@mail.ru')
        self.merch_user = User.objects.create_user(username='merch_test', password='test', email='email2@mail.ru', is_active=1, role='merchant')
        self.merch_user2 = User.objects.create_user(username='merch_test2', password='test2', email='email22@mail.ru',
                                                   is_active=1, role='merchant')
        self.admin = User.objects.create_superuser(username='admin', password='admin', email='email3@mail.ru')

        self.shop = Merchant.objects.create(name='merch', secret='secret1', host='localhost', owner=self.merch_user)
        self.shop2 = Merchant.objects.create(name='merch2', secret='secret2', host='localhost', owner=self.merch_user2)

    def test_create_payment(self):
        # Тест создания платежа по api
        url = '/api/payment/'

        # ПРоверка неавторизованного
        good_data = {"merchant": "1", "order_id": "testorder", "amount": "10", "pay_type": "card_2"},
        response = self.client.post(url, good_data)
        assert response.status_code == 400
        self.client.force_authenticate(user=self.user)
        response = self.client.post(url, good_data)
        assert response.status_code == 400

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
        assert Payment.objects.all().exists() is False


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
        for data in good_data:
            response = self.client.post(url, data)
            assert response.status_code == 201, 'Не создается платеж зарегистрированного мерча'
        assert Payment.objects.count() == 2

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
