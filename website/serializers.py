from rest_framework import serializers
from .models import (
    GalleryItem, VolunteerOpportunity, Testimonial, TeamMember,
    ImpactStat, ContactSubmission, VolunteerApplication,
    JoinCentreRequest, NewsletterSubscriber,
)


class GalleryItemSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = GalleryItem
        fields = [
            'id', 'title', 'description', 'image', 'image_url',
            'thumbnail', 'thumbnail_url', 'video_url',
            'type', 'type_display', 'category', 'category_display',
            'date', 'is_published', 'created_at',
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None


class VolunteerOpportunitySerializer(serializers.ModelSerializer):
    skills = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    class Meta:
        model = VolunteerOpportunity
        fields = [
            'id', 'title', 'description', 'location', 'commitment',
            'skills', 'is_active', 'created_at', 'updated_at',
        ]


class TestimonialSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Testimonial
        fields = [
            'id', 'name', 'role', 'avatar', 'avatar_url',
            'quote', 'is_published', 'order', 'created_at',
        ]

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class TeamMemberSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = TeamMember
        fields = [
            'id', 'name', 'role', 'bio', 'image', 'image_url',
            'order', 'is_active', 'created_at',
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ImpactStatSerializer(serializers.ModelSerializer):
    display = serializers.SerializerMethodField()

    class Meta:
        model = ImpactStat
        fields = ['id', 'label', 'value', 'prefix', 'suffix', 'order', 'display']

    def get_display(self, obj):
        return f'{obj.prefix}{obj.value}{obj.suffix}'


class ContactSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactSubmission
        fields = ['id', 'name', 'email', 'subject', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']


class VolunteerApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VolunteerApplication
        fields = [
            'id', 'name', 'email', 'phone', 'centre_preference',
            'skills', 'availability', 'message', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class JoinCentreRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = JoinCentreRequest
        fields = [
            'id', 'name', 'email', 'phone', 'centre',
            'message', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ['id', 'email', 'subscribed_at']
        read_only_fields = ['id', 'subscribed_at']
