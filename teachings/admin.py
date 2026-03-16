from django.contrib import admin
from .models import Teaching


@admin.register(Teaching)
class TeachingAdmin(admin.ModelAdmin):
    list_display = ('topic', 'format', 'language', 'status')
    list_filter = ('format', 'language', 'status')
    search_fields = ('topic',)
