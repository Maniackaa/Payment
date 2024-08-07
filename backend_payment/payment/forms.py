import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from payment.models import Payment, CreditCard, Merchant, Withdraw
User = get_user_model()


class InvoiceForm(forms.ModelForm):
    amount = forms.CharField(widget=forms.HiddenInput())
    order_id = forms.CharField(widget=forms.HiddenInput())
    # screenshot = forms.ImageField(widget=forms.ClearableFileInput(), required=True, label='Скриншот об оплате')

    class Meta:
        model = Payment
        fields = (
                  'order_id',
                  'amount',
                  # 'phone',
                  # 'screenshot',
                  )


class M10ToM10Form(forms.ModelForm):
    amount = forms.CharField(widget=forms.HiddenInput())
    payment_id = forms.CharField(widget=forms.HiddenInput())
    phone = forms.CharField(label='Phone (+994)',
                                  widget=forms.TextInput(attrs={'placeholder': 'xx xxx xx xx',
                                                                'minlength': 9,
                                                                'maxlength': 12,
                                                                'size': 12
                                                                }))

    class Meta:
        model = Payment
        fields = (
                  'payment_id',
                  'amount',
                  )

    def clean_phone(self):
        data = self.cleaned_data["phone"]
        phone = ''.join([x for x in data if x.isdigit() or x in ['+']])
        # if phone.startswith('0') and len(phone) == 10:
        #     phone = '+994' + phone[1:]
        print(phone)
        if len(phone) == 9:
            phone = '+994' + phone
        if not phone.startswith('+994'):
            raise ValidationError('Bad format number')
        if len(phone) != 13:
            raise ValidationError('Bad number')  # Неверное количество символов в номере карты
        return phone



class InvoiceTestForm(forms.ModelForm):
    amount = forms.CharField(widget=forms.TextInput(attrs={'placeholder': '₼',}), required=False)
    owner_name = forms.CharField(label='owner_name',
                                 widget=forms.TextInput(), required=False)

    user_login = forms.CharField(label='user_login',
                                 widget=forms.TextInput(), required=False)
    merchant_id = forms.CharField(initial='2', required=True)
    order_id = forms.CharField(required=True)

    class Meta:
        model = Payment
        fields = ('amount', 'owner_name', 'user_login', 'pay_type')


class InvoiceM10Form(forms.ModelForm):
    payment_id = forms.CharField(widget=forms.HiddenInput())
    amount = forms.CharField(widget=forms.TextInput(attrs={'placeholder': '₼',
                                                           }
                                                         ))
    owner_name = forms.CharField(label='owner_name',
                                 widget=forms.TextInput(), required=False)
    card_number = forms.CharField(label='card_number',
                                  widget=forms.TextInput(attrs={'placeholder': '0000 0000 0000 0000',
                                                                'minlength': 16,
                                                                'maxlength': 19,
                                                                }
                                                         )
                                  )
    months = ((1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10), (11, 11), (12, 12), )
    expired_month = forms.CharField(label='expired_month',
                                    widget=forms.TextInput(attrs={'placeholder': 'MM',
                                                                  'minlength': 2,
                                                                  'maxlength': 2,
                                                                  }
                                                           )
                                    )
    expired_year = forms.CharField(label='expired_year',
                                   widget=forms.TextInput(attrs={'placeholder': 'YY',
                                                                 'minlength': 2,
                                                                 'maxlength': 2,
                                                                 }
                                                          )
                                   )
    cvv = forms.CharField(label='cvv',
                          widget=forms.PasswordInput(render_value=True, attrs={
                                       'placeholder': '***',
                                       'minlength': 3,
                                       'maxlength': 4,
                                   }))
    sms_code = forms.CharField(label='sms_code', required=False,
                               widget=forms.TextInput(attrs={'minlength': 4,
                                                             'maxlength': 6})
                               )

    class Meta:
        model = Payment
        fields = ('payment_id', 'owner_name', 'card_number', 'expired_month', 'expired_year', 'cvv', 'sms_code')

    def clean_card_number(self):
        data = self.cleaned_data["card_number"]
        card_number = ''.join([x for x in data if x.isdigit()])
        if len(card_number) != 16:
            raise ValidationError('Kart nömrəsindəki simvolların sayı səhvdir')  # Неверное количество символов в номере карты
        return card_number

    def clean_expired_month(self):
        data = self.cleaned_data["expired_month"]
        try:
            month = int(data)
            if 1 <= month <= 12:
                return data
            else:
                raise ValidationError('Qeyd etdiyiniz ay yalnışdır')  # Неверный месяц
        except Exception:
            raise ValidationError('Qeyd etdiyiniz ay yalnışdır')

    def clean_expired_year(self):
        data = self.cleaned_data["expired_year"]
        min_year = 20
        max_year = 40
        try:
            year = int(data)
            if min_year <= year <= max_year:
                return data
            else:
                raise ValidationError(f'Year must be {min_year}-{max_year}')  # Неверный месяц
        except Exception:
            raise ValidationError(f'Year must be {min_year}-{max_year}')


class InvoiceM10SmsForm(forms.ModelForm):

    sms_code = forms.CharField(label='sms_code', required=True,
                               widget=forms.TextInput(attrs={'minlength': 4,
                                                             'maxlength': 6})
                               )
    class Meta:
        model = Payment
        fields = ('sms_code',)


class PaymentListConfirmForm(forms.ModelForm):
    # confirmed_incoming = forms.CharField(required=False)

    class Meta:
        model = Payment
        fields = (
            'confirmed_amount',
            'confirmed_incoming'
        )


class MerchantForm(forms.ModelForm):
    name = forms.CharField(label='235')

    class Meta:
        model = Merchant
        fields = ('name', 'host', 'host_withdraw', 'pay_success_endpoint',
                  'secret', 'check_balance', 'white_ip')


class MerchBalanceChangeForm(forms.ModelForm):
    balance_delta = forms.DecimalField()
    comment = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ('balance_delta', 'comment')

    def clean(self):
        cleaned_data = super().clean()
        balance = self.instance.balance
        print(cleaned_data)
        print(balance)
        balance_delta = cleaned_data.get('balance_delta')
        if balance_delta < 0 and balance < -balance_delta:
            raise ValidationError(f'Недостаточно средств: {balance}')
        return self.cleaned_data


class PaymentForm(forms.ModelForm):
    comment = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = Payment
        fields = ('confirmed_amount', 'comment', 'status')


class WithdrawForm(forms.ModelForm):
    comment = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = Withdraw
        fields = ('comment', 'status')


class MyDateInput(forms.DateInput):
    input_type = 'date'
    format = '%Y-%m-%d'


class DateFilterForm(forms.Form):
    begin = forms.DateField(label='От', required=True,
                           widget=MyDateInput({
                               'class': 'form-control'
                           }))
    end = forms.DateField(label='До', required=True,
                           widget=MyDateInput({
                               'class': 'form-control'
                           }))