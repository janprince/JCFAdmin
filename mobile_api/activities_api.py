"""Mobile Upcoming Activities (designs 37–41).

A keyset-paginated browse over scheduled activities, with a week selector, a
calendar density view, primary and advanced filters, search, reminders,
saves and registration.

Two rules this module is built around:

* **Status is derived here, never in the app.** `registration.state`,
  `access.allowed`, `is_live_now` and the rest are strings the client
  renders; it does not recompute them from dates it may have skewed clocks
  for. `server_time` rides along so the app can show an honest countdown.
* **Destinations are identifiers, not routes.** An item says
  `{"type": "live", "event_id": 12}`; the app maps that to its own router.

Visibility is a ladder rather than a hard filter. A guest sees public
activities plus members-only ones marked locked (that lock is the reason to
sign in); a member additionally sees students-only ones locked; a student
sees everything open. Nothing a caller may not attend is ever hidden so
completely that the schedule looks empty, and nothing two tiers above them
is advertised.
"""
import base64
from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import (Activity, ActivityRegistration,
                               ActivityReminder, ActivitySave)
from programs.models import Program

from .authentication import IsMember, MobileTokenAuthentication

# How far ahead the unfiltered feed looks, and how soon before start a live
# session is flagged "starting soon".
FEED_WINDOW_DAYS = 120
STARTING_SOON_MINUTES = 60
# An activity stays in the feed while it runs, and lingers this long after.
GRACE_AFTER_END = timedelta(minutes=30)

DEFAULT_LIMIT = 20
MAX_LIMIT = 50

PRIMARY_FILTERS = ('all', 'live', 'online', 'in_person')


# --------------------------------------------------------------------------
# visibility
# --------------------------------------------------------------------------

def _audiences_for(contact):
    """Audiences a caller may *attend*. Used by the home screens, which
    advertise nothing the reader cannot walk into."""
    values = [Activity.Audience.PUBLIC]
    if contact is not None:
        if contact.is_member or contact.is_student:
            values.append(Activity.Audience.MEMBERS)
        if contact.is_student:
            values.append(Activity.Audience.STUDENTS)
    return values


def _visible_audiences(contact):
    """Audiences a caller may *see*, including the tier above them."""
    if contact is None:
        return [Activity.Audience.PUBLIC, Activity.Audience.MEMBERS]
    if contact.is_student:
        return [Activity.Audience.PUBLIC, Activity.Audience.MEMBERS,
                Activity.Audience.STUDENTS]
    if contact.is_member:
        return [Activity.Audience.PUBLIC, Activity.Audience.MEMBERS,
                Activity.Audience.STUDENTS]
    return [Activity.Audience.PUBLIC, Activity.Audience.MEMBERS]


def _may_attend(activity, contact):
    if activity.audience == Activity.Audience.PUBLIC:
        return True
    if contact is None:
        return False
    if activity.audience == Activity.Audience.MEMBERS:
        return contact.is_member or contact.is_student
    return contact.is_student


def _access_json(activity, contact):
    allowed = _may_attend(activity, contact)
    if allowed:
        reason = ''
    elif contact is None:
        reason = 'sign_in'
    elif activity.audience == Activity.Audience.STUDENTS:
        reason = 'students_only'
    else:
        reason = 'members_only'
    return {
        'allowed': allowed,
        'required_audience': activity.audience,
        'sign_in_required': not allowed and contact is None,
        'reason': reason,
    }


# --------------------------------------------------------------------------
# compact home-card shape
#
# The member and student home screens show a single "Live & upcoming" card
# and read a deliberately smaller payload than the browse list. Keeping it
# here means both screens agree on what "live soon" means.
# --------------------------------------------------------------------------

def _activity_json(activity, now, reminded_ids):
    delta = activity.starts_at - now
    live_soon = (
        activity.kind == Activity.Kind.LIVE
        and delta <= timedelta(minutes=STARTING_SOON_MINUTES)
    )
    return {
        'kind': activity.kind,
        'activity_id': activity.id,
        'program_slug': None,
        'title': activity.title,
        'description': activity.description,
        'starts_at': activity.starts_at.isoformat(),
        'all_day': activity.all_day,
        'duration_minutes': activity.duration_minutes,
        'venue': activity.venue,
        'audience': activity.audience,
        'live_soon': live_soon,
        'reminder_set': activity.id in reminded_ids,
    }


def _program_json(program, reminded_slugs):
    return {
        'kind': 'programme',
        'activity_id': None,
        'program_slug': program.slug,
        'title': program.title,
        'description': program.description,
        # Programmes carry a date, not a time — midnight local, all_day.
        'starts_at': program.starts_on.isoformat(),
        'all_day': True,
        'duration_minutes': None,
        'venue': program.venue or program.location,
        'audience': program.audience,
        'live_soon': False,
        'reminder_set': program.slug in reminded_slugs,
    }


# --------------------------------------------------------------------------
# cursor
# --------------------------------------------------------------------------

def encode_cursor(activity):
    raw = f'{activity.starts_at.isoformat()}|{activity.id}'
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip('=')


def decode_cursor(value):
    """-> (starts_at, id), or None when the cursor is unusable.

    A bad cursor is not an error: the client gets page one rather than a
    dead end it cannot recover from without clearing its state.
    """
    if not value:
        return None
    try:
        padded = value + '=' * (-len(value) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        stamp, _, ident = raw.rpartition('|')
        return datetime.fromisoformat(stamp), int(ident)
    except (ValueError, TypeError, UnicodeDecodeError):
        return None


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------

def _facilitator_json(activity):
    worker = activity.facilitator
    name = activity.facilitator_name or (
        worker.contact.full_name if worker else '')
    if not name:
        return None
    portrait = ''
    session = getattr(activity, 'live_session', None)
    if session is not None and session.facilitator_portrait:
        portrait = session.facilitator_portrait.url
    return {
        'display_name': name,
        'role': worker.role if worker else '',
        # Only an approved portrait is sent; without one the app draws
        # initials rather than attaching a stock face to a real person.
        'avatar_url': portrait,
        'verified': worker is not None,
    }


def _location_line(activity):
    if activity.activity_format == Activity.Format.ONLINE:
        return activity.online_platform or 'Online'
    parts = [p for p in (activity.venue, activity.city) if p]
    line = ', '.join(parts)
    if activity.activity_format == Activity.Format.HYBRID:
        platform = activity.online_platform or 'Online'
        return f'{line} + {platform}' if line else platform
    return line


def _fee_json(activity):
    if activity.is_free:
        return {'free': True, 'amount': None, 'currency': '', 'display': ''}
    amount = activity.fee_amount
    currency = activity.fee_currency or 'GHS'
    # Whole amounts read better without the trailing zeros on a card.
    text = (f'{amount:.0f}' if amount == amount.to_integral_value()
            else f'{amount:.2f}')
    return {
        'free': False,
        'amount': str(amount),
        'currency': currency,
        'display': f'{currency} {text}',
    }


def _registration_json(activity, now, my_status):
    return {
        'required': activity.registration_required,
        'state': activity.registration_state(now),
        'capacity': activity.capacity,
        'seats_left': activity.seats_left(),
        'opens_at': (activity.registration_opens_at.isoformat()
                     if activity.registration_opens_at else None),
        'closes_at': (activity.registration_closes_at.isoformat()
                      if activity.registration_closes_at else None),
        'waitlist_enabled': activity.waitlist_enabled,
        'external_url': activity.external_registration_url,
        'my_status': my_status,
    }


def _destination(activity):
    """A stable identifier the app maps to a route of its own choosing."""
    if activity.kind == Activity.Kind.LIVE and hasattr(
            activity, 'live_session'):
        return {'type': 'live', 'event_id': activity.id}
    return {'type': 'activity', 'event_id': activity.id}


def activity_json(activity, now, *, contact=None, reminded_ids=(),
                  saved_ids=(), registrations=None):
    registrations = registrations or {}
    ends_at = activity.ends_at
    return {
        'id': activity.id,
        'kind': activity.kind,
        'activity_type': activity.activity_type,
        'activity_type_label': activity.get_activity_type_display(),
        'title': activity.title,
        'summary': activity.description,
        'starts_at': activity.starts_at.isoformat(),
        'ends_at': ends_at.isoformat(),
        'all_day': activity.all_day,
        'duration_minutes': activity.duration_minutes,
        'format': activity.activity_format,
        'format_label': activity.get_activity_format_display(),
        'venue': activity.venue,
        'city': activity.city,
        'country': activity.country,
        'online_platform': activity.online_platform,
        'location_line': _location_line(activity),
        'facilitator': _facilitator_json(activity),
        'language': activity.language,
        'image_url': activity.image.url if activity.image else '',
        'image_key': activity.image_key,
        'audience': activity.audience,
        'access': _access_json(activity, contact),
        'registration': _registration_json(
            activity, now, registrations.get(activity.id)),
        'fee': _fee_json(activity),
        'reminder_set': activity.id in reminded_ids,
        'saved': activity.id in saved_ids,
        'cancelled': activity.cancelled,
        'rescheduled_note': activity.rescheduled_note,
        'is_live_now': (
            activity.kind == Activity.Kind.LIVE
            and not activity.cancelled
            and activity.starts_at <= now < ends_at),
        'starting_soon': (
            not activity.cancelled
            and now < activity.starts_at <= now + timedelta(
                minutes=STARTING_SOON_MINUTES)),
        'destination': _destination(activity),
    }


# --------------------------------------------------------------------------
# query building
# --------------------------------------------------------------------------

def _parse_date(value):
    try:
        return datetime.fromisoformat(value).date()
    except (TypeError, ValueError):
        return None


def _day_bounds(day):
    """Local midnight-to-midnight for a date, as aware datetimes.

    Grouping happens in the *viewer's* timezone, so an activity at 23:30
    does not slide into the next day the way a naive UTC cut would.
    """
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    return start, start + timedelta(days=1)


def _base_queryset(contact, now):
    return (Activity.objects
            .filter(is_active=True,
                    audience__in=_visible_audiences(contact))
            .select_related('facilitator__contact', 'live_session')
            .order_by('starts_at', 'id'))


def _apply_filters(qs, params, contact):
    primary = params.get('filter', 'all')
    if primary not in PRIMARY_FILTERS:
        primary = 'all'
    if primary == 'live':
        qs = qs.filter(kind=Activity.Kind.LIVE)
    elif primary == 'online':
        # Hybrid is genuinely both, so it answers to either chip.
        qs = qs.filter(activity_format__in=[
            Activity.Format.ONLINE, Activity.Format.HYBRID])
    elif primary == 'in_person':
        qs = qs.filter(activity_format__in=[
            Activity.Format.IN_PERSON, Activity.Format.HYBRID])

    types = [t for t in params.get('types', '').split(',') if t]
    if types:
        qs = qs.filter(activity_type__in=types)

    languages = [t for t in params.get('languages', '').split(',') if t]
    if languages:
        qs = qs.filter(language__in=languages)

    fee = params.get('fee')
    if fee == 'free':
        qs = qs.filter(Q(fee_amount__isnull=True) | Q(fee_amount__lte=0))
    elif fee == 'paid':
        qs = qs.filter(fee_amount__gt=0)

    if params.get('access') == 'open_to_me':
        if contact is None:
            qs = qs.filter(audience=Activity.Audience.PUBLIC)
        elif not contact.is_student:
            qs = qs.exclude(audience=Activity.Audience.STUDENTS)

    query = (params.get('q') or '').strip()
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(venue__icontains=query)
            | Q(city__icontains=query)
            | Q(facilitator_name__icontains=query)
            | Q(facilitator__contact__full_name__icontains=query))
    return qs, primary


class UpcomingActivitiesView(APIView):
    """GET /activities/upcoming/ — the browsable schedule, soonest first.

    Query: `from`/`to` (local dates), `filter` (all|live|online|in_person),
    `types`, `languages`, `fee` (free|paid), `access` (open_to_me), `q`,
    `cursor`, `limit`.
    """

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        token = getattr(request, 'auth', None)
        contact = token.contact if token is not None else None
        now = timezone.now()
        params = request.query_params

        qs = _base_queryset(contact, now)
        qs, primary = _apply_filters(qs, params, contact)

        from_date = _parse_date(params.get('from'))
        to_date = _parse_date(params.get('to'))
        if from_date:
            lower, _ = _day_bounds(from_date)
            # Never reach back past the grace floor: this screen is
            # *upcoming* activities, so a day that is already over reads as
            # empty rather than as a list of things that have finished.
            qs = qs.filter(starts_at__gte=max(lower, now - GRACE_AFTER_END))
        else:
            qs = qs.filter(starts_at__gte=now - GRACE_AFTER_END)
        if to_date:
            _, upper = _day_bounds(to_date)
            qs = qs.filter(starts_at__lt=upper)
        else:
            qs = qs.filter(starts_at__lte=now + timedelta(
                days=FEED_WINDOW_DAYS))

        # Filter facets are counted before pagination, over the same window.
        facets = self._facets(qs)

        cursor = decode_cursor(params.get('cursor'))
        if cursor is not None:
            stamp, ident = cursor
            qs = qs.filter(
                Q(starts_at__gt=stamp)
                | Q(starts_at=stamp, id__gt=ident))

        try:
            limit = min(int(params.get('limit', DEFAULT_LIMIT)), MAX_LIMIT)
        except (TypeError, ValueError):
            limit = DEFAULT_LIMIT
        limit = max(limit, 1)

        page = list(qs[:limit + 1])
        has_more = len(page) > limit
        page = page[:limit]

        reminded, saved, registrations = self._personal(contact, page)
        results = [
            activity_json(a, now, contact=contact, reminded_ids=reminded,
                          saved_ids=saved, registrations=registrations)
            for a in page
        ]

        payload = {
            'server_time': now.isoformat(),
            'timezone': str(timezone.get_current_timezone()),
            'applied_filter': primary,
            'results': results,
            'next_cursor': encode_cursor(page[-1]) if has_more and page
                           else None,
            'available_filters': facets,
        }
        # The banner belongs to the unfiltered, unpaged first view only:
        # a featured card floating above a filtered list is a lie about
        # what the filter matched.
        if cursor is None:
            payload['featured_activity'] = self._featured(
                contact, now, reminded, saved, registrations)
        else:
            payload['featured_activity'] = None
        return Response(payload)

    def _facets(self, qs):
        types, languages, formats = {}, {}, {}
        for activity_type, language, fmt in qs.values_list(
                'activity_type', 'language', 'activity_format'):
            types[activity_type] = types.get(activity_type, 0) + 1
            if language:
                languages[language] = languages.get(language, 0) + 1
            formats[fmt] = formats.get(fmt, 0) + 1
        labels = dict(Activity.ActivityType.choices)
        format_labels = dict(Activity.Format.choices)
        return {
            'types': [
                {'value': value, 'label': labels.get(value, value),
                 'count': count}
                for value, count in sorted(
                    types.items(), key=lambda kv: -kv[1])],
            'languages': [
                {'value': value, 'label': value, 'count': count}
                for value, count in sorted(
                    languages.items(), key=lambda kv: -kv[1])],
            'formats': [
                {'value': value, 'label': format_labels.get(value, value),
                 'count': count}
                for value, count in sorted(
                    formats.items(), key=lambda kv: -kv[1])],
        }

    def _personal(self, contact, activities):
        if contact is None or not activities:
            return set(), set(), {}
        ids = [a.id for a in activities]
        reminded = set(ActivityReminder.objects.filter(
            contact=contact, activity_id__in=ids)
            .values_list('activity_id', flat=True))
        saved = set(ActivitySave.objects.filter(
            contact=contact, activity_id__in=ids)
            .values_list('activity_id', flat=True))
        registrations = dict(ActivityRegistration.objects.filter(
            contact=contact, activity_id__in=ids)
            .values_list('activity_id', 'status'))
        return reminded, saved, registrations

    def _featured(self, contact, now, reminded, saved, registrations):
        """The server picks the banner: the soonest flagged activity the
        caller may actually attend. Nothing locked is ever featured."""
        candidates = (_base_queryset(contact, now)
                      .filter(is_featured=True, cancelled=False,
                              starts_at__gte=now - GRACE_AFTER_END))
        for activity in candidates[:5]:
            if _may_attend(activity, contact):
                payload = activity_json(
                    activity, now, contact=contact,
                    reminded_ids=reminded, saved_ids=saved,
                    registrations=registrations)
                payload['featured_blurb'] = activity.featured_blurb
                return payload
        return None


class ActivityCalendarView(APIView):
    """GET /activities/calendar/?month=YYYY-MM — one row per day that has
    something on it, so the calendar view can draw density dots without
    pulling every activity."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        token = getattr(request, 'auth', None)
        contact = token.contact if token is not None else None
        now = timezone.now()

        raw = request.query_params.get('month') or ''
        try:
            year, month = (int(part) for part in raw.split('-', 1))
            first = datetime(year, month, 1).date()
        except (TypeError, ValueError):
            first = timezone.localdate().replace(day=1)
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)

        qs, _ = _apply_filters(
            _base_queryset(contact, now), request.query_params, contact)
        lower, _ = _day_bounds(first)
        _, upper = _day_bounds(next_month - timedelta(days=1))
        qs = qs.filter(starts_at__gte=lower, starts_at__lt=upper)

        tz = timezone.get_current_timezone()
        days = {}
        for starts_at, kind, cancelled in qs.values_list(
                'starts_at', 'kind', 'cancelled'):
            key = starts_at.astimezone(tz).date().isoformat()
            entry = days.setdefault(
                key, {'date': key, 'count': 0, 'has_live': False})
            entry['count'] += 1
            if kind == Activity.Kind.LIVE and not cancelled:
                entry['has_live'] = True

        return Response({
            'month': f'{first.year:04d}-{first.month:02d}',
            'server_time': now.isoformat(),
            'timezone': str(tz),
            'days': [days[key] for key in sorted(days)],
        })


class ActivityDetailView(APIView):
    """GET /activities/<pk>/ — one activity, same shape as a list row."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, pk):
        token = getattr(request, 'auth', None)
        contact = token.contact if token is not None else None
        now = timezone.now()
        activity = _base_queryset(contact, now).filter(pk=pk).first()
        if activity is None:
            return Response({'detail': 'Activity not found.'}, status=404)
        reminded, saved, registrations = (set(), set(), {})
        if contact is not None:
            reminded = set(ActivityReminder.objects.filter(
                contact=contact, activity=activity)
                .values_list('activity_id', flat=True))
            saved = set(ActivitySave.objects.filter(
                contact=contact, activity=activity)
                .values_list('activity_id', flat=True))
            registrations = dict(ActivityRegistration.objects.filter(
                contact=contact, activity=activity)
                .values_list('activity_id', 'status'))
        payload = activity_json(
            activity, now, contact=contact, reminded_ids=reminded,
            saved_ids=saved, registrations=registrations)
        payload['server_time'] = now.isoformat()
        return Response(payload)


class ReminderToggleView(APIView):
    """POST /activities/reminder/ {activity_id | program_slug} — toggle a
    "remind me". Stored server-side; push delivery lands with FCM."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]

    def post(self, request):
        contact = request.member
        activity_id = request.data.get('activity_id')
        program_slug = request.data.get('program_slug')

        if activity_id:
            activity = Activity.objects.filter(
                pk=activity_id, is_active=True).first()
            if activity is None:
                return Response({'detail': 'Activity not found.'}, status=404)
            existing = ActivityReminder.objects.filter(
                contact=contact, activity=activity)
            if existing.exists():
                existing.delete()
                return Response({'reminder_set': False})
            ActivityReminder.objects.create(contact=contact, activity=activity)
            return Response({'reminder_set': True}, status=201)

        if program_slug:
            program = Program.objects.filter(
                slug=program_slug, is_published=True).first()
            if program is None:
                return Response({'detail': 'Programme not found.'}, status=404)
            existing = ActivityReminder.objects.filter(
                contact=contact, program=program)
            if existing.exists():
                existing.delete()
                return Response({'reminder_set': False})
            ActivityReminder.objects.create(contact=contact, program=program)
            return Response({'reminder_set': True}, status=201)

        return Response(
            {'detail': 'activity_id or program_slug is required.'}, status=400)


class ActivitySaveToggleView(APIView):
    """POST /activities/save/ {activity_id} — toggle a bookmark.

    Saving is deliberately not registering: it holds no seat and tells
    staff nothing.
    """

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]

    def post(self, request):
        contact = request.member
        activity = Activity.objects.filter(
            pk=request.data.get('activity_id'), is_active=True).first()
        if activity is None:
            return Response({'detail': 'Activity not found.'}, status=404)
        existing = ActivitySave.objects.filter(
            contact=contact, activity=activity)
        if existing.exists():
            existing.delete()
            return Response({'saved': False})
        ActivitySave.objects.create(contact=contact, activity=activity)
        return Response({'saved': True}, status=201)


class ActivityRegistrationView(APIView):
    """POST /activities/register/ {activity_id, cancel?} — take or give up
    a place. The server decides between a seat and the waitlist."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]

    def post(self, request):
        contact = request.member
        now = timezone.now()
        activity = Activity.objects.filter(
            pk=request.data.get('activity_id'), is_active=True).first()
        if activity is None:
            return Response({'detail': 'Activity not found.'}, status=404)

        if request.data.get('cancel'):
            ActivityRegistration.objects.filter(
                contact=contact, activity=activity).update(
                    status=ActivityRegistration.Status.CANCELLED)
            return Response({
                'my_status': None,
                'registration': _registration_json(activity, now, None),
            })

        if not _may_attend(activity, contact):
            return Response(
                {'detail': 'This activity is not open to you.'}, status=403)

        state = activity.registration_state(now)
        if state in ('cancelled', 'closed', 'opens_later', 'full'):
            return Response(
                {'detail': 'Registration is not open.', 'state': state},
                status=409)
        if state == 'external':
            return Response(
                {'detail': 'Registration happens off-app.',
                 'external_url': activity.external_registration_url},
                status=409)

        status_value = (ActivityRegistration.Status.WAITLISTED
                        if state == 'waitlist'
                        else ActivityRegistration.Status.REGISTERED)
        registration, created = ActivityRegistration.objects.get_or_create(
            contact=contact, activity=activity,
            defaults={'status': status_value})
        if not created and registration.status != status_value:
            registration.status = status_value
            registration.save(update_fields=['status', 'updated_at'])
        return Response({
            'my_status': registration.status,
            'registration': _registration_json(
                activity, now, registration.status),
        }, status=201 if created else 200)
