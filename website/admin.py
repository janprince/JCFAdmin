from django.contrib import admin
from .models import (
    GalleryItem, VolunteerOpportunity, Testimonial, TeamMember,
    ImpactStat, ContactSubmission, VolunteerApplication,
    JoinCentreRequest, NewsletterSubscriber,
)


@admin.register(GalleryItem)
class GalleryItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'category', 'date', 'is_published')
    list_filter = ('type', 'category', 'is_published')
    search_fields = ('title',)
    date_hierarchy = 'date'


@admin.register(VolunteerOpportunity)
class VolunteerOpportunityAdmin(admin.ModelAdmin):
    list_display = ('title', 'location', 'commitment', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('title', 'location')


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'is_published', 'order')
    list_filter = ('is_published',)
    search_fields = ('name', 'role')
    list_editable = ('order', 'is_published')


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'role')
    list_editable = ('order', 'is_active')


@admin.register(ImpactStat)
class ImpactStatAdmin(admin.ModelAdmin):
    list_display = ('label', 'value', 'prefix', 'suffix', 'order')
    list_editable = ('value', 'order')


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('name', 'email', 'subject')
    readonly_fields = ('name', 'email', 'subject', 'message', 'created_at')


@admin.register(VolunteerApplication)
class VolunteerApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'email')


@admin.register(JoinCentreRequest)
class JoinCentreRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'centre', 'status', 'created_at')
    list_filter = ('status', 'centre')
    search_fields = ('name', 'email')


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_active', 'subscribed_at')
    list_filter = ('is_active',)
    search_fields = ('email',)
