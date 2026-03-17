from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .forms import EventForm, EventCategoryForm
from .models import Event, EventCategory


class EventListView(LoginRequiredMixin, ListView):
    model = Event
    template_name = 'events/event_list.html'
    context_object_name = 'events'
    paginate_by = 20

    def get_queryset(self):
        qs = Event.objects.select_related('category').order_by('-date', '-time')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(location__icontains=q))

        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category_id=category)

        filter_type = self.request.GET.get('filter')
        today = timezone.now().date()
        if filter_type == 'upcoming':
            qs = qs.filter(date__gte=today)
        elif filter_type == 'past':
            qs = qs.filter(date__lt=today)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['current_filter'] = self.request.GET.get('filter', '')
        context['current_category'] = self.request.GET.get('category', '')
        context['categories'] = EventCategory.objects.all()
        context['category_form'] = EventCategoryForm()
        today = timezone.now().date()
        context['total_count'] = Event.objects.count()
        context['upcoming_count'] = Event.objects.filter(date__gte=today).count()
        context['past_count'] = Event.objects.filter(date__lt=today).count()
        return context


class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = reverse_lazy('events:event_list')

    def form_valid(self, form):
        messages.success(self.request, 'Event created successfully.')
        return super().form_valid(form)


class EventUpdateView(LoginRequiredMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = reverse_lazy('events:event_list')

    def form_valid(self, form):
        messages.success(self.request, 'Event updated successfully.')
        return super().form_valid(form)


class EventDeleteView(LoginRequiredMixin, DeleteView):
    model = Event
    success_url = reverse_lazy('events:event_list')

    def get(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f'Event "{self.object.title}" deleted.')
        return super().form_valid(form)


class EventCategoryListView(LoginRequiredMixin, ListView):
    model = EventCategory
    template_name = 'events/event_list.html'
    context_object_name = 'categories'

    def post(self, request, *args, **kwargs):
        form = EventCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added.')
        else:
            messages.warning(request, 'Category name is required.')
        return redirect('events:event_list')


@login_required
def delete_category(request, pk):
    category = get_object_or_404(EventCategory, pk=pk)
    category.delete()
    messages.success(request, 'Category deleted.')
    return redirect('events:event_list')
