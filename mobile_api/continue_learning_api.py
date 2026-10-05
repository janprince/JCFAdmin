"""Continue Learning (owner spec + designs 43–47).

A personalised learning hub: where the member left off, what they have
active, what comes next, and what to try afterwards.

The rules this module is built around:

* **The server picks the resume lesson.** Sequencing across modules,
  prerequisites, completion and access is too easy to get subtly wrong on
  a client that has only the current page in hand, so the client never
  guesses it.
* **The server owns progress.** Percentages, streaks and completion come
  from here. The client clamps what it renders but never invents a value,
  and opening a lesson is not completing it.
* **Aggregates are counted over everything, not over a page.** The summary
  is computed from the member's whole history; deriving it from whichever
  cursor page happened to load would quietly under-report.
* **Destinations are identifiers, not routes.** A lesson says
  `{"type": "video", "lesson_id": 12}` and the app maps that to its own
  router.
"""
import base64
from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from studies.models import Enrolment
from teachings.models import Teaching, TeachingProgress, TeachingSeries

from . import tiers
from .authentication import IsSignedIn, MobileTokenAuthentication

DEFAULT_LIMIT = 20
MAX_LIMIT = 200
RECOMMENDATION_LIMIT = 8

# A lesson counts as finished at this much watched, matching the player's
# own completion rule.
COMPLETION_THRESHOLD = 90


# --------------------------------------------------------------------------
# cursors
# --------------------------------------------------------------------------

def encode_cursor(*parts):
    raw = '|'.join(str(p) for p in parts)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip('=')


def decode_cursor(value):
    """-> list of strings, or None when unusable.

    A bad cursor yields page one rather than an error the client cannot
    recover from without clearing its own state.
    """
    if not value:
        return None
    try:
        padded = value + '=' * (-len(value) % 4)
        return base64.urlsafe_b64decode(padded.encode()).decode().split('|')
    except (ValueError, TypeError, UnicodeDecodeError):
        return None


def _limit_from(params):
    try:
        limit = int(params.get('limit', DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(limit, MAX_LIMIT))


# --------------------------------------------------------------------------
# access
# --------------------------------------------------------------------------

def _may_open(teaching, contact):
    if not teaching.is_premium:
        return True
    return tiers.is_approved(contact)


def _enrolment_for(series, enrolments):
    for enrolment in enrolments:
        if enrolment.series_id == series.id:
            return enrolment
    return None


def _access_json(teaching, contact, enrolment=None):
    allowed = _may_open(teaching, contact)
    expires_at = enrolment.access_expires_at if enrolment else None
    expired = bool(expires_at and expires_at <= timezone.now())
    if expired:
        allowed = False
        reason = 'expired'
    elif not allowed:
        reason = 'tier'
    else:
        reason = ''
    return {
        'allowed': allowed,
        'required_tier': teaching.tier,
        'enrolment_required': False,
        'expires_at': expires_at.isoformat() if expires_at else None,
        'restriction_reason': reason,
    }


# --------------------------------------------------------------------------
# progress helpers
# --------------------------------------------------------------------------

def _clamp_percent(value):
    return max(0, min(int(value or 0), 100))


def _lesson_status(teaching, progress, unlocked):
    if not unlocked:
        return 'locked'
    if progress is None:
        return 'not_started'
    if progress.completed or _clamp_percent(progress.percent) >= 100:
        return 'completed'
    if _clamp_percent(progress.percent) > 0:
        return 'in_progress'
    return 'not_started'


def _prerequisite_json(teaching, completed_ids):
    required = teaching.prerequisite
    if required is None:
        return {
            'required': False,
            'satisfied': True,
            'prerequisite_lesson_id': None,
            'prerequisite_title': '',
            'reason': '',
        }
    satisfied = required.id in completed_ids
    return {
        'required': True,
        'satisfied': satisfied,
        'prerequisite_lesson_id': required.id,
        'prerequisite_title': required.topic,
        'reason': '' if satisfied else 'incomplete_prerequisite',
    }


def _download_json(teaching, access_allowed):
    """Download state as the server understands it.

    The app has no download manager yet, so every lesson reports
    `not_downloaded` or `unavailable`. The shape is the final one, so the
    field does not have to change when the manager lands.
    """
    if not teaching.downloadable or not access_allowed:
        state = 'unavailable'
    else:
        state = 'not_downloaded'
    return {
        'downloadable': teaching.downloadable and access_allowed,
        'state': state,
        'progress_percentage': 0,
        'downloaded_bytes': None,
        'total_bytes': None,
        'expires_at': None,
        'failure_code': '',
    }


def _destination(teaching):
    """A stable identifier; the app owns the route."""
    return {'type': teaching.lesson_type, 'lesson_id': teaching.id}


def lesson_json(teaching, contact, progress_by_id, completed_ids,
                enrolment=None):
    progress = progress_by_id.get(teaching.id)
    prerequisite = _prerequisite_json(teaching, completed_ids)
    access = _access_json(teaching, contact, enrolment)
    unlocked = prerequisite['satisfied'] and access['allowed']
    series = teaching.series
    module = teaching.module
    return {
        'lesson_id': teaching.id,
        'course_id': series.id if series else None,
        'course_title': series.title if series else '',
        'module_id': module.id if module else None,
        'module_title': module.title if module else '',
        'title': teaching.topic,
        'type': teaching.lesson_type,
        'image_url': teaching.thumbnail.url if teaching.thumbnail else '',
        'course_category': series.category if series else 'other',
        'duration_seconds': teaching.duration_seconds,
        'progress_percentage': _clamp_percent(
            progress.percent if progress else 0),
        'position_seconds': progress.position_seconds if progress else None,
        'status': _lesson_status(teaching, progress, unlocked),
        'prerequisite': prerequisite,
        'access': access,
        'download': _download_json(teaching, access['allowed']),
        'destination': _destination(teaching),
    }


# --------------------------------------------------------------------------
# the view
# --------------------------------------------------------------------------

class ContinueLearningView(APIView):
    """GET /learning/continue — the personalised learning hub.

    Query: `course_cursor`, `lesson_cursor`, `limit`, `status`,
    `content_type`, `downloaded`.

    Requires authentication: every field on this screen is private
    progress, so nothing is fetched for a guest.
    """

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsSignedIn]

    def get(self, request):
        contact = request.member
        now = timezone.now()
        params = request.query_params

        progress_rows = list(
            TeachingProgress.objects.filter(contact=contact)
            .select_related('teaching'))
        progress_by_id = {p.teaching_id: p for p in progress_rows}
        completed_ids = {
            p.teaching_id for p in progress_rows
            if p.completed or _clamp_percent(p.percent) >= 100}

        enrolments = list(
            Enrolment.objects.filter(contact=contact)
            .select_related('series'))

        courses, course_cursor = self._active_courses(
            contact, params, progress_by_id, completed_ids, enrolments, now)
        lessons, lesson_cursor = self._up_next(
            contact, params, progress_by_id, completed_ids, enrolments)

        return Response({
            'resume_item': self._resume_item(
                contact, progress_rows, progress_by_id, completed_ids,
                enrolments, now),
            'learning_summary': self._summary(
                contact, progress_rows, completed_ids, now),
            'active_courses': {
                'results': courses,
                'next_cursor': course_cursor,
                'has_more': course_cursor is not None,
            },
            'up_next_lessons': {
                'results': lessons,
                'next_cursor': lesson_cursor,
                'has_more': lesson_cursor is not None,
            },
            'recommendations': self._recommendations(contact, enrolments),
            'server_time': now.isoformat(),
            'fetched_at': now.isoformat(),
        })

    # --- resume ---------------------------------------------------------

    def _resume_item(self, contact, progress_rows, progress_by_id,
                     completed_ids, enrolments, now):
        """The single most useful lesson to open right now.

        Priority: the most recently touched unfinished lesson, then the
        first unfinished lesson of the most recently touched course, then
        the first lesson of the newest enrolment. Anything locked,
        expired, unpublished or out of reach is skipped rather than
        offered and then refused.
        """
        candidates = []

        for row in sorted(progress_rows, key=lambda r: r.last_viewed_at,
                          reverse=True):
            if row.teaching_id in completed_ids:
                continue
            candidates.append(row.teaching)

        # Then: continue the course they were last in, from its first
        # unfinished lesson.
        for row in sorted(progress_rows, key=lambda r: r.last_viewed_at,
                          reverse=True):
            series_id = row.teaching.series_id
            if series_id is None:
                continue
            nxt = (Teaching.objects
                   .filter(series_id=series_id,
                           status=Teaching.Status.PUBLISHED)
                   .exclude(id__in=completed_ids)
                   .select_related('series', 'module', 'prerequisite')
                   .order_by('order', 'id').first())
            if nxt is not None:
                candidates.append(nxt)

        # Finally: the start of the newest enrolment.
        for enrolment in sorted(
                enrolments, key=lambda e: e.created_at, reverse=True):
            if enrolment.series_id is None:
                continue
            first = (Teaching.objects
                     .filter(series_id=enrolment.series_id,
                             status=Teaching.Status.PUBLISHED)
                     .exclude(id__in=completed_ids)
                     .select_related('series', 'module', 'prerequisite')
                     .order_by('order', 'id').first())
            if first is not None:
                candidates.append(first)

        seen = set()
        for teaching in candidates:
            if teaching.id in seen:
                continue
            seen.add(teaching.id)
            if teaching.status != Teaching.Status.PUBLISHED:
                continue
            enrolment = (_enrolment_for(teaching.series, enrolments)
                         if teaching.series else None)
            payload = lesson_json(
                teaching, contact, progress_by_id, completed_ids, enrolment)
            if not payload['access']['allowed']:
                continue
            if not payload['prerequisite']['satisfied']:
                continue

            duration = teaching.duration_seconds or 0
            position = payload['position_seconds'] or 0
            progress = progress_by_id.get(teaching.id)
            payload.update({
                'enrolment_id': enrolment.id if enrolment else None,
                'course_image_url': (
                    teaching.series.cover.url
                    if teaching.series and teaching.series.cover else ''),
                'duration_seconds': duration or None,
                'remaining_seconds': max(duration - position, 0) or None,
                'last_accessed_at': (
                    progress.last_viewed_at.isoformat()
                    if progress else None),
            })
            return payload
        return None

    # --- summary --------------------------------------------------------

    def _summary(self, contact, progress_rows, completed_ids, now):
        """Counted over the member's whole history, never over a page."""
        completed_courses = 0
        for series in TeachingSeries.objects.filter(
                is_published=True).annotate(
                    total=Count('teachings', filter=Q(
                        teachings__status=Teaching.Status.PUBLISHED))):
            if series.total == 0:
                continue
            series_lessons = set(
                Teaching.objects.filter(
                    series=series, status=Teaching.Status.PUBLISHED)
                .values_list('id', flat=True))
            if series_lessons and series_lessons <= completed_ids:
                completed_courses += 1

        total_seconds = 0
        for row in progress_rows:
            duration = row.teaching.duration_seconds or 0
            total_seconds += round(duration * _clamp_percent(row.percent) / 100)

        return {
            'completed_lessons': len(completed_ids),
            'completed_courses': completed_courses,
            'current_streak_days': self._streak(progress_rows, now),
            'downloaded_items': 0,
            'total_learning_seconds': total_seconds,
        }

    def _streak(self, progress_rows, now):
        """Consecutive local days with study, counting back from today.

        Computed here so every client agrees, and in the server's
        timezone so a member does not lose a streak by travelling. A
        streak that has already lapsed reads as zero rather than being
        quietly carried forward.
        """
        if not progress_rows:
            return 0
        tz = timezone.get_current_timezone()
        days = {row.last_viewed_at.astimezone(tz).date()
                for row in progress_rows}
        today = now.astimezone(tz).date()
        if today not in days and (today - timedelta(days=1)) not in days:
            return 0
        cursor = today if today in days else today - timedelta(days=1)
        streak = 0
        while cursor in days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    # --- active courses -------------------------------------------------

    def _active_courses(self, contact, params, progress_by_id,
                        completed_ids, enrolments, now):
        limit = _limit_from(params)
        series_ids = {e.series_id for e in enrolments if e.series_id}
        # A course the member has touched counts as active even without a
        # formal enrolment — otherwise browsing then returning loses it.
        series_ids |= {
            p.teaching.series_id for p in progress_by_id.values()
            if p.teaching.series_id}

        qs = (TeachingSeries.objects
              .filter(id__in=series_ids, is_published=True)
              .order_by('order', 'id'))

        cursor = decode_cursor(params.get('course_cursor'))
        if cursor is not None:
            try:
                qs = qs.filter(id__gt=int(cursor[-1]))
            except (ValueError, IndexError):
                pass

        page = list(qs[:limit + 1])
        has_more = len(page) > limit
        page = page[:limit]

        status_filter = params.get('status') or ''
        results = []
        for series in page:
            payload = self._course_json(
                series, contact, progress_by_id, completed_ids,
                enrolments, now)
            if status_filter and payload['status'] != status_filter:
                continue
            results.append(payload)

        cursor_out = encode_cursor(page[-1].id) if has_more and page else None
        return results, cursor_out

    def _course_json(self, series, contact, progress_by_id, completed_ids,
                     enrolments, now):
        lessons = list(
            Teaching.objects.filter(
                series=series, status=Teaching.Status.PUBLISHED)
            .order_by('order', 'id'))
        lesson_ids = [t.id for t in lessons]
        done = [i for i in lesson_ids if i in completed_ids]
        total_modules = series.modules.filter(is_published=True).count()
        completed_modules = 0
        for module in series.modules.filter(is_published=True):
            module_lessons = {
                t.id for t in lessons if t.module_id == module.id}
            if module_lessons and module_lessons <= completed_ids:
                completed_modules += 1

        percentage = (
            round(len(done) * 100 / len(lesson_ids)) if lesson_ids else 0)

        enrolment = _enrolment_for(series, enrolments)
        expires_at = enrolment.access_expires_at if enrolment else None
        expired = bool(expires_at and expires_at <= now)

        touched = [progress_by_id[i] for i in lesson_ids
                   if i in progress_by_id]
        last_accessed = max((p.last_viewed_at for p in touched), default=None)

        current = next((t for t in lessons if t.id not in completed_ids), None)

        if expired:
            status = 'expired'
        elif enrolment is not None and enrolment.status == 'paused':
            status = 'paused'
        elif lesson_ids and len(done) == len(lesson_ids):
            status = 'completed'
        elif done or touched:
            status = 'in_progress'
        else:
            status = 'not_started'

        return {
            'enrolment_id': enrolment.id if enrolment else None,
            'course_id': series.id,
            'title': series.title,
            'description': series.description,
            'image_url': series.cover.url if series.cover else '',
            'category': series.category,
            'facilitator': series.facilitator,
            'total_modules': total_modules,
            'completed_modules': completed_modules,
            'total_lessons': len(lesson_ids),
            'completed_lessons': len(done),
            'progress_percentage': _clamp_percent(percentage),
            'current_module_id': current.module_id if current else None,
            'current_lesson_id': current.id if current else None,
            'status': status,
            'access': {
                'allowed': not expired,
                'required_tier': 'general',
                'enrolment_required': False,
                'expires_at': expires_at.isoformat() if expires_at else None,
                'restriction_reason': 'expired' if expired else '',
            },
            'last_accessed_at': (
                last_accessed.isoformat() if last_accessed else None),
            'destination': {'type': 'course', 'course_id': series.id},
        }

    # --- up next --------------------------------------------------------

    def _up_next(self, contact, params, progress_by_id, completed_ids,
                 enrolments):
        limit = _limit_from(params)
        series_ids = {e.series_id for e in enrolments if e.series_id}
        series_ids |= {
            p.teaching.series_id for p in progress_by_id.values()
            if p.teaching.series_id}

        qs = (Teaching.objects
              .filter(status=Teaching.Status.PUBLISHED,
                      series_id__in=series_ids)
              .exclude(id__in=completed_ids)
              .select_related('series', 'module', 'prerequisite')
              .order_by('series__order', 'order', 'id'))

        content_type = params.get('content_type')
        if content_type:
            qs = qs.filter(lesson_type=content_type)

        cursor = decode_cursor(params.get('lesson_cursor'))
        if cursor is not None:
            try:
                qs = qs.filter(id__gt=int(cursor[-1]))
            except (ValueError, IndexError):
                pass

        page = list(qs[:limit + 1])
        has_more = len(page) > limit
        page = page[:limit]

        results = []
        for teaching in page:
            enrolment = (_enrolment_for(teaching.series, enrolments)
                         if teaching.series else None)
            results.append(lesson_json(
                teaching, contact, progress_by_id, completed_ids, enrolment))

        cursor_out = encode_cursor(page[-1].id) if has_more and page else None
        return results, cursor_out

    # --- recommendations ------------------------------------------------

    def _recommendations(self, contact, enrolments):
        """Courses to try next.

        Anything already active is excluded: a recommendation row that
        repeats what the member is part-way through wastes the space and
        confuses what the CTA means.
        """
        active_ids = {e.series_id for e in enrolments if e.series_id}
        active_ids |= set(
            TeachingProgress.objects.filter(contact=contact)
            .exclude(teaching__series__isnull=True)
            .values_list('teaching__series_id', flat=True))

        qs = (TeachingSeries.objects
              .filter(is_published=True, is_recommended=True)
              .exclude(id__in=active_ids)
              .annotate(lesson_count=Count('teachings', filter=Q(
                  teachings__status=Teaching.Status.PUBLISHED)))
              .order_by('order', 'id')[:RECOMMENDATION_LIMIT])

        return [{
            'course_id': series.id,
            'title': series.title,
            'image_url': series.cover.url if series.cover else '',
            'category': series.category,
            'facilitator': series.facilitator,
            'module_count': series.modules.filter(is_published=True).count(),
            'lesson_count': series.lesson_count,
            'access_level': 'general',
            'recommendation_reason': series.recommendation_reason,
            'destination': {'type': 'course', 'course_id': series.id},
        } for series in qs]


class LessonProgressView(APIView):
    """POST /learning/lessons/<pk>/progress/ {position_seconds, percent}

    The server stays authoritative: progress only moves forward, and
    completion needs the threshold to be reached rather than the screen
    merely having been opened.
    """

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsSignedIn]

    def post(self, request, pk):
        contact = request.member
        teaching = Teaching.objects.filter(
            pk=pk, status=Teaching.Status.PUBLISHED).first()
        if teaching is None:
            return Response({'detail': 'Lesson not found.'}, status=404)
        if not _may_open(teaching, contact):
            return Response(
                {'detail': 'This lesson is not open to you.'}, status=403)

        try:
            percent = _clamp_percent(request.data.get('percent'))
        except (TypeError, ValueError):
            return Response({'detail': 'percent must be a number.'},
                            status=400)
        position = request.data.get('position_seconds')
        try:
            position = None if position is None else max(0, int(position))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'position_seconds must be a number.'}, status=400)

        row, _ = TeachingProgress.objects.get_or_create(
            contact=contact, teaching=teaching)
        # Never move a member backwards because a stale client reported an
        # older position — a second device, or a queued offline write.
        if percent > row.percent:
            row.percent = percent
        if position is not None and (
                row.position_seconds is None
                or position > row.position_seconds):
            row.position_seconds = position
        if row.percent >= COMPLETION_THRESHOLD:
            row.completed = True
            row.percent = 100
        row.save()

        return Response({
            'lesson_id': teaching.id,
            'progress_percentage': row.percent,
            'position_seconds': row.position_seconds,
            'completed': row.completed,
            'server_time': timezone.now().isoformat(),
        })
