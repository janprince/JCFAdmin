from django.contrib import admin

from .models import AccessGrantLog


@admin.register(AccessGrantLog)
class AccessGrantLogAdmin(admin.ModelAdmin):
    """Read-only view of the audit trail. Entries are written by the service
    layer only — nothing here should ever be edited by hand."""

    list_display = ('created_at', 'action', 'student_email', 'performed_by', 'amount', 'currency')
    list_filter = ('action', 'created_at')
    search_fields = ('student_email', 'student_id', 'receipt_ref')
    readonly_fields = [field.name for field in AccessGrantLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
