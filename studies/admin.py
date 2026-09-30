from django.contrib import admin

from .models import Enrolment, Mentorship, Milestone, PracticeAssignment


@admin.register(Enrolment)
class EnrolmentAdmin(admin.ModelAdmin):
    list_display = ['contact', 'program', 'cohort', 'status', 'is_primary']
    list_filter = ['status', 'is_primary', 'program']
    raw_id_fields = ['contact']


@admin.register(PracticeAssignment)
class PracticeAssignmentAdmin(admin.ModelAdmin):
    list_display = ['contact', 'practice', 'due_at', 'completed_at', 'required']
    list_filter = ['required', 'excused']
    raw_id_fields = ['contact']


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ['title', 'program', 'required_progress', 'is_active']
    list_filter = ['program', 'is_active']


@admin.register(Mentorship)
class MentorshipAdmin(admin.ModelAdmin):
    list_display = ['student', 'mentor', 'next_check_in_at', 'is_active']
    list_filter = ['is_active', 'messaging_enabled']
    raw_id_fields = ['student']
