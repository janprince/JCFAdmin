from django import forms
from .models import Worker, Representative
from members.models import Contact


class WorkerForm(forms.ModelForm):
    contact = forms.ModelChoiceField(
        queryset=Contact.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Worker
        fields = ['contact', 'role', 'duties', 'salary']
        widgets = {
            'role': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Role / Position'}),
            'duties': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Duties'}),
            'salary': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
        }


class RepresentativeForm(forms.ModelForm):
    contact = forms.ModelChoiceField(
        queryset=Contact.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Representative
        fields = ['contact', 'country', 'region']
        widgets = {
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'}),
            'region': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Region'}),
        }
