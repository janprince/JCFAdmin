from django import forms
from .models import Centre


class CentreForm(forms.ModelForm):
    class Meta:
        model = Centre
        fields = [
            'name', 'location', 'address', 'country', 'image',
            'description', 'leader_name', 'leader_title', 'leader_avatar',
            'contact_email', 'contact_phone', 'latitude', 'longitude',
            'member_count', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Centre Name'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City, e.g. Accra'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Address'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Description'}),
            'leader_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leader Name'}),
            'leader_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Centre Director'}),
            'leader_avatar': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@example.com'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+233...'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': 'e.g. 5.614818'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': 'e.g. -0.205874'}),
            'member_count': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
