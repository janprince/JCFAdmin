"""
Mobile content API: teachings (lessons) + series.

Access tiers:
- General teachings are visible to everyone (guests included).
- Premium teachings are listed to guests as *locked* (teaser) with no media,
  and only members/students can open them.

These views authenticate with MobileTokenAuthentication but allow anonymous
access (AllowAny); membership only controls premium unlocking.
"""
from django.utils.translation import gettext as _
from django.db.models import F
from rest_framework import generics, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from teachings.models import Teaching, TeachingProgress, TeachingSeries
from .authentication import MobileTokenAuthentication


def _can_premium(request) -> bool:
    """True if the request carries a valid token for an active member/student."""
    token = getattr(request, 'auth', None)
    if token is None:
        return False
    contact = token.contact
    return bool(contact.is_active and (contact.is_member or contact.is_student))


class PremiumContextMixin:
    """Adds `can_premium` to serializer context and authenticates (optionally)."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['can_premium'] = _can_premium(self.request)
        return ctx


# --- Serializers ---

class TeachingListSerializer(serializers.ModelSerializer):
    is_locked = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    series = serializers.SlugRelatedField(slug_field='slug', read_only=True)

    class Meta:
        model = Teaching
        fields = [
            'id', 'slug', 'topic', 'author', 'description', 'format',
            'language', 'tier', 'media_kind', 'duration_seconds',
            'thumbnail_url', 'series', 'is_locked', 'view_count',
        ]

    def get_is_locked(self, obj):
        return obj.is_premium and not self.context.get('can_premium', False)

    def get_thumbnail_url(self, obj):
        return obj.thumbnail.url if obj.thumbnail else ''


class TeachingDetailSerializer(TeachingListSerializer):
    media_url = serializers.SerializerMethodField()

    class Meta(TeachingListSerializer.Meta):
        fields = TeachingListSerializer.Meta.fields + [
            'youtube_url', 'media_url', 'created_at',
        ]

    def get_media_url(self, obj):
        return obj.media_url  # model property → R2 public URL


class SeriesSerializer(serializers.ModelSerializer):
    cover_url = serializers.SerializerMethodField()
    teaching_count = serializers.SerializerMethodField()

    class Meta:
        model = TeachingSeries
        fields = ['id', 'slug', 'title', 'description', 'cover_url', 'teaching_count']

    def get_cover_url(self, obj):
        return obj.cover.url if obj.cover else ''

    def get_teaching_count(self, obj):
        return obj.teachings.filter(status=Teaching.Status.PUBLISHED).count()


class SeriesDetailSerializer(SeriesSerializer):
    teachings = serializers.SerializerMethodField()

    class Meta(SeriesSerializer.Meta):
        fields = SeriesSerializer.Meta.fields + ['teachings']

    def get_teachings(self, obj):
        qs = obj.teachings.filter(status=Teaching.Status.PUBLISHED)
        return TeachingListSerializer(qs, many=True, context=self.context).data


# --- Views ---

class TeachingListView(PremiumContextMixin, generics.ListAPIView):
    serializer_class = TeachingListSerializer

    def get_queryset(self):
        qs = Teaching.objects.filter(status=Teaching.Status.PUBLISHED).select_related('series')
        p = self.request.query_params
        if p.get('series'):
            qs = qs.filter(series__slug=p['series'])
        if p.get('format'):
            qs = qs.filter(format=p['format'])
        if p.get('language'):
            qs = qs.filter(language=p['language'])
        if p.get('tier'):
            qs = qs.filter(tier=p['tier'])
        if p.get('search'):
            qs = qs.filter(topic__icontains=p['search'])
        return qs


class TeachingDetailView(PremiumContextMixin, generics.RetrieveAPIView):
    serializer_class = TeachingDetailSerializer
    lookup_field = 'slug'
    queryset = Teaching.objects.filter(status=Teaching.Status.PUBLISHED).select_related('series')

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.is_premium and not _can_premium(request):
            raise PermissionDenied(_('This lesson is for registered members or students.'))
        # Count the open, and record it in the member's viewing history.
        Teaching.objects.filter(pk=obj.pk).update(view_count=F('view_count') + 1)
        token = getattr(request, 'auth', None)
        if token is not None:
            TeachingProgress.objects.update_or_create(
                contact=token.contact, teaching=obj)
        return Response(self.get_serializer(obj).data)


class SeriesListView(PremiumContextMixin, generics.ListAPIView):
    serializer_class = SeriesSerializer
    queryset = TeachingSeries.objects.filter(is_published=True)


class SeriesDetailView(PremiumContextMixin, generics.RetrieveAPIView):
    serializer_class = SeriesDetailSerializer
    lookup_field = 'slug'
    queryset = TeachingSeries.objects.filter(is_published=True)


# --- Continue Learning (design 26) ---

from rest_framework.views import APIView  # noqa: E402
from .authentication import IsStudentOrMember  # noqa: E402


class TeachingProgressView(APIView):
    """POST /teachings/<slug>/progress/ {percent?, position_seconds?,
    completed?} — upsert the member's progress in a teaching."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsStudentOrMember]

    def post(self, request, slug):
        try:
            teaching = Teaching.objects.get(
                slug=slug, status=Teaching.Status.PUBLISHED)
        except Teaching.DoesNotExist:
            return Response(status=404)

        progress, _created = TeachingProgress.objects.get_or_create(
            contact=request.member, teaching=teaching)
        data = request.data
        if 'percent' in data:
            progress.percent = max(0, min(100, int(data['percent'] or 0)))
        if 'position_seconds' in data:
            progress.position_seconds = int(data['position_seconds'] or 0)
        if 'completed' in data:
            progress.completed = bool(data['completed'])
            if progress.completed:
                progress.percent = 100
        progress.save()
        return Response({
            'percent': progress.percent,
            'completed': progress.completed,
        })


class ContinueLearningView(APIView):
    """GET /learning/continue/ — the member's Continue Learning summary:
    per-series progress cards + recently viewed (design 26)."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsStudentOrMember]

    def get(self, request):
        contact = request.member
        rows = (
            TeachingProgress.objects.filter(contact=contact)
            .select_related('teaching', 'teaching__series')
            .order_by('-last_viewed_at')
        )
        completed_ids = {r.teaching_id for r in rows if r.completed}

        # Per-series cards, ordered by most recent activity in the series.
        series_cards, seen = [], set()
        for row in rows:
            series = row.teaching.series
            if series is None or series.id in seen or not series.is_published:
                continue
            seen.add(series.id)
            lessons = list(
                series.teachings.filter(status=Teaching.Status.PUBLISHED)
                .order_by('order', 'id'))
            total = len(lessons)
            done = sum(1 for lesson in lessons if lesson.id in completed_ids)
            # Resume target: the most recent non-completed lesson viewed in
            # this series, else the first not-completed lesson.
            resume = next(
                (r.teaching for r in rows
                 if r.teaching.series_id == series.id and not r.completed),
                next((l for l in lessons if l.id not in completed_ids), None),
            )
            series_cards.append({
                'slug': series.slug,
                'title': series.title,
                'author': resume.author if resume else (
                    lessons[0].author if lessons else ''),
                'percent': round(done * 100 / total) if total else 0,
                'lessons_total': total,
                'lessons_done': done,
                'current_lesson': min(done + 1, total) if total else 0,
                'resume_slug': resume.slug if resume else None,
                'cover_url': series.cover.url if series.cover else '',
            })

        recently = [{
            'slug': r.teaching.slug,
            'topic': r.teaching.topic,
            'series_title': r.teaching.series.title if r.teaching.series else None,
            'media_kind': r.teaching.media_kind,
            'duration_seconds': r.teaching.duration_seconds,
            'thumbnail_url': r.teaching.thumbnail.url if r.teaching.thumbnail else '',
            'completed': r.completed,
            'last_viewed_at': r.last_viewed_at,
        } for r in rows[:10]]

        return Response({
            'active_series': len(series_cards),
            'lessons_completed': len(completed_ids),
            'series': series_cards,
            'recently_viewed': recently,
        })
