from django import forms

from deposit.models import Incoming
from payment.models import Payment


class IncomingForm(forms.ModelForm):

    comment = forms.CharField(widget=forms.Textarea, required=False)
    confirmed_payment = forms.ModelChoiceField(queryset=Payment.objects.exclude(status__in=[-1, 9]), required=False)

    class Meta:
        model = Incoming
        fields = ('confirmed_payment', 'comment',)
