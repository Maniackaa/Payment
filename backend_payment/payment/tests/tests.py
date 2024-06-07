from aiohttp.test_utils import TestClient
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.http import HttpResponseRedirect
from django.test import Client, TestCase, override_settings

from core.global_func import hash_gen
from deposit.models import Incoming
from payment.models import Merchant, PayRequisite, Payment, BalanceChange, Withdraw, CreditCard
from payment.views import get_pay_requisite

User = get_user_model()


def get_url_to_create_payment(amount, order_id, pay_type='card_2') -> str:
    shop = Merchant.objects.get(name='merch')
    shop_id = shop.id
    string_value = f'{shop_id}{order_id}'
    merch_hash = hash_gen(string_value, shop.secret)
    url = f'/invoice/?merchant_id={shop_id}&order_id={order_id}&amount={amount}&owner_name=John%20Dou&user_login=user_22216456&pay_type={pay_type}&signature={merch_hash}&back_url=https://stackoverflow.com/questions'
    return url


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
        cls.card1 = CreditCard.objects.create(
            card_number='1111222233331111',
            expired_year=26,
            expired_month=12,
            card_type='MIR'
        )

    def test_create_payment_card_2(self):
        # Проверка создания платежа card_2 через браузер
        print('test')
        shop_id = self.shop.id
        order_id = 'b34823cc-6278-43c5-886a-f65b36c9b396'
        shop = Merchant.objects.get(pk=shop_id)
        string_value = f'{shop.id}{order_id}'
        merch_hash = hash_gen(string_value, shop.secret)
        url = f'/invoice/?merchant_id={shop.id}&order_id={order_id}&amount=10&owner_name=John%20Dou&user_login=user_22216456&pay_type=card_2&signature={merch_hash}&back_url=https://stackoverflow.com/questions'
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 400, 'Платеж создается без наличия типа')
        self.assertEqual(Payment.objects.count(), 0)

        PayRequisite.objects.create(pay_type='card_2', min_amount=3, max_amount=3000, is_active=True)

        bad_sign_url = f'/invoice/?merchant_id={shop.id}&order_id={order_id}&amount=10&owner_name=John%20Dou&user_login=user_22216456&pay_type=card_2&signature={merch_hash}x&back_url=https://stackoverflow.com/questions'
        response = self.client.get(bad_sign_url, follow=True)
        self.assertEqual(response.status_code, 400, 'Создается платеж с неверной сигнатурой')

        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200, 'Не создается платеж')
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.last()
        self.assertEqual(payment.status, 0, 'Статус платежа не 0')
        self.assertEqual(payment.referrer, 'https://stackoverflow.com/questions', 'Не сохраняется back_url')

    def test_create_payment_card_to_card(self):
        # Проверка создания платежа card_to_card через браузер
        card = self.card1
        pay_req = PayRequisite.objects.create(card=card, pay_type='card-to-card', min_amount=3, max_amount=3000, is_active=True)
        self.assertEqual(pay_req.card, card)
        shop_id = self.shop.id
        order_id = 'orderx'
        shop = Merchant.objects.get(pk=shop_id)
        string_value = f'{shop.id}{order_id}'
        url = get_url_to_create_payment(amount=1, order_id=order_id, pay_type='card-to-card')
        print(f'url: {url}')
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.last()
        self.assertEqual(payment.amount, 1)
        self.assertEqual(payment.status, 0, 'Статус платежа не 0')
        self.assertEqual(payment.referrer, 'https://stackoverflow.com/questions', 'Не сохраняется back_url')

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

    def test_payment_card_to_card(self):
        # Тест заявки card-to-card, выдачи карт для оплаты и проверка автоматического подтверждения платежа
        card1 = self.card1
        pay_req1 = PayRequisite.objects.create(pay_type='card-to-card', card=card1, min_amount=10, is_active=True)
        self.assertIsInstance(pay_req1, PayRequisite)
        selected_pay_req = get_pay_requisite('card-to-card')
        self.assertIsInstance(selected_pay_req, PayRequisite, 'Не выдаются реквизиты')

        # Создаем заявку на 10:
        order_id = 'order1'
        # response = self.create_payment(amount=10, order_id='order1', pay_type='card-to-card')
        url = get_url_to_create_payment(amount=10, order_id='order1', pay_type='card-to-card')
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200, 'Не создается Payment card-to-card')
        payments_with_payreq = Payment.objects.filter(pay_requisite__isnull=False)
        self.assertEqual(payments_with_payreq.count(), 1, 'Заявок с реквизитами не 1')

        payment = Payment.objects.get(order_id=order_id)

        #  Приходит смс-ка с нужной суммой
        incoming = Incoming.objects.create(recipient='1111****1111', pay=10)

        incoming.refresh_from_db()
        # Проверим что к смс привязался платеж:
        self.assertIsInstance(incoming.confirmed_payment, Payment, 'К смс не привязался платеж')

        # Проверим что подтвердиласвь заявка и освободились реквизиты:
        payment.refresh_from_db()
        self.assertEqual(payment.status, 9, 'Не подтвердился автоматически платеж')
        self.assertEqual(payment.pay_requisite, None, 'Не освободились реквизиты')

    @staticmethod
    def create_card(number):
        return CreditCard.objects.create(card_number=number, expired_year=26, expired_month=12)

    # @override_settings(DEBUG='True')
    def test_pay_requsite(self):
        # Тест выдачи реквизитов
        pass
        self.assertEqual(PayRequisite.objects.filter(pay_type='card-to-card').count(), 0, 'Реквизиты не пустые')
        card1 = CreditCard.objects.create(card_number=1111333344441111, expired_year=26, expired_month=12)
        card2 = CreditCard.objects.create(card_number=1111333344442222, expired_year=26, expired_month=12)
        card3 = CreditCard.objects.create(card_number=1111333344443333, expired_year=26, expired_month=12)
        pay_req1 = PayRequisite.objects.create(pay_type='card-to-card', card=card1, min_amount=10, is_active=True)
        pay_req2 = PayRequisite.objects.create(pay_type='card-to-card', card=card2, min_amount=10, is_active=True)
        pay_req3 = PayRequisite.objects.create(pay_type='card-to-card', card=card3, min_amount=10, is_active=True)
        self.assertEqual(PayRequisite.objects.filter(pay_type='card-to-card').count(), 3, 'Реквизитов не 3')
        self.assertEqual(Payment.objects.count(), 0)

        url = get_url_to_create_payment(amount=11, order_id='1', pay_type='card-to-card')
        self.client.get(url, follow=True)
        pay1 = Payment.objects.get(order_id='1')  # 1111333344441111
        self.assertEqual(pay1.order_id, '1')
        # self.assertEqual(pay1.pay_requisite, pay_req1, '1 из 3 не 1')
        self.assertEqual(Payment.objects.count(), 1)

        url = get_url_to_create_payment(amount=11, order_id='2', pay_type='card-to-card')
        self.client.get(url, follow=True)

        pay2 = Payment.objects.get(order_id='2')   # 1111333344442222
        self.assertEqual(pay2.order_id, '2')
        self.assertEqual(Payment.objects.count(), 2)
        # self.assertEqual(pay2.pay_requisite, pay_req2, '2 из 3 не 2')
        #
        url = get_url_to_create_payment(amount=11, order_id='3', pay_type='card-to-card')
        self.client.get(url, follow=True)
        pay3 = Payment.objects.get(order_id='3')  # 1111333344443333
        self.assertEqual(pay3.order_id, '3')
        self.assertEqual(Payment.objects.count(), 3)
        # self.assertEqual(pay3.pay_requisite, pay_req3, '3 из 3 не 3')
        #
        url = get_url_to_create_payment(amount=12, order_id='4', pay_type='card-to-card')
        response = self.client.get(url, follow=True)
        pay4 = Payment.objects.get(order_id='4')  # 1111333344441111
        self.assertEqual(pay4.order_id, '4')
        # self.assertEqual(pay4.pay_requisite, pay_req1)
        self.assertEqual(response.status_code, 200)

        url = get_url_to_create_payment(amount=12, order_id='5', pay_type='card-to-card')
        response = self.client.get(url, follow=True)
        pay5 = Payment.objects.get(order_id='5')
        self.assertEqual(pay5.order_id, '5')    # 1111333344442222
        # self.assertEqual(pay5.pay_requisite, pay_req2)
        self.assertEqual(response.status_code, 200)

        pay1.refresh_from_db()
        self.assertEqual(pay1.status, 0)
        self.assertEqual(pay2.status, 0)
        self.assertEqual(pay3.status, 0)
        self.assertEqual(pay4.status, 0)
        self.assertEqual(pay5.status, 0)

        # Пришла смс и подтвердился платеж
        Incoming.objects.create(recipient=pay1.pay_requisite.card.card_number, pay=11)
        pay1.refresh_from_db()
        self.assertEqual(pay1.status, 9, 'Не подтвердилась заявка 1')

        Incoming.objects.create(recipient=pay3.pay_requisite.card.card_number, pay=11)
        pay3.refresh_from_db()
        pay4.refresh_from_db()
        pay5.refresh_from_db()
        self.assertEqual(pay3.status, 9)
        self.assertEqual(pay4.status, 0)
        self.assertEqual(pay5.status, 0)

        Incoming.objects.create(recipient=pay2.pay_requisite.card.card_number, pay=11)
        pay1.refresh_from_db()
        pay2.refresh_from_db()
        pay3.refresh_from_db()
        pay4.refresh_from_db()
        pay5.refresh_from_db()
        self.assertEqual(pay2.status, 9)
        self.assertEqual(pay3.status, 9)
        self.assertEqual(pay4.status, 0)
        self.assertEqual(pay5.status, 0)

        Incoming.objects.create(recipient=pay4.pay_requisite.card.card_number, pay=12)
        pay4.refresh_from_db()
        self.assertEqual(pay4.status, 9)

        Incoming.objects.create(recipient=pay5.pay_requisite.card.card_number, pay=12)
        pay5.refresh_from_db()
        self.assertEqual(pay5.status, 9)
        self.assertEqual(pay5.amount, 12)
        self.assertEqual(pay5.confirmed_amount, pay5.amount)
