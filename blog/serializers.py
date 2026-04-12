from rest_framework import serializers
from .models import Author, Category, Tag, Post


class AuthorSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Author
        fields = ['id', 'name', 'avatar_url', 'role']

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']


class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    tags = serializers.SlugRelatedField(many=True, read_only=True, slug_field='name')
    read_time = serializers.CharField(read_only=True)
    image_url = serializers.SerializerMethodField()
    published_date = serializers.DateTimeField(format='%Y-%m-%d', read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'excerpt', 'content',
            'image_url', 'video_link', 'author', 'category_name', 'tags',
            'status', 'published_date', 'read_time',
            'created_at', 'updated_at',
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class PostListSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    tags = serializers.SlugRelatedField(many=True, read_only=True, slug_field='name')
    read_time = serializers.CharField(read_only=True)
    image_url = serializers.SerializerMethodField()
    published_date = serializers.DateTimeField(format='%Y-%m-%d', read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'excerpt',
            'image_url', 'video_link', 'author', 'category_name', 'tags',
            'status', 'published_date', 'read_time',
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
