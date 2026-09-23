"""Helpers for list pages: tab links with counts, and grouped counts.

Tabs are built in views rather than templates because `{% querystring %}`
cannot take a variable parameter name, and each list filters on a different
one (`status`, `role`, `filter`, `access`, `category`).
"""
from django.db.models import Count


def count_by(queryset, field):
    """{value: count} for one field, in a single grouped query.

    `order_by()` clears the model's Meta ordering, which Django would otherwise
    add to the GROUP BY and so split the counts.
    """
    return dict(queryset.order_by().values_list(field).annotate(n=Count('pk')))


def tabs(request, param, options, total=None, all_label='All', default=''):
    """Tab links for a list page, rendered by partials/_tabs.html.

    `options` is an iterable of (value, label, count). An "All" tab showing
    `total` comes first unless `all_label` is None. `default` is the value the
    view assumes when the parameter is absent; its tab links to the bare URL.
    Every link keeps the page's other filters and drops `page`.
    """
    current = request.GET.get(param) or default

    def href(value):
        query = request.GET.copy()
        query.pop('page', None)
        if value and value != default:
            query[param] = value
        else:
            query.pop(param, None)
        encoded = query.urlencode()
        return f'?{encoded}' if encoded else request.path

    items = []
    if all_label is not None:
        items.append({'label': all_label, 'count': total, 'href': href(''), 'active': current == ''})
    for value, label, count in options:
        items.append({'label': label, 'count': count, 'href': href(value), 'active': current == value})
    return items
