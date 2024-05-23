from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.http import HttpResponseRedirect
from django.test import TestCase

from core.global_func import hash_gen
from payment.models import Merchant, PayRequisite, Payment, Withdraw

User = get_user_model()


class TestPayment(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command('import_bins')
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

        withdraws = Withdraw.objects.all()
        self.assertEqual(withdraws.count(), 2)
        print('withdraws:', withdraws)
        for x in withdraws:
            print(x.amount, x.comment, x.payment)
