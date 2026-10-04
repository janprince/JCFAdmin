from django.contrib import admin
from .models import Representative, ServiceEntry, ServiceUnit, Worker


@admin.register(ServiceUnit)
class ServiceUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'lead', 'portal_roles', 'is_active')


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ('contact', 'title', 'unit', 'service_type', 'status', 'allowance', 'allowance_currency', 'started_on')
    list_filter = ('status', 'service_type', 'unit')
    search_fields = ('contact__full_name', 'title', 'skills')
    filter_horizontal = ('other_units',)


@admin.register(ServiceEntry)
class ServiceEntryAdmin(admin.ModelAdmin):
    list_display = ('worker', 'kind', 'occurred_on', 'recorded_by')
    list_filter = ('kind',)


@admin.register(Representative)
class RepresentativeAdmin(admin.ModelAdmin):
    list_display = ('contact', 'country', 'region')
