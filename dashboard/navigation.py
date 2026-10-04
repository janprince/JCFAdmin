"""Staff navigation. URLs and active sections are resolved on the server."""
from django.db.models import Count, Value
from django.urls import reverse
from django.utils import timezone

from accounts.access import can_visit


def _waiting(routes):
    """{route: records waiting on staff} for the queues among `routes`.

    One query for every badge: each queue's count is a branch of a UNION ALL.
    A count of 0 shows no badge.

    Default database only: the Inner Space queue lives in the remote student
    platform, and a round trip to it on every page load is not worth a badge.
    """
    from consultations.models import Consultation
    from website.models import ContactSubmission, FoundationRegistration, JoinCentreRequest, VolunteerApplication
    queues = {
        'website:foundation_registration_list': lambda: FoundationRegistration.objects.filter(reviewed_at__isnull=True),
        'website:contact_list': lambda: ContactSubmission.objects.filter(is_read=False),
        'website:join_request_list': lambda: JoinCentreRequest.objects.filter(status='pending'),
        'website:volunteer_app_list': lambda: VolunteerApplication.objects.filter(status='pending'),
        'consultations:consultation_list': lambda: Consultation.objects.filter(done=False, scheduled_date__lte=timezone.localdate()),
    }
    counts = [queues[route]().order_by().annotate(route=Value(route)).values('route').annotate(n=Count('pk'))
              for route in routes if route in queues]
    if not counts:
        return {}
    return {row['route']: row['n'] for row in counts[0].union(*counts[1:], all=True)}


# (section, group label, icon, [(link label, route)]). A section heading is
# drawn above the first group of each section the user can see; queues come
# first because the office starts its day there.
DEFINITIONS = [
    (None, 'Overview', 'squares-four', [('Foundation overview', 'dashboard:analytics')]),
    ('Daily work', 'Inbox', 'tray', [('Foundation registrations', 'website:foundation_registration_list'), ('Contact messages', 'website:contact_list'), ('Centre join requests', 'website:join_request_list'), ('Volunteer applications', 'website:volunteer_app_list'), ('Newsletter subscribers', 'website:newsletter_list')]),
    ('Daily work', 'Consultations', 'calendar-check', [('Consultations', 'consultations:consultation_list')]),
    ('Daily work', 'Inner Space', 'monitor-play', [('Online students', 'innerspace:student_list'), ('Access requests', 'innerspace:request_list')]),
    ('Foundation', 'Community', 'users-three', [('All contacts', 'members:contact_list'), ('Members', 'members:member_list'), ('Students', 'members:student_list'), ('Centres', 'centres:centre_list')]),
    ('Foundation', 'Giving', 'hand-heart', [('Initiatives', 'causes:cause_list'), ('Donations', 'causes:donation_list')]),
    ('Publishing', 'Teaching & events', 'book-open-text', [('Teachings', 'teachings:teaching_list'), ('Writings', 'blog:post_list'), ('Events', 'events:event_list')]),
    ('Publishing', 'Website content', 'globe-simple', [('Gallery', 'website:gallery_list'), ('Team members', 'website:team_list'), ('Testimonials', 'website:testimonial_list'), ('Volunteer roles', 'website:volunteer_list'), ('Impact statistics', 'website:impact_list')]),
    ('Administration', 'Service team', 'identification-badge', [('Service members', 'staff:staff_list'), ('Service units', 'staff:unit_list'), ('Portal access', 'staff:user_list')]),
]


def navigation_for(request):
    visible = [(index, section, label, icon, [(title, route) for title, route in links if can_visit(request.user, route)])
               for index, (section, label, icon, links) in enumerate(DEFINITIONS)]
    waiting = _waiting([route for *_, links in visible for _, route in links])
    groups = []
    for index, section, label, icon, links in visible:
        if not links:
            continue
        links = [{'label': title, 'url': reverse(route), 'count': waiting.get(route)} for title, route in links]
        groups.append({'id': f'office-nav-{index}', 'section': section, 'label': label, 'icon': icon, 'links': links,
                       'count': sum(link['count'] or 0 for link in links)})
    # The most specific path wins: /contacts/members/ must not select All contacts.
    candidates = [link for group in groups for link in group['links'] if request.path.startswith(link['url'])]
    active_url = max(candidates, key=lambda item: len(item['url']))['url'] if candidates else None
    # Writings' taxonomy pages live beside /blog/posts/ rather than beneath it.
    if not active_url and request.resolver_match and request.resolver_match.namespace == 'blog':
        active_url = reverse('blog:post_list')
    previous_section = None
    for group in groups:
        for link in group['links']:
            link['active'] = link['url'] == active_url
        group['active'] = any(link['active'] for link in group['links'])
        group['heading'] = group['section'] if group['section'] != previous_section else None
        previous_section = group['section']
    return groups
