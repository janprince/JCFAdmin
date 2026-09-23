"""Presentation helpers shared by every admin template.

Registered as a template builtin in `config/settings.py`, so templates use
these without `{% load %}`.

Everything here is display-only: names and phone numbers are tidied on the way
out, never rewritten in the database.
"""
import zlib

from django import template
from django.utils.dateformat import format as dateformat
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()

# Must match the number of `.jcf-avatar--tone-N` rules in static/jcf/css/ui.css.
AVATAR_TONES = 6


def _squash(value):
    """Collapse runs of whitespace and trim — legacy imports are full of both."""
    return ' '.join(str(value or '').split())


def _initials(name):
    words = [w for w in name.split() if any(c.isalpha() for c in w)]
    if not words:
        return '?'
    ends = (words[0], words[-1]) if len(words) > 1 else (words[0],)
    return ''.join(next(c for c in w if c.isalpha()) for w in ends).upper()


@register.filter
def person_name(value):
    """Re-case names that were typed in ALL CAPS or all lower case.

    Mixed-case names are left alone, so a deliberate "McAdams" or "de Souza"
    survives; only the obviously unformatted ones are title-cased.
    """
    name = _squash(value)
    # Some legacy records hold an email in the name field; leave those as typed.
    if '@' not in name and (name.isupper() or name.islower()):
        return name.title()
    return name


@register.simple_tag
def avatar(name, size='sm', fallback=''):
    """Initials in a tinted circle: `{% avatar contact.full_name %}`.

    Two letters (first and last word) read as a person where one letter reads
    as a bullet. The tint is derived from the name, so the same person keeps
    the same colour on every page. `fallback` is used when the name is blank —
    pass an email for accounts that never set one.
    """
    source = _squash(name) or _squash(fallback)
    tone = zlib.crc32(source.lower().encode()) % AVATAR_TONES
    return format_html(
        '<span class="jcf-avatar jcf-avatar--{} jcf-avatar--tone-{}" aria-hidden="true">{}</span>',
        size, tone, _initials(source),
    )


@register.filter
def phone(value):
    """`+233542549699` → `+233 54 254 9699`. Unparseable input is shown as typed."""
    if not value:
        return ''
    is_valid = getattr(value, 'is_valid', None)
    if is_valid and is_valid():
        return value.as_international
    return str(value)


@register.filter
def or_dash(value):
    """A muted em dash for missing values, so blanks don't read as data."""
    if value is None or not str(value).strip():
        return mark_safe('<span class="jcf-empty" title="Not recorded">—</span>')
    return value


@register.filter
def as_switch(bound_field):
    """Render a checkbox with role="switch", so it's announced as a toggle."""
    return bound_field.as_widget(attrs={'role': 'switch'})


@register.simple_tag(takes_context=True)
def keep_params(context, *names):
    """Hidden inputs that carry the named GET parameters through a filter form.

    `{% keep_params 'status' %}` inside a search form keeps the current tab
    when the user searches.
    """
    request = context['request']
    return format_html_join(
        '', '<input type="hidden" name="{}" value="{}">',
        ((name, request.GET[name]) for name in names if request.GET.get(name)),
    )


@register.simple_tag
def date_range(start, end=None):
    """Say a span once: `16–17 May 2026`, `31 Jul – 9 Aug 2026`."""
    if not start:
        return ''
    if not end or end == start:
        return dateformat(start, 'j M Y')
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}–{dateformat(end, 'j M Y')}"
    if start.year == end.year:
        return f"{dateformat(start, 'j M')} – {dateformat(end, 'j M Y')}"
    return f"{dateformat(start, 'j M Y')} – {dateformat(end, 'j M Y')}"


@register.simple_tag
def page_window(page_obj):
    """Page numbers with gaps: 1 … 4 5 6 … 38, instead of all 38."""
    return page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)


@register.inclusion_tag('partials/_office_navigation.html', takes_context=True)
def office_navigation(context):
    from dashboard.navigation import navigation_for
    return {'groups': navigation_for(context['request'])}
