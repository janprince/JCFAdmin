from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import CostItemForm, ProgramForm, TierForm
from .models import AccommodationTier, CostLineItem, Program, Registration


class ProgramListView(LoginRequiredMixin, ListView):
    model = Program
    template_name = 'programs/program_list.html'
    context_object_name = 'programs'
    paginate_by = 50

    def get_queryset(self):
        return Program.objects.annotate(
            registration_count=Count(
                'registrations',
                filter=Q(registrations__status=Registration.Status.CONFIRMED),
            ),
        )


class ProgramCreateView(LoginRequiredMixin, CreateView):
    model = Program
    form_class = ProgramForm
    template_name = 'programs/program_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Program created. Now add fees and accommodation tiers.')
        return reverse('programs:program_detail', args=[self.object.pk])


class ProgramUpdateView(LoginRequiredMixin, UpdateView):
    model = Program
    form_class = ProgramForm
    template_name = 'programs/program_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Program updated.')
        return reverse('programs:program_detail', args=[self.object.pk])


class ProgramDetailView(LoginRequiredMixin, DetailView):
    model = Program
    template_name = 'programs/program_detail.html'
    context_object_name = 'program'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        registrations = self.object.registrations.select_related(
            'contact', 'accommodation_tier')
        context.update({
            'tiers': self.object.accommodation_tiers.all(),
            'cost_items': self.object.cost_line_items.all(),
            'registrations': registrations,
            'confirmed_count': registrations.filter(
                status=Registration.Status.CONFIRMED).count(),
            'pending_count': registrations.filter(
                status=Registration.Status.PENDING).count(),
            'tier_form': TierForm(),
            'cost_form': CostItemForm(),
        })
        return context


@login_required
@require_POST
def tier_add(request, pk):
    program = get_object_or_404(Program, pk=pk)
    form = TierForm(request.POST)
    if form.is_valid():
        tier = form.save(commit=False)
        tier.program = program
        # Quick-add form has no is_active checkbox; new tiers start active.
        if 'is_active' not in request.POST:
            tier.is_active = True
        tier.save()
        messages.success(request, f'Tier "{tier.name}" added.')
    else:
        messages.warning(request, f'Tier not added: {form.errors.as_text()}')
    return redirect('programs:program_detail', pk=pk)


@login_required
@require_POST
def tier_delete(request, pk):
    tier = get_object_or_404(AccommodationTier, pk=pk)
    program_id = tier.program_id
    if tier.registrations.exists():
        tier.is_active = False
        tier.save(update_fields=['is_active'])
        messages.warning(
            request, f'"{tier.name}" has registrations, so it was deactivated instead of deleted.')
    else:
        tier.delete()
        messages.success(request, 'Tier removed.')
    return redirect('programs:program_detail', pk=program_id)


@login_required
@require_POST
def cost_item_add(request, pk):
    program = get_object_or_404(Program, pk=pk)
    form = CostItemForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.program = program
        if 'is_active' not in request.POST:
            item.is_active = True
        item.save()
        messages.success(request, f'Fee "{item.label}" added.')
    else:
        messages.warning(request, f'Fee not added: {form.errors.as_text()}')
    return redirect('programs:program_detail', pk=pk)


@login_required
@require_POST
def cost_item_delete(request, pk):
    item = get_object_or_404(CostLineItem, pk=pk)
    program_id = item.program_id
    item.delete()
    messages.success(request, 'Fee removed.')
    return redirect('programs:program_detail', pk=program_id)


@login_required
@require_POST
def registration_cancel(request, pk):
    """Cancel a registration; frees the tier room if it was confirmed."""
    registration = get_object_or_404(
        Registration.objects.select_related('accommodation_tier'), pk=pk)
    if registration.status == Registration.Status.CANCELLED:
        messages.info(request, 'Already cancelled.')
        return redirect('programs:program_detail', pk=registration.program_id)

    was_confirmed = registration.status == Registration.Status.CONFIRMED
    registration.status = Registration.Status.CANCELLED
    registration.save(update_fields=['status'])
    tier = registration.accommodation_tier
    if was_confirmed and tier is not None and tier.rooms_confirmed > 0:
        tier.rooms_confirmed -= 1
        tier.save(update_fields=['rooms_confirmed'])
    messages.success(request, f'Registration {registration.reference} cancelled.')
    return redirect('programs:program_detail', pk=registration.program_id)
