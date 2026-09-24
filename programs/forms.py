import json

from django import forms

from .models import AccommodationTier, CostLineItem, Program


class ProgramForm(forms.ModelForm):
    """Author a program. `form_schema` is edited as JSON in a textarea."""

    form_schema_text = forms.CharField(
        required=False,
        label='Registration form fields (JSON)',
        help_text=(
            'A list of extra fields the app shows at registration, e.g. '
            '[{"name": "emergency_contact", "label": "Emergency contact", '
            '"type": "text", "required": true}]. Types: text, number, email, textarea.'
        ),
        widget=forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 5}),
    )

    class Meta:
        model = Program
        fields = [
            'title', 'year', 'description', 'audience', 'starts_on', 'ends_on',
            'venue', 'location', 'image', 'registration_opens_at',
            'registration_closes_at', 'capacity', 'requires_payment',
            'currency', 'is_published',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'audience': forms.Select(attrs={'class': 'form-select'}),
            'starts_on': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'ends_on': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'venue': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'registration_opens_at': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'registration_closes_at': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'requires_payment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'currency': forms.TextInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.is_bound:
            self.fields['form_schema_text'].initial = json.dumps(
                self.instance.form_schema, indent=2) if self.instance.form_schema else ''

    def clean_form_schema_text(self):
        raw = (self.cleaned_data.get('form_schema_text') or '').strip()
        if not raw:
            return []
        try:
            schema = json.loads(raw)
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f'Invalid JSON: {e.msg} (line {e.lineno}).')
        if not isinstance(schema, list):
            raise forms.ValidationError('The schema must be a JSON list of fields.')
        for i, field in enumerate(schema, 1):
            if not isinstance(field, dict) or 'name' not in field or 'label' not in field:
                raise forms.ValidationError(
                    f'Field {i} must be an object with at least "name" and "label".')
        return schema

    def save(self, commit=True):
        self.instance.form_schema = self.cleaned_data.get('form_schema_text') or []
        return super().save(commit)


class TierForm(forms.ModelForm):
    class Meta:
        model = AccommodationTier
        fields = ['name', 'description', 'price_per_person', 'total_rooms', 'is_active', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'price_per_person': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_rooms': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


class CostItemForm(forms.ModelForm):
    class Meta:
        model = CostLineItem
        fields = ['label', 'amount', 'unit', 'is_active', 'order']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
