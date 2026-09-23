from datetime import date, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from accounts.access import areas_for
from members.models import Contact
from consultations.models import Consultation
from teachings.models import Teaching
from causes.models import Donation
from events.models import Event
from blog.models import Post
from website.models import ContactSubmission, VolunteerApplication, JoinCentreRequest


class AnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        access = areas_for(self.request.user)
        today = timezone.localdate()
        month_start = today.replace(day=1)
        if 'community' in access:
            contact_counts = Contact.objects.aggregate(
                total=Count('pk'), members=Count('pk', filter=Q(is_member=True, is_active=True)),
                students=Count('pk', filter=Q(is_student=True, is_active=True)),
            )
            context.update(contact_count=contact_counts['total'], member_count=contact_counts['members'], student_count=contact_counts['students'])
        if 'giving' in access:
            completed_this_month = Donation.objects.filter(status=Donation.Status.COMPLETED, donated_at__date__gte=month_start, donated_at__date__lte=today)
            context['giving_by_currency'] = list(completed_this_month.order_by('currency').values('currency').annotate(total=Sum('amount'), count=Count('pk')))
            context['monthly_donation_count'] = completed_this_month.count()
            context['general_donation_count'] = completed_this_month.filter(cause__isnull=True).count()
            context['giving_month'] = today
        if 'inbox' in access:
            tasks = [
                ('Contact messages', 'Unread messages from the public website', 'envelope-simple', ContactSubmission.objects.filter(is_read=False).count(), reverse('website:contact_list') + '?status=unread'),
                ('Centre join requests', 'People waiting to connect with a centre', 'users-three', JoinCentreRequest.objects.filter(status='pending').count(), reverse('website:join_request_list') + '?status=pending'),
                ('Volunteer applications', 'Offers of time and skills to review', 'hand-heart', VolunteerApplication.objects.filter(status='pending').count(), reverse('website:volunteer_app_list') + '?status=pending'),
            ]
            context['inbox_count'] = sum(item[3] for item in tasks)
            context['inbox_tasks'] = [{'title': title, 'description': description, 'icon': icon, 'count': count, 'url': url} for title, description, icon, count, url in tasks]
        if 'giving' in access:
            context['pending_donation_count'] = Donation.objects.filter(status='pending').count()
        if 'consultations' in access:
            context['overdue_consultation_count'] = Consultation.objects.filter(done=False, scheduled_date__lt=today).count()
            context['upcoming_consultations'] = Consultation.objects.filter(done=False, scheduled_date__gte=today, scheduled_date__lte=today + timedelta(days=7)).select_related('contact').order_by('scheduled_date', 'pk')[:5]
            context['today_consultation_count'] = Consultation.objects.filter(done=False, scheduled_date=today).count()
        if 'publishing' in access:
            # Multi-day events stay current through their final day.
            events = Event.objects.filter(is_published=True).filter(Q(end_date__gte=today) | Q(end_date__isnull=True, date__gte=today))
            context['upcoming_events'] = events.order_by('date', 'time')[:3]
            context['upcoming_event_count'] = events.count()
            context['draft_post_count'] = Post.objects.filter(status='draft').count()
            context['draft_event_count'] = Event.objects.filter(is_published=False).count()
            context['pending_teaching_count'] = Teaching.objects.filter(status='pending').count()
        if 'community' in access:
            context['recent_contacts'] = Contact.objects.order_by('-created_at', '-pk')[:4]

            year, month = today.year, today.month
            months = []
            for _ in range(6):
                months.append((year, month))
                year, month = (year, month - 1) if month > 1 else (year - 1, 12)
            months.reverse()
            monthly = (Contact.objects.filter(created_at__date__gte=date(*months[0], 1), created_at__date__lte=today)
                       .annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('pk')).order_by('month'))
            per_month = {(row['month'].year, row['month'].month): row['count'] for row in monthly}
            maximum = max(per_month.values(), default=1) or 1
            context['contact_trend'] = [{'month': date(y, m, 1), 'count': per_month.get((y, m), 0), 'width': round(100 * per_month.get((y, m), 0) / maximum)} for y, m in months]
        return context
