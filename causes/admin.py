from django.contrib import admin
from .models import CauseCategory, Cause, Donation


@admin.register(CauseCategory)
class CauseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Cause)
class CauseAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'category', 'goal_amount', 'raised_amount', 'is_active', 'created_at')
    list_filter = ('is_active', 'type', 'category', 'currency')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ('donor_name', 'amount', 'currency', 'method', 'cause', 'status', 'donated_at')
    list_filter = ('status', 'method', 'currency', 'cause')
    search_fields = ('donor_name', 'donor_email', 'reference', 'paystack_reference')
    readonly_fields = ('created_at',)
