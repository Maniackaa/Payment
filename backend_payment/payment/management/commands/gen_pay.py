import datetime
import io
import random
import uuid

from PIL.Image import Image
from django.contrib.auth import get_user_model
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand, CommandError

from backend_payment.settings import BASE_DIR
from core.global_func import TZ
from payment.management.commands.bins import bins, banks
from payment.models import PhoneScript, Bank, Merchant, Payment, PayRequisite

User = get_user_model()


def get_status():
    x = random.randint(0, 100)
    if x > 97:
        return -1
    else:
        return 9


def get_amount():
    x = random.randint(30, 2000)
    amounts = [15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 300, 400, 500, 700, 1000]
    w = [10, 9, 9, 9, 3, 7, 6, 5, 4, 3, 3, 2, 2, 1, 1, 1, 1]

    return random.choices(population=amounts, weights=w, k=1)[0]


class Command(BaseCommand):
    help = 'generate'
    def handle(self, *args, **kwargs):

        start = datetime.datetime(2024, 5, 30, 0, 0, tzinfo=TZ)
        merch_user = User.objects.get(username='slot_machine')
        merch_user.balance = 0
        merch_user.save()
        pay_requisite = PayRequisite.objects.filter(pay_type='card_2').first()
        shop = Merchant.objects.get(pk=2)
        operator = User.objects.get(username='opertest1')
        Payment.objects.filter(merchant=shop).delete()
        current_time = start
        while current_time < datetime.datetime(2024, 6, 1, tzinfo=TZ):
            current_time += datetime.timedelta(seconds=random.randint(10, 90))
            amount = int(get_amount())
            payment = Payment.objects.create(
                create_at=current_time,
                merchant=shop,
                order_id=str(uuid.uuid4()),
                amount=amount,
                pay_type='card_2',
                pay_requisite=pay_requisite,
            )
            delay = datetime.timedelta(seconds=random.randint(50, 150))
            payment.status = get_status()
            payment.confirmed_user = operator
            payment.confirmed_time = current_time + delay
            payment.confirmed_amount = payment.amount
            payment.change_time = payment.create_at + delay
            payment.save()
        all_payment = Payment.objects.filter(merchant=shop).count()
        confirmed = Payment.objects.filter(merchant=shop, status=9).count()
        declined = Payment.objects.filter(merchant=shop, status=-1).count()
        print(all_payment, confirmed, declined)

        self.stdout.write(self.style.SUCCESS('Successfully generated data.'))