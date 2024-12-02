from django import forms

from deposit.models import Incoming
from payment.models import Payment


class IncomingForm(forms.ModelForm):

    comment = forms.CharField(widget=forms.Textarea, required=False)
    # confirmed_payment = forms.ModelChoiceField(queryset=Payment.objects.exclude(status__in=[-1, 9]), required=False)
    confirmed_payment = forms.CharField(required=False)

    def clean_confirmed_payment(self, *args):
        print(self.data)
        print(self.cleaned_data)
        print(self.instance)
        return self.data['confirmed_payment'].strip() or None

    class Meta:
        model = Incoming
        fields = ('confirmed_payment', 'comment',)
