from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from . import services
from .forms import GroupForm
from .models import Group, GroupMembership


class GroupListView(LoginRequiredMixin, ListView):
    model = Group
    template_name = 'groups/group_list.html'
    context_object_name = 'groups'
    paginate_by = 50

    def get_queryset(self):
        qs = Group.objects.select_related('centre').order_by('name')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['pending_total'] = GroupMembership.objects.filter(
            status=GroupMembership.Status.PENDING
        ).count()
        return context


class GroupCreateView(LoginRequiredMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = 'groups/group_form.html'
    success_url = reverse_lazy('groups:group_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Group created.')
        return super().form_valid(form)


class GroupUpdateView(LoginRequiredMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = 'groups/group_form.html'
    success_url = reverse_lazy('groups:group_list')

    def form_valid(self, form):
        messages.success(self.request, 'Group updated.')
        return super().form_valid(form)


class GroupDetailView(LoginRequiredMixin, DetailView):
    model = Group
    template_name = 'groups/group_detail.html'
    context_object_name = 'group'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        memberships = self.object.memberships.select_related('contact', 'decided_by')
        context['pending'] = memberships.filter(status=GroupMembership.Status.PENDING)
        context['members'] = memberships.filter(status=GroupMembership.Status.APPROVED)
        context['declined'] = memberships.filter(status=GroupMembership.Status.DECLINED)
        return context


@login_required
@require_POST
def approve_membership(request, pk):
    membership = get_object_or_404(
        GroupMembership.objects.select_related('group', 'contact'), pk=pk
    )
    try:
        services.approve_request(membership, request.user)
        messages.success(
            request, f'{membership.contact.full_name} added to {membership.group.name}.'
        )
    except ValidationError as e:
        messages.warning(request, '; '.join(e.messages))
    return redirect('groups:group_detail', pk=membership.group_id)


@login_required
@require_POST
def decline_membership(request, pk):
    membership = get_object_or_404(
        GroupMembership.objects.select_related('group', 'contact'), pk=pk
    )
    services.decline_request(membership, request.user)
    messages.success(request, f'Request from {membership.contact.full_name} declined.')
    return redirect('groups:group_detail', pk=membership.group_id)


@login_required
@require_POST
def remove_membership(request, pk):
    """Remove an approved member (deletes the row so they may request again)."""
    membership = get_object_or_404(
        GroupMembership.objects.select_related('group', 'contact'), pk=pk
    )
    group_id = membership.group_id
    name = membership.contact.full_name
    membership.delete()
    messages.success(request, f'{name} removed from the group.')
    return redirect('groups:group_detail', pk=group_id)
