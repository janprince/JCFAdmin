from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.access import areas_for
from .forms import DigitalResourceForm, NewResourceForm
from .models import DigitalResource

# Suggested in the language box; anything else can still be typed.
LANGUAGES = ['English', 'Twi', 'Ga', 'Ewe', 'French']


class ResourceListView(LoginRequiredMixin, ListView):
    """Every portal role can open and copy links; content managers also edit them."""
    template_name = 'resources/resource_list.html'
    context_object_name = 'resources'

    def can_manage(self):
        return 'content' in areas_for(self.request.user)

    def get_queryset(self):
        qs = DigitalResource.objects.all()
        return qs if self.can_manage() else qs.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resources = list(context['resources'])
        groups = [{'label': label, 'value': value, 'items': [r for r in resources if r.category == value and r.is_active]}
                  for value, label in DigitalResource.Category.choices]
        used = {r.language for r in resources if r.language}
        context.update(
            groups=[group for group in groups if group['items']],
            archived=[r for r in resources if not r.is_active],
            can_manage=self.can_manage(),
            form=kwargs.get('form') or NewResourceForm(),
            languages=sorted(used | set(LANGUAGES)),
        )
        return context


class ResourceCreateView(LoginRequiredMixin, CreateView):
    model = DigitalResource
    form_class = NewResourceForm
    success_url = reverse_lazy('resources:resource_list')
    http_method_names = ['post']

    def form_valid(self, form):
        messages.success(self.request, f'{form.instance.title} added.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please check the highlighted fields.')
        view = ResourceListView(request=self.request, kwargs={})
        view.object_list = view.get_queryset()
        return view.render_to_response(view.get_context_data(form=form))


class ResourceUpdateView(LoginRequiredMixin, UpdateView):
    model = DigitalResource
    form_class = DigitalResourceForm
    template_name = 'resources/resource_form.html'
    success_url = reverse_lazy('resources:resource_list')

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'languages': LANGUAGES}

    def form_valid(self, form):
        messages.success(self.request, f'{form.instance.title} updated.')
        return super().form_valid(form)


class ResourceDeleteView(LoginRequiredMixin, DeleteView):
    model = DigitalResource
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('resources:resource_list')

    def form_valid(self, form):
        messages.success(self.request, f'{self.object.title} removed.')
        return super().form_valid(form)
