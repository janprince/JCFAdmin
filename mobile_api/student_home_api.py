"""Student Home aggregate (GET /home/student/).

One authenticated call for the student home: enrolment and programme
progress, the lesson and practice to do next, the next live class, canonical
progress aggregates, the next milestone, the assigned mentor, daily
inspiration, priority updates and quick actions.

This is the home for everyone who is signed in, enrolled on a course or
not, so every section is optional. Someone with no enrolment still gets
inspiration, updates and quick actions rather than a page of zeroes.

Progress values are computed here from published lessons and recorded
progress, so the app never derives them from a partial page of data.
"""
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Activity, ActivityReminder
from engagement.models import (Announcement, AnnouncementRead,
                               DailyInspiration, Notification)
from practices.models import PracticeLog
from studies.models import Enrolment, Mentorship, Milestone, PracticeAssignment
from teachings.models import Teaching, TeachingProgress

from . import tiers
from .authentication import IsStudent, MobileTokenAuthentication
from .engagement_api import InspirationSerializer
from .practices_api import _streak

# How soon before a live class the join button opens.
JOIN_WINDOW = timedelta(minutes=15)
STARTING_SOON = timedelta(minutes=60)

DEST_LESSON = 'lesson'
DEST_PRACTICE = 'practice'
DEST_PROGRAM = 'program'
DEST_CLASS = 'live_class'
DEST_MILESTONE = 'milestone'
DEST_MENTOR = 'mentor'
DEST_ANNOUNCEMENT = 'announcement'


def _student_summary(contact, enrolment):
    first = (contact.full_name or '').strip().split(' ')[0]
    expires = enrolment.access_expires_at if enrolment else None
    return {
        'id': contact.id,
        'preferred_name': first,
        'first_name': first,
        'avatar_url': '',
        'student_status': enrolment.status if enrolment else 'none',
        'access_expires_at': expires.isoformat() if expires else None,
    }


def _pick_enrolment(contact):
    """The enrolment the hero shows: the primary open one, else the most
    recently used open one. A paused, completed or expired enrolment is
    never silently promoted to 'current'."""
    enrolments = list(
        Enrolment.objects.filter(contact=contact)
        .select_related('program', 'series'))
    open_ones = [e for e in enrolments if e.is_open]
    if open_ones:
        primary = next((e for e in open_ones if e.is_primary), None)
        return primary or open_ones[0], enrolments
    return (enrolments[0] if enrolments else None), enrolments


def _lesson_state(contact, enrolment):
    """Completed lessons and the next one to open for this enrolment."""
    if enrolment is None:
        return [], set(), None
    lessons = enrolment.lessons()
    completed = set(
        TeachingProgress.objects
        .filter(contact=contact, completed=True,
                teaching__in=[lesson.id for lesson in lessons] or [0])
        .values_list('teaching_id', flat=True))
    # Resume at the most recently viewed unfinished lesson, else the first
    # lesson that is not complete.
    viewed = (
        TeachingProgress.objects
        .filter(contact=contact, completed=False,
                teaching__in=[lesson.id for lesson in lessons] or [0])
        .select_related('teaching')
        .order_by('-last_viewed_at')
        .first()
    )
    nxt = viewed.teaching if viewed else next(
        (lesson for lesson in lessons if lesson.id not in completed), None)
    return lessons, completed, nxt


def _enrolment_json(enrolment, percent, lessons, nxt):
    program = enrolment.program
    return {
        'enrolment_id': enrolment.id,
        'program_id': program.slug,
        'program_title': program.title,
        'image_url': program.image.url if program.image else '',
        'cohort': enrolment.cohort,
        'intake': str(program.year),
        'current_module_id': enrolment.series.slug if enrolment.series else None,
        'current_module_title': (
            nxt.topic if nxt else (
                enrolment.series.title if enrolment.series else '')),
        'progress_percentage': percent,
        'status': enrolment.status,
        'last_accessed_at': (
            enrolment.last_accessed_at.isoformat()
            if enrolment.last_accessed_at else None),
        'is_primary': enrolment.is_primary,
        'destination_id': DEST_PROGRAM,
    }


def _continue_course(enrolment, lessons, completed, nxt):
    if enrolment is None or nxt is None:
        return None
    total = len(lessons)
    done = len(completed)
    return {
        'course_id': enrolment.series.slug if enrolment.series else '',
        'course_title': enrolment.series.title if enrolment.series else '',
        'module_id': enrolment.series.slug if enrolment.series else None,
        'module_title': enrolment.series.title if enrolment.series else '',
        'lesson_id': nxt.slug,
        'lesson_title': nxt.topic,
        'lesson_type': nxt.media_kind,
        'image_url': nxt.thumbnail.url if nxt.thumbnail else '',
        'progress_percentage': round(done * 100 / total) if total else 0,
        'remaining_seconds': sum(
            (lesson.duration_seconds or 0) for lesson in lessons
            if lesson.id not in completed) or None,
        'started': done > 0,
        # Access follows the enrolment, not merely being signed in.
        'access_granted': enrolment.is_open,
        'destination_id': DEST_LESSON,
    }


def _assignment_json(assignment, now):
    practice = assignment.practice
    return {
        'assignment_id': assignment.id,
        'practice_id': practice.slug,
        'title': practice.title,
        'practice_type': practice.category,
        'image_url': '',
        'duration_seconds': practice.minutes * 60,
        'assigned_at': assignment.assigned_at.isoformat(),
        'due_at': assignment.due_at.isoformat() if assignment.due_at else None,
        'started_at': (assignment.started_at.isoformat()
                       if assignment.started_at else None),
        'completed_at': (assignment.completed_at.isoformat()
                         if assignment.completed_at else None),
        'status': assignment.status(now),
        'required': assignment.required,
        'attempt_count': assignment.attempt_count,
        'destination_id': DEST_PRACTICE,
    }


def _assigned_practices(contact, now):
    rows = (
        PracticeAssignment.objects
        .filter(contact=contact, completed_at__isnull=True)
        .select_related('practice')
    )
    return [_assignment_json(a, now) for a in rows
            if a.practice.is_active][:3]


def _next_live_class(contact, now):
    """The next class the student may attend, with join gated by time."""
    activity = next((
        a for a in Activity.objects.filter(
            is_active=True, kind=Activity.Kind.LIVE,
            starts_at__gte=now - timedelta(hours=6))
        if a.starts_at + timedelta(minutes=a.duration_minutes) >= now), None)
    if activity is None:
        return None
    ends = activity.starts_at + timedelta(minutes=activity.duration_minutes)
    if activity.starts_at <= now < ends:
        status = 'live'
    elif activity.starts_at - now <= STARTING_SOON:
        status = 'starting_soon'
    else:
        status = 'upcoming'
    join_allowed = activity.starts_at - now <= JOIN_WINDOW and now < ends
    reminded = ActivityReminder.objects.filter(
        contact=contact, activity=activity).exists()
    return {
        'session_id': activity.id,
        'title': activity.title,
        'module_title': '',
        'facilitator': '',
        'image_url': '',
        'starts_at': activity.starts_at.isoformat(),
        'ends_at': ends.isoformat(),
        'timezone': str(timezone.get_current_timezone()),
        'status': status,
        'attendance_status': 'registered' if reminded else 'not_registered',
        'join_allowed': join_allowed,
        # The joining link is withheld until the window opens.
        'join_url': '' if not join_allowed else '',
        'replay_url': '',
        'reminder_enabled': reminded,
        'venue': activity.venue,
        'destination_id': DEST_CLASS,
    }


def _progress_summary(contact, enrolment, lessons, completed, percent):
    required = PracticeAssignment.objects.filter(
        contact=contact, required=True)
    milestone = None
    if enrolment is not None:
        milestone = (
            Milestone.objects
            .filter(program=enrolment.program, is_active=True,
                    required_progress__gt=percent)
            .first()
        )
    return {
        'program_percentage': percent,
        'completed_lessons': len(completed),
        'total_lessons': len(lessons),
        'completed_practices': required.filter(
            completed_at__isnull=False).count(),
        'required_practices': required.count(),
        'current_streak': _streak(contact, timezone.localdate()),
        'next_milestone_percentage': (
            milestone.required_progress if milestone else None),
    }


def _next_milestone(enrolment, percent):
    if enrolment is None:
        return None
    milestone = (
        Milestone.objects.filter(program=enrolment.program, is_active=True)
        .filter(required_progress__gt=percent)
        .first()
    ) or Milestone.objects.filter(
        program=enrolment.program, is_active=True).last()
    if milestone is None:
        return None
    return {
        'id': milestone.id,
        'title': milestone.title,
        'description': milestone.description,
        'image_url': '',
        'current_progress': percent,
        'required_progress': milestone.required_progress,
        'status': milestone.status_for(percent),
        'achieved_at': None,
        'destination_id': DEST_MILESTONE,
    }


def _mentor(contact):
    mentorship = (
        Mentorship.objects.filter(student=contact, is_active=True)
        .select_related('mentor__contact')
        .first()
    )
    if mentorship is None:
        return None
    mentor_contact = mentorship.mentor.contact
    return {
        'id': mentorship.id,
        'display_name': mentor_contact.full_name,
        'role': mentorship.mentor.role or str(_('Mentor')),
        'avatar_url': '',
        'availability': mentorship.availability,
        'next_check_in_at': (
            mentorship.next_check_in_at.isoformat()
            if mentorship.next_check_in_at else None),
        'messaging_enabled': mentorship.messaging_enabled,
        'booking_enabled': mentorship.booking_enabled,
        'destination_id': DEST_MENTOR,
    }


def _updates(contact, now):
    """Priority feed: urgent deadlines first, then unread announcements."""
    items = []
    for assignment in (
        PracticeAssignment.objects
        .filter(contact=contact, completed_at__isnull=True,
                due_at__isnull=False)
        .select_related('practice')
    ):
        status = assignment.status(now)
        if status not in (PracticeAssignment.Status.OVERDUE,
                          PracticeAssignment.Status.DUE_SOON):
            continue
        items.append({
            'id': f'assignment-{assignment.id}',
            'type': 'assignment',
            'title': assignment.practice.title,
            'summary': assignment.practice.description[:160],
            'published_at': assignment.assigned_at.isoformat(),
            'due_at': assignment.due_at.isoformat(),
            'priority': ('urgent'
                         if status == PracticeAssignment.Status.OVERDUE
                         else 'important'),
            'read': False,
            'destination_id': DEST_PRACTICE,
            'sort_key': (0, assignment.due_at.isoformat()),
        })

    read_ids = set(
        AnnouncementRead.objects.filter(contact=contact)
        .values_list('announcement_id', flat=True))
    for row in Announcement.objects.filter(
            is_published=True,
            audience__in=tiers.visible_audiences(contact))[:5]:
        items.append({
            'id': f'announcement-{row.id}',
            'type': 'announcement',
            'title': row.title,
            'summary': row.body[:160],
            'published_at': row.created_at.isoformat(),
            'due_at': None,
            'priority': 'important' if row.pinned else 'normal',
            'read': row.id in read_ids,
            'destination_id': DEST_ANNOUNCEMENT,
            'sort_key': (1 if row.id not in read_ids else 2,
                         row.created_at.isoformat()),
        })

    items.sort(key=lambda i: i['sort_key'])
    for item in items:
        item.pop('sort_key')
    return items[:3]


class StudentHomeView(APIView):
    """GET /home/student/ — everything the student home renders."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsStudent]

    def get(self, request):
        contact = request.member
        now = timezone.now()

        enrolment, all_enrolments = _pick_enrolment(contact)
        lessons, completed, nxt = _lesson_state(contact, enrolment)
        percent = (round(len(completed) * 100 / len(lessons))
                   if lessons else 0)

        active = [
            _enrolment_json(e, percent if e == enrolment else 0,
                            lessons if e == enrolment else [],
                            nxt if e == enrolment else None)
            for e in all_enrolments if e.is_open
        ]

        return Response({
            'student_summary': _student_summary(contact, enrolment),
            'primary_enrolment': (
                _enrolment_json(enrolment, percent, lessons, nxt)
                if enrolment else None),
            'active_enrolments': active,
            'continue_course': _continue_course(
                enrolment, lessons, completed, nxt),
            'assigned_practices': _assigned_practices(contact, now),
            'next_live_class': _next_live_class(contact, now),
            'progress_summary': _progress_summary(
                contact, enrolment, lessons, completed, percent),
            'next_milestone': _next_milestone(enrolment, percent),
            'mentor': _mentor(contact),
            # Carried over from the member home when the two merged: it is
            # the one thing that screen had which this one lacked, and the
            # only section a signed-in person with no course is sure to see.
            'daily_inspirations': [
                InspirationSerializer(i).data
                for i in DailyInspiration.objects.filter(
                    is_published=True, date__lte=timezone.localdate())
                .select_related('related_teaching')
                .order_by('-date')[:3]
            ],
            'updates': _updates(contact, now),
            'quick_actions': [
                {'id': 'courses', 'sort_order': 1},
                {'id': 'schedule', 'sort_order': 2},
                {'id': 'assignments', 'sort_order': 3},
            ],
            'unread_notification_count': Notification.objects.filter(
                contact=contact, read_at__isnull=True).count(),
            'fetched_at': now.isoformat(),
        })
