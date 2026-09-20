from django import forms

from .models import Practice


class PracticeForm(forms.ModelForm):
    class Meta:
        model = Practice
        fields = ['title', 'description', 'category', 'minutes', 'audience',
                  'audio_file', 'audio_url', 'order', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'audience': forms.Select(attrs={'class': 'form-select'}),
            'audio_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'audio_url': forms.URLInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
