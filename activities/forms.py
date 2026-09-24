from django import forms

from .models import Activity


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ['title', 'description', 'kind', 'starts_at',
                  'duration_minutes', 'venue', 'audience', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'kind': forms.Select(attrs={'class': 'form-select'}),
            'starts_at': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 5}),
            'venue': forms.TextInput(attrs={'class': 'form-control',
                                            'placeholder': 'Blank = Online'}),
            'audience': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
