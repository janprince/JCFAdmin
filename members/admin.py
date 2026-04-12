from django.contrib import admin
from .models import Contact, DataFile, Inquiry


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'centre', 'is_member', 'is_student', 'is_active', 'country')
    list_filter = ('centre', 'is_member', 'is_student', 'is_active', 'gender', 'country')
    search_fields = ('full_name', 'phone')


@admin.register(DataFile)
class DataFileAdmin(admin.ModelAdmin):
    list_display = ('contact', 'file', 'created_at')


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('contact', 'subject', 'created_at')
    search_fields = ('contact__full_name',)
