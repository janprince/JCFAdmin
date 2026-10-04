from django import forms
from django.utils import timezone
from phonenumber_field.formfields import PhoneNumberField

from accounts.forms import style_fields
from accounts.models import Profile
from members.models import Contact
from .models import ROLE_ORDER, ServiceEntry, ServiceUnit, Worker

CURRENCIES = [('GHS', 'GHS'), ('USD', 'USD'), ('GBP', 'GBP'), ('EUR', 'EUR')]


class WorkerForm(forms.ModelForm):
    """Service member editor. On create it also finds or adds the person's contact record."""
    person = forms.ChoiceField(choices=[('existing', 'Already in our contacts'), ('new', 'New to our records')],
                               initial='existing', widget=forms.RadioSelect, required=False)
    contact = forms.ModelChoiceField(queryset=Contact.objects.none(), required=False, label='Contact')
    new_name = forms.CharField(label='Full name', max_length=255, required=False)
    new_phone = PhoneNumberField(label='Phone', required=False)
    new_email = forms.EmailField(label='Email', required=False)
    receives_allowance = forms.BooleanField(label='Receives a monthly allowance', required=False)
    allowance_currency = forms.ChoiceField(choices=CURRENCIES, label='Currency')

    class Meta:
        model = Worker
        fields = ['title', 'service_type', 'status', 'unit', 'other_units', 'started_on', 'ended_on', 'duties',
                  'availability', 'skills', 'allowance', 'allowance_currency', 'emergency_name', 'emergency_phone', 'notes']
        labels = {
            'service_type': 'Commitment', 'unit': 'Main service unit', 'other_units': 'Also serves in',
            'started_on': 'Began service', 'ended_on': 'Service ended', 'duties': 'Responsibilities',
            'skills': 'Gifts & skills', 'allowance': 'Monthly amount', 'emergency_name': 'Emergency contact',
            'emergency_phone': 'Emergency phone', 'notes': 'Private notes',
        }
        help_texts = {
            'title': 'What they do, in a few words — e.g. Videographer, Farm hand, Office secretary.',
            'availability': 'When they usually serve — e.g. Weekdays, Saturday mornings.',
            'skills': 'Separate with commas. Helps the office find the right person for a task.',
            'notes': 'Seen only by those who manage the service team.',
            'other_units': 'Choose any other units they regularly help.',
        }
        widgets = {
            'service_type': forms.RadioSelect,
            'other_units': forms.CheckboxSelectMultiple,
            'started_on': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'ended_on': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'duties': forms.Textarea(attrs={'rows': 4, 'placeholder': 'What they look after, and who they work with.'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'allowance': forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'placeholder': '0.00', 'inputmode': 'decimal'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        units = ServiceUnit.objects.all()
        if self.instance.pk:
            # Keep an archived unit selectable for the people still in it.
            active = units.filter(is_active=True) | units.filter(pk=self.instance.unit_id) | units.filter(pk__in=self.instance.other_units.all())
            units = active.distinct()
            for name in ('person', 'contact', 'new_name', 'new_phone', 'new_email'):
                del self.fields[name]
        else:
            units = units.filter(is_active=True)
            self.fields['contact'].queryset = Contact.objects.filter(worker__isnull=True).order_by('full_name')
            self.fields['contact'].empty_label = 'Choose a contact'
            if not self.fields['contact'].queryset.exists():
                self.fields['person'].initial = 'new'
            self.fields['started_on'].required = True
            self.fields['started_on'].initial = timezone.localdate()
        self.fields['unit'].queryset = units.order_by('name')
        self.fields['unit'].empty_label = 'Choose a unit'
        self.fields['unit'].required = True
        self.fields['other_units'].queryset = units.order_by('name')
        self.fields['receives_allowance'].initial = self.instance.receives_allowance
        self.fields['service_type'].required = True
        style_fields(self)
        # Radios are drawn one by one in the template; the checkbox list is
        # styled as chips by .jcf-checks, which expects no widget class.
        for name in ('service_type', 'person'):
            if name in self.fields:
                self.fields[name].widget.attrs['class'] = 'form-check-input'
        self.fields['other_units'].widget.attrs.pop('class', None)

    def clean(self):
        data = super().clean()
        if not self.instance.pk:
            self._clean_person(data)
        if data.get('receives_allowance'):
            if not data.get('allowance') or data['allowance'] <= 0:
                self.add_error('allowance', 'Enter the monthly amount, or switch off the allowance.')
        else:
            data['allowance'] = None
        if data.get('status') == Worker.Status.INACTIVE:
            data['ended_on'] = data.get('ended_on') or timezone.localdate()
        else:
            data['ended_on'] = None
        started, ended = data.get('started_on'), data.get('ended_on')
        if started and ended and ended < started:
            self.add_error('ended_on', 'Service cannot end before it began.')
        if started and started > timezone.localdate():
            self.add_error('started_on', 'Choose today or an earlier date.')
        if data.get('unit') and data.get('other_units') is not None:
            data['other_units'] = [u for u in data['other_units'] if u != data['unit']]
        return data

    def _clean_person(self, data):
        if data.get('person') == 'new':
            name, phone = (data.get('new_name') or '').strip(), data.get('new_phone')
            if not name:
                self.add_error('new_name', 'Enter their full name.')
            if not phone:
                self.add_error('new_phone', 'Enter a phone number so the office can reach them.')
            if name and phone:
                existing = Contact.objects.filter(full_name__iexact=name, phone=phone).first()
                if existing:
                    self.add_error('new_name', 'This person is already in our contacts. Choose “Already in our contacts” and pick them from the list.')
        elif not data.get('contact'):
            self.add_error('contact', 'Choose who is joining the service team.')

    def save(self, commit=True):
        worker = super().save(commit=False)
        if not worker.pk:
            data = self.cleaned_data
            if data.get('person') == 'new':
                worker.contact = Contact.objects.create(full_name=data['new_name'].strip(), phone=data['new_phone'],
                                                        email=data.get('new_email') or '')
            else:
                worker.contact = data['contact']
        if commit:
            worker.save()
            self.save_m2m()
        return worker


class ServiceUnitForm(forms.ModelForm):
    """`portal_roles` is shown only to people who manage portal accounts."""
    portal_roles = forms.MultipleChoiceField(
        choices=[(role, label) for role in ROLE_ORDER for value, label in Profile.Role.choices if value == role],
        required=False, widget=forms.CheckboxSelectMultiple, label='Portal roles this unit may hold',
        help_text='Accounts linked to a member of this unit can only be given these roles. Leave all unticked if the unit’s work happens outside the portal.')

    class Meta:
        model = ServiceUnit
        fields = ['name', 'description', 'icon', 'lead', 'portal_roles', 'is_active']
        labels = {'lead': 'Unit lead', 'is_active': 'Unit is active'}
        help_texts = {'is_active': 'Archived units stay on past records but cannot be chosen for new members.'}

    def __init__(self, *args, can_set_roles=False, **kwargs):
        super().__init__(*args, **kwargs)
        leads = Worker.objects.exclude(status=Worker.Status.INACTIVE).select_related('contact').order_by('contact__full_name')
        self.fields['lead'].queryset = leads
        self.fields['lead'].empty_label = 'No lead named'
        if not can_set_roles:
            del self.fields['portal_roles']
        style_fields(self)
        if 'portal_roles' in self.fields:
            self.fields['portal_roles'].widget.attrs.pop('class', None)


class ServiceEntryForm(forms.ModelForm):
    class Meta:
        model = ServiceEntry
        fields = ['kind', 'occurred_on', 'text']
        labels = {'kind': 'What kind of moment', 'occurred_on': 'Date', 'text': 'What happened'}
        widgets = {
            'occurred_on': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'text': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. Led the recording of the Easter retreat teachings.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Changes are written by the system when a record is edited.
        self.fields['kind'].choices = [c for c in ServiceEntry.Kind.choices if c[0] != ServiceEntry.Kind.CHANGE]
        self.fields['kind'].initial = ServiceEntry.Kind.APPRECIATION
        style_fields(self)

    def clean_occurred_on(self):
        value = self.cleaned_data['occurred_on']
        if value > timezone.localdate():
            raise forms.ValidationError('Record moments that have already happened.')
        return value
