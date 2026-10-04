from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.access import areas_for
from accounts.models import Profile
from dashboard.listing import count_by, tabs
from .forms import ServiceEntryForm, ServiceUnitForm, WorkerForm
from .journey import record_changes, record_joined, snapshot
from .models import ServiceEntry, ServiceUnit, Worker


def manages_accounts(user):
    return 'accounts' in areas_for(user)


def allowed_role_labels(worker):
    allowed = worker.allowed_portal_roles()
    if allowed is None:
        return None
    labels = dict(Profile.Role.choices)
    return [labels[role] for role in allowed]


def with_units(qs):
    return qs.select_related('contact', 'unit', 'portal_profile__user').prefetch_related(
        Prefetch('other_units', queryset=ServiceUnit.objects.order_by('name')))


def allowance_totals(qs):
    """Monthly allowances of `qs`, one row per currency: never add GHS to USD."""
    return list(qs.filter(allowance__gt=0).order_by().values('allowance_currency')
                .annotate(total=Sum('allowance'), people=Count('pk')).order_by('allowance_currency'))


class StaffListView(LoginRequiredMixin, ListView):
    """The service team directory. Opens on the people currently serving."""
    template_name = 'staff/staff_list.html'
    context_object_name = 'staff'
    paginate_by = 50

    def get_queryset(self):
        qs = with_units(Worker.objects.all())
        status = self.request.GET.get('status', 'serving')
        if status == 'serving':
            qs = qs.exclude(status=Worker.Status.INACTIVE)
        elif status in Worker.Status.values:
            qs = qs.filter(status=status)
        query = self.request.GET.get('q', '').strip()
        if query:
            qs = qs.filter(Q(contact__full_name__icontains=query) | Q(title__icontains=query) | Q(skills__icontains=query))
        unit = self.request.GET.get('unit', '')
        if unit.isdigit():
            qs = qs.filter(Q(unit_id=unit) | Q(other_units=unit)).distinct()
        kind = self.request.GET.get('type')
        if kind in Worker.ServiceType.values:
            qs = qs.filter(service_type=kind)
        if self.request.GET.get('support') == 'allowance':
            qs = qs.filter(allowance__gt=0)
        elif self.request.GET.get('support') == 'none':
            qs = qs.filter(Q(allowance__isnull=True) | Q(allowance=0))
        return qs.order_by('contact__full_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        statuses = count_by(Worker.objects.all(), 'status')
        serving = Worker.objects.exclude(status=Worker.Status.INACTIVE)
        today = timezone.localdate()
        context.update(
            tabs=tabs(self.request, 'status', [
                ('serving', 'Serving', statuses.get('active', 0) + statuses.get('on_leave', 0)),
                ('on_leave', 'On leave', statuses.get('on_leave', 0)),
                ('inactive', 'Inactive', statuses.get('inactive', 0)),
                ('all', 'All', sum(statuses.values())),
            ], all_label=None, default='serving'),
            commitment=count_by(serving, 'service_type'),
            serving_count=serving.count(),
            allowances=allowance_totals(serving),
            anniversaries=with_units(serving.filter(started_on__month=today.month, started_on__year__lt=today.year)).order_by('started_on__day'),
            units=ServiceUnit.objects.filter(is_active=True),
            type_choices=Worker.ServiceType.choices,
            search_query=self.request.GET.get('q', ''),
            unit_filter=self.request.GET.get('unit', ''),
            type_filter=self.request.GET.get('type', ''),
            support_filter=self.request.GET.get('support', ''),
            needs_review=[worker for worker in with_units(Worker.objects.filter(portal_profile__isnull=False))
                          if worker.access_concerns()] if manages_accounts(self.request.user) else [],
        )
        for worker in context['anniversaries']:
            worker.years = today.year - worker.started_on.year
        return context


class StaffDetailView(LoginRequiredMixin, DetailView):
    template_name = 'staff/staff_detail.html'
    context_object_name = 'worker'

    def get_queryset(self):
        return with_units(Worker.objects.all())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        worker = self.object
        context.update(
            journey=worker.journey.select_related('recorded_by'),
            entry_form=kwargs.get('entry_form') or ServiceEntryForm(),
            manages_accounts=manages_accounts(self.request.user),
            concerns=worker.access_concerns(),
            allowed_roles=allowed_role_labels(worker),
            units_led=worker.units_led.all(),
            skills=[s.strip() for s in worker.skills.split(',') if s.strip()],
        )
        return context


class WorkerFormMixin(LoginRequiredMixin):
    model = Worker
    form_class = WorkerForm
    template_name = 'staff/staff_form.html'

    def get_success_url(self):
        return reverse('staff:staff_detail', args=[self.object.pk])

    def form_invalid(self, form):
        messages.warning(self.request, 'Please check the highlighted fields.')
        return super().form_invalid(form)


class StaffCreateView(WorkerFormMixin, CreateView):
    def get_initial(self):
        initial = super().get_initial()
        contact = self.request.GET.get('contact', '')
        if contact.isdigit():
            initial['contact'] = contact
        unit = self.request.GET.get('unit', '')
        if unit.isdigit():
            initial['unit'] = unit
        return initial

    def get(self, request, *args, **kwargs):
        contact = request.GET.get('contact', '')
        if contact.isdigit():
            existing = Worker.objects.filter(contact_id=contact).first()
            if existing:
                messages.info(request, f'{existing} is already on the service team.')
                return redirect('staff:staff_detail', pk=existing.pk)
        return super().get(request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        response = super().form_valid(form)
        record_joined(self.object, self.request.user)
        messages.success(self.request, f'{self.object} has joined the service team.')
        return response


class StaffUpdateView(WorkerFormMixin, UpdateView):
    def get_queryset(self):
        return Worker.objects.select_related('contact')

    @transaction.atomic
    def form_valid(self, form):
        # The bound form has already copied the new values onto the instance.
        before = snapshot(Worker.objects.select_related('unit').get(pk=self.object.pk))
        response = super().form_valid(form)
        record_changes(before, self.object, self.request.user)
        messages.success(self.request, 'Service record updated.')
        return response


class EntryCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        worker = get_object_or_404(with_units(Worker.objects.all()), pk=pk)
        form = ServiceEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.worker, entry.recorded_by = worker, request.user
            entry.save()
            messages.success(request, 'Added to their service journey.')
            return redirect('staff:staff_detail', pk=pk)
        view = StaffDetailView(request=request, kwargs={'pk': pk}, object=worker)
        return view.render_to_response(view.get_context_data(entry_form=form))


class EntryDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        # Automatic entries are the record of what changed; only notes can go.
        entry = get_object_or_404(ServiceEntry.objects.exclude(kind=ServiceEntry.Kind.CHANGE), pk=pk)
        entry.delete()
        messages.success(request, 'Journey entry removed.')
        return redirect('staff:staff_detail', pk=entry.worker_id)


class UnitListView(LoginRequiredMixin, ListView):
    template_name = 'staff/unit_list.html'
    context_object_name = 'units'

    def get_queryset(self):
        serving = ~Q(members__status=Worker.Status.INACTIVE)
        return (ServiceUnit.objects.select_related('lead__contact')
                .annotate(serving=Count('members', filter=serving, distinct=True),
                          volunteers=Count('members', filter=serving & Q(members__service_type=Worker.ServiceType.VOLUNTEER), distinct=True),
                          helpers=Count('supporting_members', filter=~Q(supporting_members__status=Worker.Status.INACTIVE), distinct=True))
                .order_by('-is_active', 'name'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_set_roles = manages_accounts(self.request.user)
        context['form'] = kwargs.get('form') or ServiceUnitForm(can_set_roles=can_set_roles)
        context['can_set_roles'] = can_set_roles
        serving = Worker.objects.exclude(status=Worker.Status.INACTIVE).filter(allowance__gt=0)
        totals = {}
        for row in serving.order_by().values('unit_id', 'allowance_currency').annotate(total=Sum('allowance')):
            totals.setdefault(row['unit_id'], []).append(row)
        for unit in context['units']:
            unit.allowances = totals.get(unit.pk, [])
        return context


class UnitCreateView(LoginRequiredMixin, View):
    def post(self, request):
        form = ServiceUnitForm(request.POST, can_set_roles=manages_accounts(request.user))
        if form.is_valid():
            unit = form.save()
            messages.success(request, f'{unit} added.')
            return redirect('staff:unit_list')
        view = UnitListView(request=request, kwargs={})
        view.object_list = view.get_queryset()
        return view.render_to_response(view.get_context_data(form=form))


class UnitUpdateView(LoginRequiredMixin, UpdateView):
    model = ServiceUnit
    form_class = ServiceUnitForm
    template_name = 'staff/unit_form.html'
    context_object_name = 'unit'

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'can_set_roles': manages_accounts(self.request.user)}

    def get_success_url(self):
        return reverse('staff:unit_list')

    def form_valid(self, form):
        messages.success(self.request, f'{form.instance} updated.')
        return super().form_valid(form)

