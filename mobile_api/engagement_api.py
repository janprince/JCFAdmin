"""Mobile engagement API: announcements, daily inspiration, push device
tokens, notifications, appointments."""
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from consultations.models import Consultation
from engagement.models import (Announcement, AnnouncementRead,
                               DailyInspiration, DeviceToken, Notification)
from .authentication import IsMember, MobileTokenAuthentication


def allowed_audience_values(contact):
    values = {Announcement.Audience.PUBLIC}
    if contact is not None:
        if contact.is_member or contact.is_student:
            values.add(Announcement.Audience.MEMBERS)
        if contact.is_student:
            values.add(Announcement.Audience.STUDENTS)
    return values


# --- Serializers ---

class AnnouncementSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'body', 'audience', 'image_url', 'pinned',
                  'is_read', 'created_at']

    def get_image_url(self, obj):
        return obj.image.url if obj.image else ''

    def get_is_read(self, obj):
        # Guests carry no read state, so they see no unread dots.
        read_ids = self.context.get('read_ids')
        return True if read_ids is None else obj.id in read_ids


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'data', 'is_read', 'created_at']


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultation
        fields = ['id', 'mode', 'scheduled_date', 'status', 'note', 'created_at']
        read_only_fields = ['status', 'created_at']

    def validate_mode(self, value):
        if value not in Consultation.Mode.values:
            raise serializers.ValidationError('Invalid mode.')
        return value


# --- Views ---

class AnnouncementListView(generics.ListAPIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        contact = self.request.auth.contact if self.request.auth else None
        return Announcement.objects.filter(
            is_published=True, audience__in=allowed_audience_values(contact)
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        contact = self.request.auth.contact if self.request.auth else None
        if contact is not None:
            context['read_ids'] = set(
                AnnouncementRead.objects.filter(contact=contact)
                .values_list('announcement_id', flat=True))
        return context


class AnnouncementReadView(APIView):
    """POST /announcements/<pk>/read/ — clear the unread dot."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]

    def post(self, request, pk):
        announcement = Announcement.objects.filter(
            pk=pk, is_published=True).first()
        if announcement is None:
            return Response({'detail': 'Not found.'}, status=404)
        AnnouncementRead.objects.get_or_create(
            contact=request.member, announcement=announcement)
        return Response({'is_read': True})


class DeviceRegisterView(APIView):
    """POST {token, platform} -> register/refresh an FCM token (links member if authed)."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        token = str(request.data.get('token', '')).strip()
        platform = request.data.get('platform')
        if not token or platform not in DeviceToken.Platform.values:
            raise ValidationError('token and a valid platform (ios/android) are required.')
        contact = request.auth.contact if request.auth else None
        DeviceToken.objects.update_or_create(
            token=token,
            defaults={'platform': platform, 'contact': contact, 'is_active': True},
        )
        return Response({'registered': True}, status=status.HTTP_200_OK)


class DeviceUnregisterView(APIView):
    """DELETE /devices/<token>/ -> deactivate a token (e.g. on logout)."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]

    def delete(self, request, token):
        DeviceToken.objects.filter(token=token).update(is_active=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationListView(generics.ListAPIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(contact=self.request.auth.contact)


class NotificationReadView(APIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]

    def post(self, request, pk):
        updated = Notification.objects.filter(
            pk=pk, contact=request.auth.contact, read_at__isnull=True
        ).update(read_at=timezone.now())
        return Response({'updated': bool(updated)})


class AppointmentListView(generics.ListAPIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        return Consultation.objects.filter(contact=self.request.auth.contact)


class AppointmentCreateView(generics.CreateAPIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]
    serializer_class = AppointmentSerializer

    def perform_create(self, serializer):
        serializer.save(
            contact=self.request.auth.contact,
            status=Consultation.Status.REQUESTED,
        )


class InspirationSerializer(serializers.ModelSerializer):
    related_teaching = serializers.SerializerMethodField()

    class Meta:
        model = DailyInspiration
        fields = ['id', 'date', 'quote', 'author', 'reflection', 'related_teaching']

    def get_related_teaching(self, obj):
        teaching = obj.related_teaching
        if teaching is None or teaching.status != teaching.Status.PUBLISHED:
            return None
        return {'slug': teaching.slug, 'topic': teaching.topic}


class InspirationTodayView(APIView):
    """Today's inspiration (or the most recent published past entry) for the
    Home hero and inspiration page (designs 19/22). Public."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        entry = (
            DailyInspiration.objects.filter(
                is_published=True, date__lte=timezone.localdate())
            .select_related('related_teaching')
            .order_by('-date')
            .first()
        )
        if entry is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(InspirationSerializer(entry).data)


class InspirationRecentView(APIView):
    """The last few published inspirations, newest first — the Home hero
    carousel (design 19). Public."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        entries = (
            DailyInspiration.objects.filter(
                is_published=True, date__lte=timezone.localdate())
            .select_related('related_teaching')
            .order_by('-date')[:3]
        )
        return Response(
            {'results': [InspirationSerializer(e).data for e in entries]})
