from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase
from django.core.management import call_command

from payment.models import Merchant, Payment, PayRequisite

User = get_user_model()

urls = ['/api/v1/payment/', '/api/v1/payment_status/']


class TestAPI(APITestCase):

    @classmethod
    def setUpTestData(cls):
        call_command('import_bins')
        cls.client = APIClient()
        user = User.objects.create_user(username='user', password='test', email='email1@mail.ru')
        merch_user = User.objects.create_user(username='merch_test', password='test', email='email2@mail.ru',
                                              is_active=1, role='merchant')
        merch_user2 = User.objects.create_user(username='merch_test2', password='test2', email='email22@mail.ru',
                                               is_active=1, role='merchant')
        admin = User.objects.create_superuser(username='admin', password='admin', email='email3@mail.ru')
        cls.user = user
        cls.merch_user = merch_user
        cls.merch_user2 = merch_user2
        cls.admin = admin

        cls.shop = Merchant.objects.create(name='merch', secret='secret1', host='localhost', owner=merch_user)
        cls.shop2 = Merchant.objects.create(name='merch2', secret='secret2', host='localhost', owner=merch_user2)
        cls.shop_user = Merchant.objects.create(name='merch_user', secret='secret4', host='localhost', owner=user)
        cls.pay_type = PayRequisite.objects.create(pay_type='card_2', min_amount=10, max_amount=3000, is_active=True)

    def test_create_payment(self):
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

        # Проверка авторизованного но юзером
        self.client.force_authenticate(user=self.user)
        good_data = [
            {"merchant": "3", "order_id": "testorderu", "amount": "10", "pay_type": "card_2"},
            {"merchant": "3", "order_id": "testorderu1", "amount": "10", "pay_type": "card_2"},
        ]
        for data in good_data:
            response = self.client.post(url, data)
            assert response.status_code >= 400, 'Создается платеж простым юзером'
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

    def test_full_steps(self):
        start_url = '/api/v1/payment/'
        self.client.force_authenticate(user=self.merch_user)
        data = {"merchant": "1", "order_id": "testorder1", "amount": "10", "pay_type": "card_2"}
        response = self.client.post(start_url, data)
        assert response.status_code == 201, f'Не создается платеж зарегистрированного мерча: {data}'
        pk = response.data.get('id')
        assert Payment.objects.count() == 1

        url = start_url + f'{pk}/send_card_data/'
        data = {
                "card_number": "4098582233334444",
                "expired_month": "12",
                "expired_year": "26",
                "cvv": "2131"}

        response = self.client.put(url, data)
        assert response.status_code == 200, f'Не верный прием данных карты: {data}'

        url = start_url + f'{pk}/send_sms_code/'
        data = {"sms_code": "134q"}
        response = self.client.put(url, data)
        assert response.status_code == 200, f'Не верный прием смс: {data}'

