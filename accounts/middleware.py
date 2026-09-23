from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render
from django.utils.deprecation import MiddlewareMixin

from .access import areas_for, area_for_route


class PortalAccessMiddleware(MiddlewareMixin):
    """Enforce roles for every portal view, including legacy function/GET actions."""
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        namespace, name = match.namespace, match.url_name or ''
        # Public website APIs (including Paystack) retain their own policies.
        if request.path_info.startswith('/api/') or name in {'login', 'logout'}:
            return None
        protected = namespace in {'dashboard', 'members', 'centres', 'consultations',
                                  'teachings', 'blog', 'events', 'causes', 'innerspace', 'website', 'staff', 'accounts', 'admin'}
        if not protected:
            return None
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.must_change_password and match.view_name != 'accounts:password_change':
            return redirect('accounts:password_change')
        if namespace == 'accounts' and name == 'password_change':
            return None
        # A portal role never grants access to Django's independent permissions UI.
        if namespace == 'admin':
            allowed = request.user.is_superuser
        else:
            areas = areas_for(request.user)
            allowed = bool(areas) if namespace == 'dashboard' else area_for_route(namespace, name) in areas
        if not allowed:
            return render(request, 'accounts/access_denied.html', status=403)
        return None
