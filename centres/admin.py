from django.contrib import admin
from .models import Centre


@admin.register(Centre)
class CentreAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'country', 'leader_name', 'member_count', 'is_active')
    list_filter = ('country', 'is_active')
    search_fields = ('name', 'location', 'country', 'leader_name')
    prepopulated_fields = {'slug': ('name',)}
