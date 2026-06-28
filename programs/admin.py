from django.contrib import admin

from .models import AccommodationTier, CostLineItem, Program, Registration


class AccommodationTierInline(admin.TabularInline):
    model = AccommodationTier
    extra = 0


class CostLineItemInline(admin.TabularInline):
    model = CostLineItem
    extra = 0


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'audience', 'requires_payment', 'is_published')
    list_filter = ('audience', 'requires_payment', 'is_published', 'year')
    search_fields = ('title',)
    prepopulated_fields = {'slug': ('title',)}
    inlines = [CostLineItemInline, AccommodationTierInline]


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('reference', 'program', 'contact', 'quantity', 'amount', 'status', 'created_at')
    list_filter = ('status', 'program')
    search_fields = ('reference', 'contact__full_name', 'paystack_reference')
    readonly_fields = ('reference', 'qr', 'created_at', 'confirmed_at')
