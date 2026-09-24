from django.contrib import admin

from .models import LoginCode, MobileToken


@admin.register(LoginCode)
class LoginCodeAdmin(admin.ModelAdmin):
    list_display = ('contact', 'channel', 'destination', 'attempts', 'consumed_at', 'created_at')
    list_filter = ('channel',)
    search_fields = ('contact__full_name', 'destination')
    readonly_fields = ('code_hash', 'created_at')


@admin.register(MobileToken)
class MobileTokenAdmin(admin.ModelAdmin):
    list_display = ('contact', 'revoked', 'access_expires_at', 'refresh_expires_at', 'last_used_at', 'created_at')
    list_filter = ('revoked',)
    search_fields = ('contact__full_name',)
    readonly_fields = ('access_token', 'refresh_token', 'created_at', 'last_used_at')
