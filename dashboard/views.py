import json
from datetime import date, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.views.generic import TemplateView

from members.models import Contact
from consultations.models import Consultation
from staff_mgmt.models import Worker
from teachings.models import Teaching


class AnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Counts
        context['contact_count'] = Contact.objects.count()
        context['member_count'] = Contact.objects.filter(is_member=True).count()
        context['student_count'] = Contact.objects.filter(is_student=True).count()
        context['consultation_count'] = Consultation.objects.filter(done=False).count()
        context['staff_count'] = Worker.objects.count()
        context['teaching_count'] = Teaching.objects.count()

        # Today's consultations
        context['todays_consultations'] = (
            Consultation.objects.filter(scheduled_date=date.today(), done=False)
            .select_related('contact')
        )

        # Upcoming consultations (next 7 days)
        context['upcoming_consultations'] = (
            Consultation.objects.filter(
                scheduled_date__gte=date.today(),
                scheduled_date__lte=date.today() + timedelta(days=7),
                done=False,
            )
            .select_related('contact')
            .order_by('scheduled_date')[:10]
        )

        # Recent contacts added (last 5)
        context['recent_contacts'] = Contact.objects.order_by('-id')[:5]

        # Monthly registrations for chart (last 6 months)
        six_months_ago = date.today() - timedelta(days=180)
        monthly = (
            Contact.objects.filter(created_at__date__gte=six_months_ago)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        chart_labels = [m['month'].strftime('%b %Y') for m in monthly]
        chart_data = [m['count'] for m in monthly]
        context['chart_labels'] = json.dumps(chart_labels)
        context['chart_data'] = json.dumps(chart_data)

        # Teachings by status
        context['teachings_published'] = Teaching.objects.filter(status='published').count()
        context['teachings_pending'] = Teaching.objects.filter(status='pending').count()
        context['teachings_archive'] = Teaching.objects.filter(status='archive').count()

        return context
