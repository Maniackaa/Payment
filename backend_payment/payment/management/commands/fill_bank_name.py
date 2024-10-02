from django.core.management.base import BaseCommand, CommandError
from payment.models import Payment


class Command(BaseCommand):
    help = 'Fill empty bank'

    def handle(self, *args, **kwargs):
        try:
            empty_bank = Payment.objects.filter(bank__isnull=True)
            for i, payment in enumerate(empty_bank):
                print(i)
                bank = payment.get_bank()
                payment.bank = bank
                if bank:
                    payment.bank_str = bank.name
                payment.save()
            # Payment.objects.update(bank=None)


        except Exception as error:
            raise CommandError(error)

        self.stdout.write(self.style.SUCCESS('Successfully imported data.'))
