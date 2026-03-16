from django.contrib import admin
from .models import Worker, Representative


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ('contact', 'role', 'salary')
    search_fields = ('contact__full_name',)


@admin.register(Representative)
class RepresentativeAdmin(admin.ModelAdmin):
    list_display = ('contact', 'country', 'region')
