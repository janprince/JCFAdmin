"""
Client for the student platform's office API (drbaffourjan.com /api/jcf/v1).

The platform owns its database and the rules for memberships and access
levels; this admin reads and changes them only through these calls. The
shared key (INNERSPACE_API_KEY here, JCF_OFFICE_API_KEY there) stays on the
two servers and never reaches a browser.

Failures come back as two exceptions:

- `InnerspaceUnavailable` — not configured, unreachable, or a server error.
  Pages show "can't be reached" and the rest of the admin carries on.
- `InnerspaceRefused` — the platform understood and said no (a request that
  was already decided, a level that would not be raised). Its message is
  written for staff and shown as is.

Writes are not retried: a timeout can mean the change landed, and a second
grant would record the cash payment twice.
"""

import logging
from collections.abc import Sequence

from urllib.parse import urljoin, urlsplit

import requests
from django.conf import settings

from .records import AccessRequest, Payment, Student

logger = logging.getLogger(__name__)

TIMEOUT = (5, 20)  # connect, read — seconds


class InnerspaceUnavailable(Exception):
    pass


class InnerspaceRefused(Exception):
    def __init__(self, message, code='', fields=None):
        super().__init__(message)
        self.code = code
        self.fields = fields or {}


def is_configured():
    return bool(getattr(settings, 'INNERSPACE_API_URL', '') and getattr(settings, 'INNERSPACE_API_KEY', ''))


def _actor(user):
    return {'email': getattr(user, 'email', '') or user.get_username(), 'name': user.get_full_name()}


class RemoteResults(Sequence):
    """One page of results with the total behind it.

    Lets Django's Paginator (and the shared pager template) work over an API
    that pages on the server: the length is the total count, and slicing
    returns the page already fetched.
    """

    def __init__(self, items, count):
        self.items, self.count = list(items), count

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        return self.items if isinstance(index, slice) else self.items[index]


class InnerspaceClient:
    def __init__(self, base_url=None, api_key=None, session=None):
        self.base_url = (base_url or getattr(settings, 'INNERSPACE_API_URL', '')).rstrip('/')
        self.api_key = api_key or getattr(settings, 'INNERSPACE_API_KEY', '')
        self.session = session or requests.Session()

    def _call(self, method, path, params=None, body=None):
        if not (self.base_url and self.api_key):
            raise InnerspaceUnavailable('Inner Space is not configured on this server. Set INNERSPACE_API_URL and INNERSPACE_API_KEY.')
        url = f'{self.base_url}/api/jcf/v1/{path}'
        try:
            # Never follow redirects: the key would be dropped on a move to another
            # host (drbaffourjan.com -> www.), and a write must not be re-sent.
            response = self.session.request(method, url, params=params, json=body, timeout=TIMEOUT, allow_redirects=False,
                                            headers={'Authorization': f'Bearer {self.api_key}', 'Accept': 'application/json'})
        except requests.RequestException as exc:
            logger.warning('Inner Space API %s %s failed: %s', method, path, exc)
            raise InnerspaceUnavailable('Could not reach drbaffourjan.com. Try again in a moment.') from exc

        if 300 <= response.status_code < 400:
            target = urlsplit(urljoin(url, response.headers.get('Location', '')))
            logger.error('Inner Space API %s redirects to %s', self.base_url, target.geturl())
            raise InnerspaceUnavailable(
                f'{self.base_url} redirects to {target.scheme}://{target.netloc}. '
                f'Set INNERSPACE_API_URL to {target.scheme}://{target.netloc} and restart.')

        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.ok:
            return data
        error = data.get('error') or {}
        message = error.get('message') or f'The student platform answered {response.status_code}.'
        if response.status_code in (400, 404, 409):
            raise InnerspaceRefused(message, error.get('code', ''), error.get('fields'))
        if response.status_code == 401:
            logger.error('Inner Space API rejected the office key.')
            message = 'The student platform did not accept this server’s key. Check INNERSPACE_API_KEY.'
        raise InnerspaceUnavailable(message)

    # Reads ------------------------------------------------------------------

    def students(self, q='', access='', page=1, page_size=50):
        data = self._call('GET', 'students', params={'q': q, 'access': access, 'page': page, 'pageSize': page_size})
        return RemoteResults((Student.from_api(s) for s in data['results']), data['count']), data['totals']

    def student(self, student_id):
        data = self._call('GET', f'students/{student_id}')
        student = Student.from_api(data['student'])
        payments = [Payment.from_api(p) for p in data['payments']]
        requests_ = [AccessRequest.from_api(r, student=student) for r in data['accessRequests']]
        return student, payments, requests_

    def access_requests(self, status='PENDING', page=1, page_size=50):
        data = self._call('GET', 'access-requests', params={'status': status, 'page': page, 'pageSize': page_size})
        return RemoteResults((AccessRequest.from_api(r) for r in data['results']), data['count']), data['totals']

    # Writes -----------------------------------------------------------------

    def _change(self, action, student_id, user, **fields):
        body = {'actor': _actor(user), **{k: v for k, v in fields.items() if v not in (None, '')}}
        data = self._call('POST', f'students/{student_id}/{action}', body=body)
        return Student.from_api(data['student']), data

    def grant(self, student_id, user, **fields):
        return self._change('grant', student_id, user, **fields)

    def extend(self, student_id, user, **fields):
        return self._change('extend', student_id, user, **fields)

    def revoke(self, student_id, user, note=''):
        return self._change('revoke', student_id, user, note=note)

    def set_level(self, student_id, user, access_level, note=''):
        return self._change('level', student_id, user, accessLevel=access_level, note=note)

    def decide(self, request_id, user, approve, note=''):
        data = self._call('POST', f'access-requests/{request_id}/{"approve" if approve else "decline"}',
                          body={'actor': _actor(user), 'note': note})
        return AccessRequest.from_api(data['request']), data['previousLevel']
