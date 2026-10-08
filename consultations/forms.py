from datetime import date

from django import forms
from .models import Consultation, ConsultationRequest
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


# The faiths people name most often, as they would write them. Stored as the
# label itself, so contact records read as plain words. "Other" asks for it.
RELIGIONS = ['Christianity', 'Islam', 'African Traditional Religion', 'Hinduism', 'Buddhism', 'Judaism',
             'Bahá’í Faith', 'Spiritual but not religious', 'No religion', 'Prefer not to say']
OTHER_RELIGION = 'Other'


class BookingRequestForm(forms.ModelForm):
    """The public booking form. Plain questions, in the order the office asked them on WhatsApp."""
    dob_unknown = forms.BooleanField(required=False, label='I don’t know my exact date of birth')
    religion = forms.ChoiceField(choices=[('', 'Choose one')] + [(r, r) for r in RELIGIONS] + [(OTHER_RELIGION, 'Other…')],
                                 label='Religion')
    religion_other = forms.CharField(required=False, max_length=100, label='Your religion')
    # Left empty by people; filled by bots that complete every field.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}))

    class Meta:
        model = ConsultationRequest
        fields = ['full_name', 'date_of_birth', 'day_of_birth', 'profession', 'hometown', 'religion', 'phone',
                  'email', 'residence', 'heard_from', 'heard_detail', 'preferred_mode', 'note']
        labels = {
            'full_name': 'Full name', 'date_of_birth': 'Date of birth', 'day_of_birth': 'Day of the week you were born',
            'hometown': 'Home town / region', 'phone': 'Phone number (WhatsApp if you have it)',
            'email': 'Email', 'residence': 'Where you live now', 'heard_from': 'How did you hear about Dr. Jan?',
            'heard_detail': 'Who or where, if you’d like to say', 'preferred_mode': 'How would you like to meet?',
            'note': 'Anything you’d like the office to know',
        }
        help_texts = {
            'full_name': 'As you would like Dr. Jan to address you.',
            'hometown': 'For example, Kumasi, Ashanti Region.',
            'residence': 'Town or area, for example East Legon, Accra.',
            'phone': 'The office will contact you on this number to arrange a date.',
        }
        widgets = {
            'full_name': forms.TextInput(attrs={'autocomplete': 'name'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'phone': forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel', 'inputmode': 'tel', 'placeholder': '024 123 4567'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'preferred_mode': forms.RadioSelect,
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('profession', 'hometown', 'residence'):
            self.fields[name].required = True
        self.fields['heard_from'].required = False
        self.fields['date_of_birth'].required = False
        self.fields['day_of_birth'].choices = [('', 'Choose a day')] + list(Contact.Weekday.choices)
        self.fields['heard_from'].choices = [('', 'Choose one, if you like')] + list(ConsultationRequest.Heard.choices)
        self.fields['preferred_mode'].choices = list(ConsultationRequest.Preference.choices) + [('', 'Either is fine')]
        self.fields['preferred_mode'].required = False
        self.fields['date_of_birth'].widget.attrs['max'] = date.today().isoformat()
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.RadioSelect, forms.CheckboxInput)):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        data = super().clean()
        born, day = data.get('date_of_birth'), data.get('day_of_birth')
        if data.get('dob_unknown'):
            data['date_of_birth'] = None
            if not day:
                self.add_error('day_of_birth', 'Choose the day of the week you were born, if you know it.')
        elif not born:
            self.add_error('date_of_birth', 'Enter your date of birth, or tick “I don’t know my exact date of birth”.')
        elif born > date.today() or born.year < 1900:
            self.add_error('date_of_birth', 'Check the year — this date doesn’t look right.')
        if data.get('religion') == OTHER_RELIGION:
            other = ' '.join((data.get('religion_other') or '').split())
            if other:
                data['religion'] = other
            else:
                self.add_error('religion_other', 'Tell us your religion, or choose one from the list.')
        return data
