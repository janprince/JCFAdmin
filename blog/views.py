from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .forms import PostForm, AuthorForm, CategoryForm, TagForm
from .models import Post, Author, Category, Tag


# ---------------------------------------------------------------------------
# Post views
# ---------------------------------------------------------------------------

class PostListView(LoginRequiredMixin, ListView):
    model = Post
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 20

    def get_queryset(self):
        qs = Post.objects.select_related('author', 'category').all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(title__icontains=q)
        status = self.request.GET.get('status')
        if status in ('draft', 'published'):
            qs = qs.filter(status=status)
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category_id=category)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_category'] = self.request.GET.get('category', '')
        context['categories'] = Category.objects.all()
        return context


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/post_form.html'
    success_url = reverse_lazy('blog:post_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['tags'] = Tag.objects.all()
        return context

    def form_valid(self, form):
        if form.cleaned_data['status'] == Post.Status.PUBLISHED and not form.cleaned_data.get('published_date'):
            form.instance.published_date = timezone.now()
        messages.success(self.request, 'Post created successfully.')
        return super().form_valid(form)


class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/post_form.html'
    success_url = reverse_lazy('blog:post_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['tags'] = Tag.objects.all()
        return context

    def form_valid(self, form):
        if form.cleaned_data['status'] == Post.Status.PUBLISHED and not form.cleaned_data.get('published_date'):
            form.instance.published_date = timezone.now()
        messages.success(self.request, 'Post updated successfully.')
        return super().form_valid(form)


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    success_url = reverse_lazy('blog:post_list')

    def form_valid(self, form):
        messages.success(self.request, 'Post deleted.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Author views
# ---------------------------------------------------------------------------

class AuthorListView(LoginRequiredMixin, ListView):
    model = Author
    template_name = 'blog/author_list.html'
    context_object_name = 'authors'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AuthorForm()
        return context


class AuthorCreateView(LoginRequiredMixin, CreateView):
    model = Author
    form_class = AuthorForm
    template_name = 'blog/author_list.html'
    success_url = reverse_lazy('blog:author_list')

    def form_valid(self, form):
        messages.success(self.request, 'Author added.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        context = self.get_context_data(form=form)
        context['authors'] = Author.objects.all()
        return self.render_to_response(context)


class AuthorUpdateView(LoginRequiredMixin, UpdateView):
    model = Author
    form_class = AuthorForm
    template_name = 'blog/author_form.html'
    success_url = reverse_lazy('blog:author_list')

    def form_valid(self, form):
        messages.success(self.request, 'Author updated.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Category views
# ---------------------------------------------------------------------------

class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'blog/category_list.html'
    context_object_name = 'categories'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = CategoryForm()
        return context


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'blog/category_list.html'
    success_url = reverse_lazy('blog:category_list')

    def form_valid(self, form):
        messages.success(self.request, 'Category added.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        context = self.get_context_data(form=form)
        context['categories'] = Category.objects.all()
        return self.render_to_response(context)


# ---------------------------------------------------------------------------
# Tag views
# ---------------------------------------------------------------------------

class TagListView(LoginRequiredMixin, ListView):
    model = Tag
    template_name = 'blog/tag_list.html'
    context_object_name = 'tags'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = TagForm()
        return context


class TagCreateView(LoginRequiredMixin, CreateView):
    model = Tag
    form_class = TagForm
    template_name = 'blog/tag_list.html'
    success_url = reverse_lazy('blog:tag_list')

    def form_valid(self, form):
        messages.success(self.request, 'Tag added.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        context = self.get_context_data(form=form)
        context['tags'] = Tag.objects.all()
        return self.render_to_response(context)
