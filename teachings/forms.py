from django import forms
from .models import Teaching


class TeachingForm(forms.ModelForm):
    class Meta:
        model = Teaching
        fields = ['topic', 'format', 'language', 'status', 'description']
        widgets = {
            'topic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Topic Title'}),
            'format': forms.Select(attrs={'class': 'form-select'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
        }
