from rest_framework import serializers
from .models import Event, EventCategory


class EventCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategory
        fields = ['id', 'name', 'slug']


class EventSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    is_past = serializers.BooleanField(read_only=True)
    formatted_time = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'description', 'content',
            'date', 'end_date', 'time', 'formatted_time',
            'location', 'address', 'image', 'image_url',
            'category', 'category_name', 'registration_url',
            'is_published', 'is_past', 'created_at', 'updated_at',
        ]

    def get_formatted_time(self, obj):
        if obj.time:
            return obj.time.strftime('%I:%M %p')
        return None

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
