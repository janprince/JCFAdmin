from django import forms
from .models import Cause, Donation, CauseCategory


class CauseCategoryForm(forms.ModelForm):
    class Meta:
        model = CauseCategory
        fields = ['name', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category name'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'category-slug'}),
        }


class CauseForm(forms.ModelForm):
    class Meta:
        model = Cause
        fields = [
            'title', 'slug', 'description', 'content', 'image', 'gallery',
            'type', 'goal_amount', 'currency', 'impact_statement',
            'category', 'is_active',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cause title'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'cause-slug'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Short summary for listing cards'}),
            'content': forms.HiddenInput(),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'gallery': forms.HiddenInput(),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'goal_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'currency': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'GHS'}),
            'impact_statement': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Reaching seekers across the world'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DonationForm(forms.ModelForm):
    donated_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
    )
    amount = forms.DecimalField(
        max_digits=12, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
    )

    class Meta:
        model = Donation
        fields = [
            'cause', 'donor_name', 'donor_email', 'donor_phone', 'amount',
            'currency', 'method', 'status', 'reference', 'paystack_reference',
            'notes', 'is_anonymous', 'donated_at',
        ]
        widgets = {
            'cause': forms.Select(attrs={'class': 'form-select'}),
            'donor_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Donor full name'}),
            'donor_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'donor_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+233...'}),
            'currency': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'GHS'}),
            'method': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bank/MoMo reference'}),
            'paystack_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Paystack ref'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Additional notes'}),
            'is_anonymous': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
