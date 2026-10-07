"""Single source of truth for portal roles, navigation and endpoint access."""
from .models import Profile

AREAS = {
    'community': 'Contacts, members, students & centres',
    'inbox': 'Messages, applications & subscribers',
    'consultations': 'Consultations',
    'publishing': 'Teachings, events & writings',
    'content': 'Website content & digital resource links',
    'giving': 'Initiatives & donations',
    'innerspace': 'Inner Space students & access decisions',
    'staff': 'Service team, units & allowances',
    'accounts': 'Portal accounts & roles',
}
ROLE_AREAS = {
    Profile.Role.ADMIN: frozenset(AREAS),
    Profile.Role.ADMINISTRATOR: frozenset(AREAS) - {'accounts'},
    Profile.Role.SECRETARY: frozenset({'community', 'inbox', 'consultations'}),
    Profile.Role.MEDIA_OPS: frozenset({'publishing', 'content'}),
}
ROLE_DESCRIPTIONS = {
    'admin': 'Full portal access, including creating accounts and assigning roles.',
    'administrator': 'Foundation operations, publishing, giving, Inner Space and the service team. Cannot manage portal accounts.',
    'secretary': 'Contacts, centres, consultations and incoming requests. No giving, service team allowances or account administration.',
    'media_operations': 'Teachings, events, writings and website content. No private contact records, giving or service team administration.',
}

def areas_for(user):
    if not user.is_authenticated or not user.is_active:
        return frozenset()
    if user.is_superuser:
        return frozenset(AREAS)
    try:
        return ROLE_AREAS.get(user.profile.role, frozenset())
    except Profile.DoesNotExist:
        return frozenset()


def area_for_route(namespace, name):
    if namespace == 'staff':
        return 'accounts' if name.startswith(('user_', 'role_')) else 'staff'
    if namespace == 'resources':
        return 'content'
    if namespace == 'website':
        if name.startswith(('foundation_registration_', 'contact_', 'join_request_', 'volunteer_app_', 'newsletter_')):
            return 'inbox'
        if name.startswith(('gallery_', 'volunteer_', 'testimonial_', 'team_', 'impact_')):
            return 'content'
        return None
    return {'members': 'community', 'centres': 'community', 'consultations': 'consultations',
            'teachings': 'publishing', 'blog': 'publishing', 'events': 'publishing',
            'causes': 'giving', 'innerspace': 'innerspace'}.get(namespace)


# Pages every portal role may open, whatever its areas.
OPEN_ROUTES = {('resources', 'resource_list')}


def route_allowed(areas, namespace, name):
    if namespace == 'dashboard' or (namespace, name) in OPEN_ROUTES:
        return bool(areas)
    return area_for_route(namespace, name) in areas


def can_visit(user, route):
    namespace, _, name = route.partition(':')
    return route_allowed(areas_for(user), namespace, name)


def role_cards():
    return [{'value': value, 'label': label, 'description': ROLE_DESCRIPTIONS[value],
             'areas': [title for key, title in AREAS.items() if key in ROLE_AREAS[value]]}
            for value, label in Profile.Role.choices]


def office_access(request):
    areas = areas_for(request.user)
    return {'office_access': {area: area in areas for area in AREAS}}
