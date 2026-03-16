from django.contrib import admin
from .models import Consultation


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('contact', 'mode', 'scheduled_date', 'done')
    list_filter = ('mode', 'done')
    search_fields = ('contact__full_name',)
