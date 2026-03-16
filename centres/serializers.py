from rest_framework import serializers
from .models import Centre


class CentreSerializer(serializers.ModelSerializer):
    leader = serializers.SerializerMethodField()
    coordinates = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Centre
        fields = [
            'id', 'name', 'slug', 'location', 'address', 'country',
            'image_url', 'description', 'leader', 'contact_email',
            'contact_phone', 'coordinates', 'member_count', 'is_active',
            'created_at', 'updated_at',
        ]

    def get_leader(self, obj):
        return {
            'name': obj.leader_name,
            'title': obj.leader_title,
            'avatar': self._get_file_url(obj.leader_avatar),
        }

    def get_coordinates(self, obj):
        if obj.latitude is not None and obj.longitude is not None:
            return {
                'lat': float(obj.latitude),
                'lng': float(obj.longitude),
            }
        return None

    def get_image_url(self, obj):
        return self._get_file_url(obj.image)

    def _get_file_url(self, field):
        if field:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(field.url)
            return field.url
        return None


class CentreListSerializer(serializers.ModelSerializer):
    leader = serializers.SerializerMethodField()
    coordinates = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Centre
        fields = [
            'id', 'name', 'slug', 'location', 'country', 'image_url',
            'leader', 'coordinates', 'member_count', 'is_active',
        ]

    def get_leader(self, obj):
        return {
            'name': obj.leader_name,
            'title': obj.leader_title,
            'avatar': obj.leader_avatar.url if obj.leader_avatar else None,
        }

    def get_coordinates(self, obj):
        if obj.latitude is not None and obj.longitude is not None:
            return {
                'lat': float(obj.latitude),
                'lng': float(obj.longitude),
            }
        return None

    def get_image_url(self, obj):
        return obj.image.url if obj.image else None
