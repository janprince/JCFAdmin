from django import forms
from django.utils import timezone

from .services import add_months, end_of_day

CURRENCY_CHOICES = [
    ('GHS', 'GHS'),
    ('USD', 'USD'),
    ('GBP', 'GBP'),
    ('EUR', 'EUR'),
]

DURATION_CHOICES = [
    ('lifetime', 'Lifetime — no expiry'),
    ('12', '12 months'),
    ('6', '6 months'),
    ('3', '3 months'),
    ('1', '1 month'),
    ('custom', 'Custom date…'),
]


class AccessForm(forms.Form):
    """Shared fields for granting and extending access at the office desk."""

    duration = forms.ChoiceField(
        choices=DURATION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'data-duration-select': ''}),
    )
    custom_expires_at = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Expires on',
    )
    amount = forms.DecimalField(
        required=False, min_value=0, decimal_places=2, max_digits=12,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
        label='Amount paid',
        help_text='Leave blank if no money changed hands.',
    )
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES, initial='GHS', required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    receipt_ref = forms.CharField(
        required=False, max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Receipt or invoice number'}),
        label='Receipt no.',
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                     'placeholder': 'Anything worth remembering about this payment'}),
    )

    def clean(self):
        cleaned = super().clean()
        duration = cleaned.get('duration')
        custom = cleaned.get('custom_expires_at')

        if duration == 'custom':
            if not custom:
                self.add_error('custom_expires_at', 'Pick the date access should end.')
            elif custom <= timezone.localdate():
                self.add_error('custom_expires_at', 'That date has already passed.')

        if cleaned.get('amount') and not cleaned.get('currency'):
            cleaned['currency'] = 'GHS'
        return cleaned

    @property
    def months(self):
        """Number of months chosen, or None for lifetime/custom."""
        duration = self.cleaned_data['duration']
        return int(duration) if duration.isdigit() else None

    def expires_at(self, base=None):
        """Resolve the form into an expiry datetime — None means lifetime."""
        duration = self.cleaned_data['duration']
        if duration == 'lifetime':
            return None
        if duration == 'custom':
            return end_of_day(self.cleaned_data['custom_expires_at'])
        return add_months(base or timezone.now(), int(duration))


class RevokeForm(forms.Form):
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                     'placeholder': 'Why is access being removed?'}),
        label='Reason',
    )
