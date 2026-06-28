"""
Mobile content API: teachings (lessons) + series.

Access tiers:
- General teachings are visible to everyone (guests included).
- Premium teachings are listed to guests as *locked* (teaser) with no media,
  and only members/students can open them.

These views authenticate with MobileTokenAuthentication but allow anonymous
access (AllowAny); membership only controls premium unlocking.
"""
from rest_framework import generics, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from teachings.models import Teaching, TeachingSeries
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
            'id', 'slug', 'topic', 'format', 'language', 'tier', 'media_kind',
            'duration_seconds', 'thumbnail_url', 'series', 'is_locked',
        ]

    def get_is_locked(self, obj):
        return obj.is_premium and not self.context.get('can_premium', False)

    def get_thumbnail_url(self, obj):
        return obj.thumbnail.url if obj.thumbnail else ''


class TeachingDetailSerializer(TeachingListSerializer):
    media_url = serializers.SerializerMethodField()

    class Meta(TeachingListSerializer.Meta):
        fields = TeachingListSerializer.Meta.fields + [
            'description', 'youtube_url', 'media_url', 'created_at',
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
            raise PermissionDenied('This lesson is for registered members or students.')
        return Response(self.get_serializer(obj).data)


class SeriesListView(PremiumContextMixin, generics.ListAPIView):
    serializer_class = SeriesSerializer
    queryset = TeachingSeries.objects.filter(is_published=True)


class SeriesDetailView(PremiumContextMixin, generics.RetrieveAPIView):
    serializer_class = SeriesDetailSerializer
    lookup_field = 'slug'
    queryset = TeachingSeries.objects.filter(is_published=True)
