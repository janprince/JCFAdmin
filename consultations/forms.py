from django import forms
from .models import Consultation
from members.models import Contact


class ConsultationForm(forms.ModelForm):
    contact = forms.ModelChoiceField(
        queryset=Contact.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Contact',
    )

    class Meta:
        model = Consultation
        fields = ['contact', 'mode', 'scheduled_date']
        widgets = {
            'mode': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
