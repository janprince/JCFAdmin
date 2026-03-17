from django import forms
from .models import Contact


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = [
            'full_name', 'gender', 'date_of_birth', 'phone', 'telephone',
            'email', 'profession', 'religion', 'residence', 'hometown',
            'country', 'father_name', 'mother_name', 'referral',
            'is_member', 'is_student', 'is_active',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+233...'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Telephone (optional)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email (optional)'}),
            'profession': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Profession'}),
            'religion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Religion'}),
            'residence': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Residence'}),
            'hometown': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Hometown'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Father's Name"}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Mother's Name"}),
            'referral': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Referred by'}),
            'is_member': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_student': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
