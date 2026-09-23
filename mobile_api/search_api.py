"""Global search (designs 30/31): one query across teachings, practices,
programmes, events (activities), centres and announcements, plus the
Popular Searches list aggregated from logged queries."""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Activity
from centres.models import Centre
from engagement.models import Announcement
from practices.models import Practice
from programs.models import Program
from teachings.models import Teaching

from .authentication import MobileTokenAuthentication
from .content import _can_premium
from .models import SearchQuery

PER_DOMAIN = 10
POPULAR_WINDOW_DAYS = 60


def _audiences_for(contact):
    values = ['public']
    if contact is not None:
        if contact.is_member or contact.is_student:
            values.append('members')
        if contact.is_student:
            values.append('students')
    return values


def _teaching_results(q, can_premium):
    rows = Teaching.objects.filter(
        Q(topic__icontains=q) | Q(description__icontains=q) |
        Q(author__icontains=q),
        status=Teaching.Status.PUBLISHED,
    )[:PER_DOMAIN]
    return [{
        'kind': 'audio' if t.media_kind == 'audio' else 'video',
        'title': t.topic,
        'subtitle': t.author,
        'description': t.description,
        'slug': t.slug,
        'id': t.id,
        'thumbnail_url': t.thumbnail.url if t.thumbnail else '',
        'duration_seconds': t.duration_seconds,
        'date': t.created_at.date().isoformat(),
        'audience': 'members' if t.is_premium else 'public',
        'locked': t.is_premium and not can_premium,
        'views': t.view_count,
    } for t in rows]


def _practice_results(q, audiences):
    rows = Practice.objects.filter(
        Q(title__icontains=q) | Q(description__icontains=q),
        is_active=True, audience__in=audiences,
    )[:PER_DOMAIN]
    return [{
        'kind': 'practice',
        'title': p.title,
        'subtitle': '',
        'description': p.description,
        'slug': p.slug,
        'id': p.id,
        'thumbnail_url': '',
        'minutes': p.minutes,
        'date': None,
        'audience': p.audience,
    } for p in rows]


def _program_results(q, audiences):
    rows = Program.objects.filter(
        Q(title__icontains=q) | Q(description__icontains=q),
        is_published=True, audience__in=audiences,
    )[:PER_DOMAIN]
    return [{
        'kind': 'programme',
        'title': p.title,
        'subtitle': '',
        'description': p.description,
        'slug': p.slug,
        'id': p.id,
        'thumbnail_url': p.image.url if p.image else '',
        'date': p.starts_on.isoformat() if p.starts_on else None,
        'audience': p.audience,
    } for p in rows]


def _event_results(q, audiences):
    now = timezone.now()
    rows = Activity.objects.filter(
        Q(title__icontains=q) | Q(description__icontains=q),
        is_active=True, audience__in=audiences, starts_at__gte=now,
    )[:PER_DOMAIN]
    return [{
        'kind': 'event',
        'title': a.title,
        'subtitle': a.venue,
        'description': a.description,
        'slug': None,
        'id': a.id,
        'thumbnail_url': '',
        'date': a.starts_at.isoformat(),
        'audience': a.audience,
    } for a in rows]


def _centre_results(q):
    rows = Centre.objects.filter(
        Q(name__icontains=q) | Q(location__icontains=q) |
        Q(description__icontains=q),
        is_active=True,
    )[:PER_DOMAIN]
    return [{
        'kind': 'centre',
        'title': c.name,
        'subtitle': f'{c.location}, {c.country}',
        'description': c.description,
        'slug': c.slug,
        'id': c.id,
        'thumbnail_url': c.image.url if c.image else '',
        'date': None,
        'audience': 'public',
    } for c in rows]


def _announcement_results(q, audiences):
    rows = Announcement.objects.filter(
        Q(title__icontains=q) | Q(body__icontains=q),
        is_published=True, audience__in=audiences,
    )[:PER_DOMAIN]
    return [{
        'kind': 'announcement',
        'title': a.title,
        'subtitle': '',
        'description': a.body,
        'slug': None,
        'id': a.id,
        'thumbnail_url': a.image.url if a.image else '',
        'date': a.created_at.date().isoformat(),
        'audience': a.audience,
    } for a in rows]


class GlobalSearchView(APIView):
    """GET /search/?q=... — audience-filtered results across every domain."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        q = (request.query_params.get('q') or '').strip()
        if len(q) < 2:
            return Response({'query': q, 'total': 0, 'results': []})

        token = getattr(request, 'auth', None)
        contact = token.contact if token is not None else None
        audiences = _audiences_for(contact)
        can_premium = _can_premium(request)

        results = (
            _teaching_results(q, can_premium)
            + _practice_results(q, audiences)
            + _program_results(q, audiences)
            + _event_results(q, audiences)
            + _centre_results(q)
            + _announcement_results(q, audiences)
        )

        SearchQuery.objects.create(term=q.lower()[:120], contact=contact)
        return Response({'query': q, 'total': len(results),
                         'results': results})


class PopularSearchesView(APIView):
    """GET /search/popular/ — the five most-run terms of the last 60 days."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        since = timezone.now() - timedelta(days=POPULAR_WINDOW_DAYS)
        rows = (
            SearchQuery.objects.filter(created_at__gte=since)
            .values('term')
            .annotate(hits=Count('id'))
            .order_by('-hits', 'term')[:5]
        )
        return Response({'results': [r['term'] for r in rows]})
