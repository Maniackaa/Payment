from aiohttp.test_utils import TestClient
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.http import HttpResponseRedirect
from django.test import Client, TestCase

from core.global_func import hash_gen
from payment.models import Merchant, PayRequisite, Payment, BalanceChange, Withdraw

User = get_user_model()



class TestPayment(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command('import_bins')
        print('setUpTestData')
        cls.user = User.objects.create_user(username='user', password='test', email='email1@mail.ru', is_active=True)
        cls.merch_user = User.objects.create_user(username='merch_test', password='test', email='email2@mail.ru',
                                                  is_active=1, role='merchant')
        cls.merch_user2 = User.objects.create_user(username='merch_test2', password='test2', email='email22@mail.ru',
                                                   is_active=1, role='merchant')
        cls.admin = User.objects.create_superuser(username='admin', password='admin', email='email3@mail.ru')
        cls.operator = User.objects.create_user(username='operator', password='oper', email='oper@mail.ru',
                                                   is_active=True, role='operator', is_staff=True)

        cls.shop = Merchant.objects.create(name='merch', secret='secret1', host='https://realpython.com/',
                                           owner=cls.merch_user)
        cls.shop2 = Merchant.objects.create(name='merch2', secret='secret2', host='https://realpython.com/',
                                            owner=cls.merch_user2)
        cls.shop_user = Merchant.objects.create(name='merch_user', secret='secret4', host='https://realpython.com/',
                                                owner=cls.user)

    def test_create_payment(self):
        print('test')
        shop_id = self.shop.id
        order_id = 'b34823cc-6278-43c5-886a-f65b36c9b396'
        shop = Merchant.objects.get(pk=shop_id)
        string_value = f'{shop.id}{order_id}'
        merch_hash = hash_gen(string_value, shop.secret)
        url = f'/invoice/?merchant_id={shop.id}&order_id={order_id}&amount=10&owner_name=John%20Dou&user_login=user_22216456&pay_type=card_2&signature={merch_hash}'
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 400, 'Платеж создается без наличия типа')
        self.assertEqual(Payment.objects.count(), 0)

        PayRequisite.objects.create(pay_type='card_2', min_amount=3, max_amount=3000, is_active=True)
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200, 'Не создается платеж')
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.last()
        self.assertEqual(payment.status, 0, 'Статус платежа не 0')

    def test_balance(self):
        amount = 100
        payment = Payment.objects.create(merchant=self.shop,
                                         amount=amount,
                                         order_id='1'
                                         )
        self.assertIsInstance(payment, Payment)
        payment.status = 9
        payment.save()
        owner = payment.merchant.owner
        user = User.objects.get(pk=owner.id)
        tax = user.tax
        self.assertEqual(user.balance, amount - tax, 'Неверный расчет баланса')

        payment = Payment.objects.create(merchant=self.shop,
                                         amount=amount,
                                         order_id='1'
                                         )
        payment.status = 9
        payment.save()
        user = User.objects.get(pk=user.id)
        self.assertEqual(user.balance, 2 * (amount - tax), 'Неверный расчет баланса')

        withdraws = BalanceChange.objects.all()
        self.assertEqual(withdraws.count(), 2)

    def test_urls(self):
        # anonymous, user, merch, other_merch, staff
        payment = Payment.objects.create(merchant=self.shop,
                                         amount=100,
                                         order_id='1')
        withdraw = Withdraw.objects.create(merchant=self.shop, amount=100, withdraw_id=1)
        self.assertIsInstance(withdraw, Withdraw)
        #GET
        guest = Client()
        user_client = Client()
        user_client.force_login(self.user)
        merch_client = Client()
        merch_client.force_login(self.merch_user)
        other_merch_client = Client()
        other_merch_client.force_login(self.merch_user2)
        staff_client = Client()
        staff_client.force_login(self.operator)

        clients_names = ('guest', 'user_client', 'merch_client', 'other_merch_client', 'staff_client')
        clients = (guest, user_client, merch_client, other_merch_client, staff_client)
        urls = {
            '': (302, 200, 200, 200, 200),
            '/payment_type_not_worked/': (200, 200, 200, 200, 200),
            '/invoice/': (400, 400, 400, 400, 400),
            '/pay_to_card_create/': (400, 400, 400, 400, 400),
            '/pay_to_m10_create/': (400, 400, 400, 400, 400),
            '/pay_result/': (404, 404, 404, 404, 404),
            f'/pay_result/{payment.id}/': (200, 200, 200, 200, 200),
            '/payments/': (302, 302, 302, 302, 200),
            f'/payments/{payment.id}/': (302, 302, 302, 302, 200),
            '/withdraws/': (302, 302, 302, 302, 200),
            f'/withdraws/{withdraw.id}/': (302, 302, 302, 302, 200),
            f'/balance/': (302, 200, 200, 200, 200),
            f'/create_merchant/': (302, 302, 200, 200, 302),
            f'/merchant/{self.shop.id}/': (302, 302, 200, 302, 302),
            f'/merchant_delete/{self.shop.id}/': (302, 302, 200, 302, 302),
            f'/merchant_orders/': (302, 302, 200, 200, 302),
            f'/merchant_test_webhook/': (302, 400, 400, 400, 400),

        }
        for url, data in urls.items():
            for i, response_code in enumerate(data):
                with self.subTest(response_code_code=response_code):
                    client = clients[i]
                    response = client.get(url)
                    self.assertEqual(
                        response.status_code, data[i], f'Url: "{url}". {clients_names[i]} ответ не {response_code}')

