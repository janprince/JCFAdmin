"""Mobile engagement API: announcements, push device tokens, notifications, appointments."""
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from consultations.models import Consultation
from engagement.models import Announcement, DeviceToken, Notification
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

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'body', 'audience', 'image_url', 'pinned', 'created_at']

    def get_image_url(self, obj):
        return obj.image.url if obj.image else ''


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
