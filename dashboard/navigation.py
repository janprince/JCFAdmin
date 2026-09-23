"""Staff navigation. URLs and active sections are resolved on the server."""
from django.urls import reverse
from accounts.access import can_visit


def navigation_for(request):
    definitions = [
        ('Overview', 'squares-four', [('Foundation overview', 'dashboard:analytics')]),
        ('Community', 'users-three', [('All contacts', 'members:contact_list'), ('Members', 'members:member_list'), ('Students', 'members:student_list'), ('Centres', 'centres:centre_list')]),
        ('Inbox', 'tray', [('Contact messages', 'website:contact_list'), ('Centre join requests', 'website:join_request_list'), ('Volunteer applications', 'website:volunteer_app_list'), ('Newsletter subscribers', 'website:newsletter_list')]),
        ('Consultations', 'calendar-check', [('Consultations', 'consultations:consultation_list')]),
        ('Teaching & events', 'book-open-text', [('Teachings', 'teachings:teaching_list'), ('Writings', 'blog:post_list'), ('Events', 'events:event_list')]),
        ('Giving', 'hand-heart', [('Initiatives', 'causes:cause_list'), ('Donations', 'causes:donation_list')]),
        ('Inner Space', 'monitor-play', [('Online students', 'innerspace:student_list'), ('Access requests', 'innerspace:request_list')]),
        ('Website content', 'globe-simple', [('Gallery', 'website:gallery_list'), ('Team members', 'website:team_list'), ('Testimonials', 'website:testimonial_list'), ('Volunteer roles', 'website:volunteer_list'), ('Impact statistics', 'website:impact_list')]),
    ]
    definitions.append(('Staff', 'identification-badge', [('Staff directory', 'staff:staff_list'), ('Portal access', 'staff:user_list')]))
    groups = []
    for index, (label, icon, links) in enumerate(definitions):
        links = [(title, route) for title, route in links if can_visit(request.user, route)]
        if not links:
            continue
        groups.append({'id': f'office-nav-{index}', 'label': label, 'icon': icon,
                       'links': [{'label': title, 'url': reverse(route)} for title, route in links]})
    # The most specific path wins: /contacts/members/ must not select All contacts.
    candidates = [link for group in groups for link in group['links'] if request.path.startswith(link['url'])]
    active_url = max(candidates, key=lambda item: len(item['url']))['url'] if candidates else None
    # Writings' taxonomy pages live beside /blog/posts/ rather than beneath it.
    if not active_url and request.resolver_match and request.resolver_match.namespace == 'blog':
        active_url = reverse('blog:post_list')
    for group in groups:
        for link in group['links']:
            link['active'] = link['url'] == active_url
        group['active'] = any(link['active'] for link in group['links'])
    return groups
