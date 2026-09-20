"""Mobile Upcoming Activities feed (design 25): scheduled activities merged
with published programmes, plus per-item reminders."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Activity, ActivityReminder
from programs.models import Program

from .authentication import IsMember, MobileTokenAuthentication

# How far ahead the feed looks, and how soon before start a live session is
# flagged "Live soon".
FEED_WINDOW_DAYS = 60
LIVE_SOON_MINUTES = 60


def _audiences_for(contact):
    values = [Activity.Audience.PUBLIC]
    if contact is not None:
        if contact.is_member or contact.is_student:
            values.append(Activity.Audience.MEMBERS)
        if contact.is_student:
            values.append(Activity.Audience.STUDENTS)
    return values


def _activity_json(activity, now, reminded_ids):
    delta = activity.starts_at - now
    live_soon = (
        activity.kind == Activity.Kind.LIVE
        and delta <= timedelta(minutes=LIVE_SOON_MINUTES)
    )
    return {
        'kind': activity.kind,
        'activity_id': activity.id,
        'program_slug': None,
        'title': activity.title,
        'description': activity.description,
        'starts_at': activity.starts_at.isoformat(),
        'all_day': False,
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


class UpcomingActivitiesView(APIView):
    """GET /activities/upcoming/ — the unified schedule, soonest first.
    Public; each caller sees only their audience. An ongoing activity stays
    in the feed until it ends."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        token = getattr(request, 'auth', None)
        contact = token.contact if token is not None else None
        now = timezone.now()
        today = timezone.localdate()
        horizon = now + timedelta(days=FEED_WINDOW_DAYS)
        audiences = _audiences_for(contact)

        activities = [
            a for a in Activity.objects.filter(
                is_active=True, audience__in=audiences,
                starts_at__gte=now - timedelta(hours=6), starts_at__lte=horizon)
            if a.starts_at + timedelta(minutes=a.duration_minutes) >= now
        ]
        programs = list(Program.objects.filter(
            is_published=True, audience__in=audiences,
            starts_on__isnull=False, starts_on__gte=today,
            starts_on__lte=horizon.date()))

        reminded_ids, reminded_slugs = set(), set()
        if contact is not None:
            reminders = ActivityReminder.objects.filter(
                contact=contact).select_related('program')
            reminded_ids = {r.activity_id for r in reminders if r.activity_id}
            reminded_slugs = {
                r.program.slug for r in reminders if r.program_id}

        items = ([_activity_json(a, now, reminded_ids) for a in activities]
                 + [_program_json(p, reminded_slugs) for p in programs])
        items.sort(key=lambda i: i['starts_at'])
        return Response({'results': items})


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
