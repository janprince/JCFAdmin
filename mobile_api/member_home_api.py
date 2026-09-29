"""Member Home aggregate (GET /home/member/).

One authenticated round trip for the member home screen: summary, welcome
block, resumable learning and practice, a member-exclusive teaching, today's
inspirations, the next event, quick actions and the latest announcement.

Every section reuses the same helpers as its standalone endpoint, so the
aggregate can never drift from the per-domain APIs.
"""
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Activity, ActivityReminder
from engagement.models import Announcement, AnnouncementRead, Notification
from practices.models import PracticeLog
from teachings.models import Teaching, TeachingProgress

from .activities_api import _audiences_for as _activity_audiences
from .activities_api import _activity_json, _program_json
from .authentication import IsStudentOrMember, MobileTokenAuthentication
from .engagement_api import (AnnouncementSerializer, InspirationSerializer,
                             allowed_audience_values)
from .practices_api import _audiences_for as _practice_audiences
from .practices_api import _practice_json, _streak
from engagement.models import DailyInspiration
from programs.models import Program

# Destination identifiers the app maps to its own routes. The API never
# sends raw route strings.
DEST_JOURNEY = 'journey'
DEST_LESSON = 'lesson'
DEST_SERIES = 'series'
DEST_PRACTICE = 'practice'
DEST_TEACHING = 'teaching'
DEST_EVENT = 'event'
DEST_ANNOUNCEMENT = 'announcement'


def _member_summary(contact):
    first = (contact.full_name or '').strip().split(' ')[0]
    return {
        'id': contact.id,
        'preferred_name': first,
        'first_name': first,
        'avatar_url': '',
        'membership_status': 'student' if contact.is_student else 'member',
        'membership_label': (
            str(_('JCF Student')) if contact.is_student
            else str(_('JCF Member'))),
    }


def _welcome(contact):
    """Default welcome block. Server-owned so copy and artwork can change
    without an app release; image_url empty means "use the packaged asset"."""
    return {
        'eyebrow': str(_('YOUR JOURNEY')),
        'title_template': str(_('Welcome back, {name}')),
        'message': str(
            _('Continue growing in awareness, one conscious step at a time.')),
        'image_url': '',
        'action_label': str(_('Continue Your Journey')),
        'destination_id': DEST_JOURNEY,
    }


def _continue_learning(contact):
    """Resumable series, most recently touched first (same rules as
    /learning/continue/)."""
    rows = (
        TeachingProgress.objects.filter(contact=contact)
        .select_related('teaching', 'teaching__series')
        .order_by('-last_viewed_at')
    )
    completed_ids = {r.teaching_id for r in rows if r.completed}
    cards, seen = [], set()
    for row in rows:
        series = row.teaching.series
        if series is None or series.id in seen or not series.is_published:
            continue
        seen.add(series.id)
        lessons = list(series.teachings.filter(
            status=Teaching.Status.PUBLISHED).order_by('order', 'id'))
        total = len(lessons)
        done = sum(1 for lesson in lessons if lesson.id in completed_ids)
        if total and done >= total:
            continue  # finished series are not "resumable"
        resume = next(
            (r.teaching for r in rows
             if r.teaching.series_id == series.id and not r.completed),
            next((l for l in lessons if l.id not in completed_ids), None),
        )
        remaining = sum(
            (l.duration_seconds or 0) for l in lessons
            if l.id not in completed_ids)
        cards.append({
            'content_id': series.slug,
            'content_type': 'series',
            'title': series.title,
            'subtitle': resume.author if resume else '',
            'current_unit_id': resume.slug if resume else None,
            'current_unit_title': resume.topic if resume else '',
            'image_url': series.cover.url if series.cover else '',
            'completed_units': done,
            'total_units': total,
            'progress_percentage': round(done * 100 / total) if total else 0,
            'remaining_seconds': remaining or None,
            'last_accessed_at': row.last_viewed_at,
            'destination_id': DEST_LESSON if resume else DEST_SERIES,
        })
    return cards[:3]


def _continue_practice(contact):
    """The most recent practice the member logged, with their live streak."""
    log = (
        PracticeLog.objects.filter(contact=contact, practice__isnull=False)
        .select_related('practice')
        .order_by('-date', '-created_at')
        .first()
    )
    if log is None or not log.practice.is_active:
        return []
    today = timezone.localdate()
    practice = log.practice
    if practice.audience not in _practice_audiences(contact):
        return []
    return [{
        'practice_id': practice.slug,
        'title': practice.title,
        'subtitle': practice.get_category_display(),
        'current_session_id': practice.slug,
        'image_url': '',
        # Practices repeat daily rather than completing, so the app shows the
        # streak instead of a percentage bar.
        'progress_percentage': None,
        'current_streak': _streak(contact, today),
        'duration_seconds': practice.minutes * 60,
        'last_accessed_at': log.created_at,
        'destination_id': DEST_PRACTICE,
    }]


def _featured_member_content(contact):
    """One member-exclusive teaching the member has not finished."""
    seen = set(
        TeachingProgress.objects.filter(contact=contact, completed=True)
        .values_list('teaching_id', flat=True))
    teaching = (
        Teaching.objects.filter(
            status=Teaching.Status.PUBLISHED, tier=Teaching.Tier.PREMIUM)
        .exclude(id__in=seen)
        .order_by('-created_at')
        .first()
    )
    if teaching is None:
        return None
    # Access is decided here, never by "the caller is authenticated".
    granted = bool(contact.is_active and (contact.is_member or contact.is_student))
    return {
        'id': teaching.slug,
        'content_type': teaching.media_kind,
        'title': teaching.topic,
        'speaker': teaching.author,
        'image_url': teaching.thumbnail.url if teaching.thumbnail else '',
        'duration_seconds': teaching.duration_seconds,
        'reading_time_minutes': None,
        'access_level': 'members',
        'access_granted': granted,
        'destination_id': DEST_TEACHING,
    }


def _featured_event(contact):
    """The soonest activity or dated programme this member may attend."""
    now = timezone.now()
    today = timezone.localdate()
    audiences = _activity_audiences(contact)
    reminders = ActivityReminder.objects.filter(contact=contact)
    reminded_ids = {r.activity_id for r in reminders if r.activity_id}
    reminded_slugs = {
        r.program.slug for r in reminders.select_related('program')
        if r.program_id}

    activity = next((
        a for a in Activity.objects.filter(
            is_active=True, audience__in=audiences,
            starts_at__gte=now - timedelta(hours=6))
        if a.starts_at + timedelta(minutes=a.duration_minutes) >= now), None)
    program = Program.objects.filter(
        is_published=True, audience__in=audiences,
        starts_on__isnull=False, starts_on__gte=today).first()

    if activity is not None:
        item = _activity_json(activity, now, reminded_ids)
        item['facilitator'] = ''
        item['ends_at'] = (
            activity.starts_at
            + timedelta(minutes=activity.duration_minutes)).isoformat()
        item['destination_id'] = DEST_EVENT
        if program is not None and program.starts_on.isoformat() < item['starts_at'][:10]:
            item = None
    if activity is None or item is None:
        if program is None:
            return None
        item = _program_json(program, reminded_slugs)
        item['facilitator'] = ''
        item['ends_at'] = None
        item['destination_id'] = DEST_EVENT
    item['timezone'] = str(timezone.get_current_timezone())
    item['join_url'] = ''
    item['replay_url'] = ''
    return item


def _quick_actions(contact):
    """Stable identifiers; the app owns the routes and icons. Downloads is
    omitted until offline downloads ship."""
    return [
        {'id': 'my_library', 'sort_order': 1},
        {'id': 'my_programs', 'sort_order': 2},
        {'id': 'saved', 'sort_order': 3},
    ]


def _announcements(contact):
    audiences = allowed_audience_values(contact)
    read_ids = set(
        AnnouncementRead.objects.filter(contact=contact)
        .values_list('announcement_id', flat=True))
    rows = Announcement.objects.filter(
        is_published=True, audience__in=audiences)[:3]
    out = []
    for row in rows:
        data = AnnouncementSerializer(
            row, context={'read_ids': read_ids}).data
        data['category'] = row.get_audience_display()
        data['summary'] = row.body[:180]
        data['read'] = row.id in read_ids
        data['destination_id'] = DEST_ANNOUNCEMENT
        out.append(data)
    return out


class MemberHomeView(APIView):
    """GET /home/member/ — everything the member home screen renders."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsStudentOrMember]

    def get(self, request):
        contact = request.member
        inspirations = (
            DailyInspiration.objects.filter(
                is_published=True, date__lte=timezone.localdate())
            .select_related('related_teaching')
            .order_by('-date')[:3]
        )
        return Response({
            'member_summary': _member_summary(contact),
            'welcome': _welcome(contact),
            'continue_learning': _continue_learning(contact),
            'continue_practice': _continue_practice(contact),
            'daily_inspirations': [
                InspirationSerializer(i).data for i in inspirations],
            'featured_member_content': _featured_member_content(contact),
            'featured_event': _featured_event(contact),
            'quick_actions': _quick_actions(contact),
            'announcements': _announcements(contact),
            'unread_notification_count': Notification.objects.filter(
                contact=contact, read_at__isnull=True).count(),
            'fetched_at': timezone.now().isoformat(),
        })
