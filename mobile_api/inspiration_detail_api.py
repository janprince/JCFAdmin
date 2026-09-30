"""Daily Inspiration detail: the public reading screen plus the member-only
save and reflection actions.

Reading is public — a shared link must open for anyone. Only save and
reflection require a member token.
"""
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from engagement.models import (DailyInspiration, InspirationReflection,
                               InspirationSave)

from .authentication import IsMember, MobileTokenAuthentication

RELATED_LIMIT = 4

# Templates the app can render. Kept server-side so a new style can be
# switched off without an app release; the artwork itself ships with the app.
SHARE_TEMPLATES = [
    {'id': 'cosmic', 'name': 'Cosmic', 'recommended_text_color': 'light',
     'formats': ['square', 'story'], 'enabled': True},
    {'id': 'dawn', 'name': 'Dawn', 'recommended_text_color': 'light',
     'formats': ['square'], 'enabled': True},
    {'id': 'stillness', 'name': 'Stillness', 'recommended_text_color': 'light',
     'formats': ['square'], 'enabled': True},
    {'id': 'light', 'name': 'Light', 'recommended_text_color': 'dark',
     'formats': ['square'], 'enabled': True},
]
DEFAULT_TEMPLATE_ID = 'cosmic'
# An editorially safe share length — never the whole reflection.
SHARE_EXCERPT_LIMIT = 220


def _published():
    return DailyInspiration.objects.filter(
        is_published=True, date__lte=timezone.localdate())


def _lookup(identifier):
    """Accept either the numeric id or the slug, so deep links work both
    ways."""
    query = Q(slug=identifier)
    if str(identifier).isdigit():
        query |= Q(pk=int(identifier))
    return _published().filter(query).first()


def _canonical_url(inspiration):
    base = settings.PUBLIC_SITE_URL.rstrip('/')
    return f'{base}/inspirations/{inspiration.slug}'


def _block_json(block):
    return {
        'id': block.id,
        'type': block.block_type,
        'text': block.text,
        'source': block.source,
        'image_url': block.image.url if block.image else '',
        'alt_text': block.alt_text,
        'caption': block.caption,
        'items': block.items or [],
        'sort_order': block.order,
    }


def _summary_json(inspiration, saved_ids):
    return {
        'id': inspiration.id,
        'slug': inspiration.slug,
        'category': inspiration.category,
        'title': inspiration.display_title,
        'image_url': (inspiration.hero_image.url
                      if inspiration.hero_image else ''),
        'published_at': inspiration.date.isoformat(),
        'reading_time_minutes': inspiration.reading_time_minutes(),
        'saved': inspiration.id in saved_ids,
    }


class InspirationDetailView(APIView):
    """GET /inspirations/<id-or-slug>/ — the full reading payload.

    Public: a shared link opens without a token. When a token is present the
    payload also carries this member's saved and reflected state.
    """

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, identifier):
        inspiration = _lookup(identifier)
        if inspiration is None:
            return Response(
                {'detail': 'This inspiration is no longer available.'},
                status=404)

        token = getattr(request, 'auth', None)
        contact = token.contact if token is not None else None

        saved = reflected = False
        reflected_at = None
        saved_ids = set()
        if contact is not None:
            saved = InspirationSave.objects.filter(
                contact=contact, inspiration=inspiration).exists()
            reflection = InspirationReflection.objects.filter(
                contact=contact, inspiration=inspiration).first()
            reflected = reflection is not None
            reflected_at = (reflection.reflected_at.isoformat()
                            if reflection else None)

        # Related: other published entries, current one excluded.
        related = list(
            _published().exclude(pk=inspiration.pk)
            .order_by('-date')[:RELATED_LIMIT])
        if contact is not None:
            saved_ids = set(
                InspirationSave.objects.filter(
                    contact=contact,
                    inspiration__in=[r.id for r in related] or [0])
                .values_list('inspiration_id', flat=True))

        # Previous/next come from the server's own ordering, never inferred
        # on the client.
        previous = _published().filter(date__lt=inspiration.date).first()
        nxt = (_published().filter(date__gt=inspiration.date)
               .order_by('date').first())

        prompt = None
        if inspiration.prompt_question or inspiration.reflection:
            prompt = {
                'id': inspiration.id,
                'question': (inspiration.prompt_question
                             or inspiration.reflection),
                'guidance': inspiration.prompt_guidance,
                'status': 'reflected' if reflected else 'open',
            }

        audio = None
        if inspiration.resolved_audio_url:
            audio = {
                'url': inspiration.resolved_audio_url,
                'duration_seconds': inspiration.audio_duration_seconds,
                'title': inspiration.display_title,
            }

        return Response({
            'id': inspiration.id,
            'slug': inspiration.slug,
            'category': inspiration.category,
            'title': inspiration.display_title,
            'primary_quote': inspiration.quote,
            'share_excerpt': inspiration.share_excerpt or inspiration.quote,
            'author': inspiration.author or None,
            'published_at': inspiration.date.isoformat(),
            'reading_time_minutes': inspiration.reading_time_minutes(),
            'hero_image': {
                'url': (inspiration.hero_image.url
                        if inspiration.hero_image else ''),
                'alt_text': inspiration.hero_alt_text,
            },
            'body_blocks': [
                _block_json(b) for b in inspiration.blocks.all()],
            'reflection_prompt': prompt,
            'audio': audio,
            'saved': saved,
            'reflected': reflected,
            'reflected_at': reflected_at,
            'sharing_allowed': inspiration.sharing_allowed,
            'canonical_url': _canonical_url(inspiration),
            'related_inspirations': [
                _summary_json(r, saved_ids) for r in related],
            'previous_inspiration': (
                _summary_json(previous, saved_ids) if previous else None),
            'next_inspiration': (
                _summary_json(nxt, saved_ids) if nxt else None),
            'updated_at': inspiration.updated_at.isoformat(),
        })


class InspirationSaveView(APIView):
    """POST/DELETE /inspirations/<id-or-slug>/save/ — members only."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]

    def post(self, request, identifier):
        inspiration = _lookup(identifier)
        if inspiration is None:
            return Response({'detail': 'Not found.'}, status=404)
        InspirationSave.objects.get_or_create(
            contact=request.member, inspiration=inspiration)
        return Response({'saved': True}, status=201)

    def delete(self, request, identifier):
        inspiration = _lookup(identifier)
        if inspiration is None:
            return Response({'detail': 'Not found.'}, status=404)
        InspirationSave.objects.filter(
            contact=request.member, inspiration=inspiration).delete()
        return Response({'saved': False})


class InspirationReflectionView(APIView):
    """POST/DELETE /inspirations/<id-or-slug>/reflection/ — members only.

    Records only that the member reflected; no written response is stored.
    """

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]

    def post(self, request, identifier):
        inspiration = _lookup(identifier)
        if inspiration is None:
            return Response({'detail': 'Not found.'}, status=404)
        reflection, _ = InspirationReflection.objects.get_or_create(
            contact=request.member, inspiration=inspiration)
        return Response(
            {'reflected': True,
             'reflected_at': reflection.reflected_at.isoformat()},
            status=201)

    def delete(self, request, identifier):
        inspiration = _lookup(identifier)
        if inspiration is None:
            return Response({'detail': 'Not found.'}, status=404)
        InspirationReflection.objects.filter(
            contact=request.member, inspiration=inspiration).delete()
        return Response({'reflected': False})


class InspirationShareDataView(APIView):
    """GET /inspirations/<id-or-slug>/share-data/ — just what a share card
    needs. Public: guests may share a public inspiration."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, identifier):
        inspiration = _lookup(identifier)
        if inspiration is None:
            return Response(
                {'detail': 'This inspiration is no longer available.'},
                status=404)

        excerpt = (inspiration.share_excerpt or inspiration.quote).strip()
        if len(excerpt) > SHARE_EXCERPT_LIMIT:
            # Trim on a word boundary rather than mid-word.
            excerpt = excerpt[:SHARE_EXCERPT_LIMIT].rsplit(' ', 1)[0] + '\u2026'

        return Response({
            'inspiration_id': inspiration.id,
            'slug': inspiration.slug,
            'share_excerpt': excerpt,
            'author': inspiration.author or None,
            'source': inspiration.category or None,
            'published_at': inspiration.date.isoformat(),
            'canonical_url': _canonical_url(inspiration),
            'sharing_allowed': inspiration.sharing_allowed,
            'default_template_id': DEFAULT_TEMPLATE_ID,
            'templates': SHARE_TEMPLATES,
            'official_website_label': settings.PUBLIC_SITE_URL
                .replace('https://', '').replace('http://', '').rstrip('/'),
        })
