from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('dashboard/', include('dashboard.urls')),
    path('login/', LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('contacts/', include('members.urls')),
    path('consultations/', include('consultations.urls')),
path('staff/', include('staff_mgmt.urls')),
    path('teachings/', include('teachings.urls')),
    # Public website content management
    path('events/', include('events.urls')),
    path('blog/', include('blog.urls')),
    path('centres/', include('centres.urls')),
    path('causes/', include('causes.urls')),
    path('website/', include('website.urls')),
    # Public API for Next.js website
    path('api/', include('config.api_urls')),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
