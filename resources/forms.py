from django import forms

from accounts.forms import style_fields
from .models import DigitalResource


class DigitalResourceForm(forms.ModelForm):
    class Meta:
        model = DigitalResource
        fields = ['title', 'url', 'category', 'audience', 'language', 'description', 'share_privately', 'position', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Intermediate Lessons (Twi)'}),
            'url': forms.URLInput(attrs={'placeholder': 'www.vimeo.com/showcase/…'}),
            'language': forms.TextInput(attrs={'list': 'resource-languages'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class NewResourceForm(DigitalResourceForm):
    """The add modal: new links are shown, in default order, until edited."""
    class Meta(DigitalResourceForm.Meta):
        fields = [f for f in DigitalResourceForm.Meta.fields if f not in ('position', 'is_active')]
