from django import forms

from deposit.models import Incoming


class IncomingForm(forms.ModelForm):

    comment = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = Incoming
        fields = ('confirmed_payment', 'comment',)
