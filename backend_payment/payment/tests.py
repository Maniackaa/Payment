from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.test import TestCase

from core.global_func import hash_gen
from payment.models import Merchant, PayRequisite, Payment

User = get_user_model()


class TestPayment(TestCase):

    @classmethod
    def setUpTestData(cls):
        # call_command('import_bins')
        print('setUpTestData')
        cls.user = User.objects.create_user(username='user', password='test', email='email1@mail.ru')
        cls.merch_user = User.objects.create_user(username='merch_test', password='test', email='email2@mail.ru',
                                                  is_active=1, role='merchant')
        cls.merch_user2 = User.objects.create_user(username='merch_test2', password='test2', email='email22@mail.ru',
                                                   is_active=1, role='merchant')
        cls.admin = User.objects.create_superuser(username='admin', password='admin', email='email3@mail.ru')

        cls.shop = Merchant.objects.create(name='merch', secret='secret1', host='https://realpython.com/',
                                           owner=cls.merch_user)
        cls.shop2 = Merchant.objects.create(name='merch2', secret='secret2', host='https://realpython.com/',
                                            owner=cls.merch_user2)
        cls.shop_user = Merchant.objects.create(name='merch_user', secret='secret4', host='https://realpython.com/',
                                                owner=cls.user)

    def test_create_payment(self):
        print('test')
        print(self.user)
        print(self.merch_user, self.merch_user.id)
        merchant_id = self.merch_user.id
        order_id = 'b34823cc-6278-43c5-886a-f65b36c9b396'
        string_value = f'{merchant_id}{order_id}'
        merch = Merchant.objects.get(pk=merchant_id)
        merch_hash = hash_gen(string_value, merch.secret)
        url = f'/invoice/?merchant_id={merchant_id}&order_id={order_id}&amount=10&owner_name=John%20Dou&user_login=user_22216456&pay_type=card_2&signature={merch_hash}'
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)

        pay_type = PayRequisite.objects.create(pay_type='card_2', min_amount=10, max_amount=3000, is_active=True)
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200, 'Не создается платеж')
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.last()
        self.assertEqual(payment.status, 0)

    def test_create_payment2(self):
        print('test2')
        print(self.user)


