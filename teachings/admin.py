from django.contrib import admin
from .models import Teaching, TeachingSeries


@admin.register(TeachingSeries)
class TeachingSeriesAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'is_published')
    list_filter = ('is_published',)
    search_fields = ('title',)
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Teaching)
class TeachingAdmin(admin.ModelAdmin):
    list_display = ('topic', 'tier', 'format', 'language', 'status', 'series', 'order')
    list_filter = ('tier', 'format', 'language', 'status', 'series')
    search_fields = ('topic', 'description')
    prepopulated_fields = {'slug': ('topic',)}
    list_editable = ('tier', 'status', 'order')
