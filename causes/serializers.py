from rest_framework import serializers
from .models import CauseCategory, Cause, Donation


class CauseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CauseCategory
        fields = ['id', 'name', 'slug']


class CauseSerializer(serializers.ModelSerializer):
    raised_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    donors_count = serializers.IntegerField(read_only=True)
    progress_percent = serializers.IntegerField(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Cause
        fields = [
            'id', 'title', 'slug', 'description', 'content', 'image', 'image_url',
            'gallery', 'goal_amount', 'currency', 'category', 'category_name',
            'is_active', 'raised_amount', 'donors_count', 'progress_percent',
            'created_at', 'updated_at',
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class CauseListSerializer(serializers.ModelSerializer):
    raised_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    progress_percent = serializers.IntegerField(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Cause
        fields = [
            'id', 'title', 'slug', 'description', 'image_url',
            'goal_amount', 'currency', 'category_name',
            'is_active', 'raised_amount', 'progress_percent',
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class DonationSerializer(serializers.ModelSerializer):
    cause_title = serializers.CharField(source='cause.title', read_only=True, default=None)

    class Meta:
        model = Donation
        fields = [
            'id', 'cause', 'cause_title', 'donor_name', 'donor_email',
            'donor_phone', 'amount', 'currency', 'method', 'status',
            'reference', 'paystack_reference', 'notes', 'is_anonymous',
            'donated_at', 'created_at',
        ]
