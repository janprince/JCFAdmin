"""Mobile practice API (design 27): today's practice, streak, weekly goal,
practice library and session logging."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from practices.models import WEEKLY_GOAL, Practice, PracticeLog

from .authentication import IsStudentOrMember, MobileTokenAuthentication


def _audiences_for(contact):
    values = [Practice.Audience.PUBLIC]
    if contact is not None:
        if contact.is_member or contact.is_student:
            values.append(Practice.Audience.MEMBERS)
        if contact.is_student:
            values.append(Practice.Audience.STUDENTS)
    return values


def _practice_json(practice):
    return {
        'id': practice.id,
        'slug': practice.slug,
        'title': practice.title,
        'description': practice.description,
        'category': practice.category,
        'minutes': practice.minutes,
        'audio_url': practice.resolved_audio_url,
    }


def _streak(contact, today):
    """Consecutive practice days ending today (or yesterday when today is
    still open)."""
    days = set(
        PracticeLog.objects.filter(
            contact=contact, date__gte=today - timedelta(days=400))
        .values_list('date', flat=True)
    )
    if not days:
        return 0
    day = today if today in days else today - timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


class PracticeListView(APIView):
    """GET /practices/ — the practice library for the caller's audience.
    Public, so guests can see (and try) the free intro practices."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        token = getattr(request, 'auth', None)
        contact = token.contact if token is not None else None
        practices = Practice.objects.filter(
            is_active=True, audience__in=_audiences_for(contact))
        return Response({'results': [_practice_json(p) for p in practices]})


class PracticeSummaryView(APIView):
    """GET /practice/summary/ — streak, this week, today's practice."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsStudentOrMember]

    def get(self, request):
        contact = request.member
        today = timezone.localdate()
        monday = today - timedelta(days=today.weekday())

        practices = list(Practice.objects.filter(
            is_active=True, audience__in=_audiences_for(contact)))

        week_logs = PracticeLog.objects.filter(
            contact=contact, date__gte=monday, date__lte=monday + timedelta(days=6))
        counts = {}
        for log in week_logs:
            counts[log.date] = counts.get(log.date, 0) + 1

        week = []
        for i in range(7):
            day = monday + timedelta(days=i)
            week.append({
                'date': day,
                'count': counts.get(day, 0),
                'done': counts.get(day, 0) > 0,
            })
        total = sum(d['count'] for d in week)
        done_days = sum(1 for d in week if d['done'])

        todays = None
        if practices:
            todays = practices[today.toordinal() % len(practices)]

        return Response({
            'streak_days': _streak(contact, today),
            'week': week,
            'week_total': total,
            'week_days_done': done_days,
            'weekly_goal': WEEKLY_GOAL,
            'goal_percent': round(min(done_days, WEEKLY_GOAL) * 100 / WEEKLY_GOAL),
            'done_today': counts.get(today, 0) > 0,
            'todays_practice': _practice_json(todays) if todays else None,
            'practices': [_practice_json(p) for p in practices],
        })


class PracticeLogView(APIView):
    """POST /practice/log/ {practice_id?, minutes?} — record today's session."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsStudentOrMember]

    def post(self, request):
        practice = None
        practice_id = request.data.get('practice_id')
        if practice_id:
            practice = Practice.objects.filter(
                pk=practice_id, is_active=True).first()
        minutes = int(request.data.get('minutes') or
                      (practice.minutes if practice else 0))
        PracticeLog.objects.create(
            contact=request.member,
            practice=practice,
            date=timezone.localdate(),
            minutes=minutes,
        )
        today = timezone.localdate()
        return Response(
            {'streak_days': _streak(request.member, today), 'logged': True},
            status=201,
        )
