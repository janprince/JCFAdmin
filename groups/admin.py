from django.contrib import admin

from .models import Group, GroupMembership


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    raw_id_fields = ['contact']
    readonly_fields = ['requested_at', 'decided_at', 'decided_by']


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'centre', 'capacity', 'is_active', 'created_at']
    list_filter = ['is_active', 'centre']
    search_fields = ['name']
    inlines = [GroupMembershipInline]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ['contact', 'group', 'status', 'requested_at', 'decided_at']
    list_filter = ['status', 'group']
    search_fields = ['contact__full_name', 'contact__email']
    raw_id_fields = ['contact']
