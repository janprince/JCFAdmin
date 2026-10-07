from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView, TemplateView

from dashboard.listing import tabs
from . import services
from .client import InnerspaceClient, InnerspaceRefused, InnerspaceUnavailable, is_configured
from .forms import AccessForm, ReviewRequestForm, RevokeForm, SetLevelForm
from .models import AccessGrantLog
from .records import AccessLevel, AccessRequestStatus

MANAGE_PERM = 'innerspace.manage_innerspace_access'
PAGE_SIZE = 50


class InnerspaceMixin:
    """Fail legibly when drbaffourjan.com can't be reached.

    These are the only pages that depend on another system. If it is down or
    not configured, staff see why — and the rest of the admin carries on.
    """

    def dispatch(self, request, *args, **kwargs):
        if not is_configured():
            return self.unavailable(request, 'Inner Space is not configured on this server. '
                                             'Set INNERSPACE_API_URL and INNERSPACE_API_KEY, then restart.')
        self.api = InnerspaceClient()
        try:
            return super().dispatch(request, *args, **kwargs)
        except InnerspaceUnavailable as exc:
            return self.unavailable(request, str(exc))

    def unavailable(self, request, reason):
        return render(request, 'innerspace/unavailable.html', {'reason': reason}, status=503)

    def page_number(self):
        page = self.request.GET.get('page', '1')
        return int(page) if page.isdigit() and int(page) > 0 else 1


class StudentListView(LoginRequiredMixin, InnerspaceMixin, ListView):
    template_name = 'innerspace/student_list.html'
    context_object_name = 'students'
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        access = self.request.GET.get('access', '')
        results, self.totals = self.api.students(
            q=self.request.GET.get('q', '').strip(),
            access=access if access in {'active', 'lapsed', 'none'} else '',
            page=self.page_number(), page_size=PAGE_SIZE,
        )
        return results

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        totals = self.totals
        context.update(
            search_query=self.request.GET.get('q', ''),
            access_filter=self.request.GET.get('access', ''),
            can_manage=self.request.user.has_perm(MANAGE_PERM),
            total_count=totals['students'], active_count=totals['active'],
            lapsed_count=totals['lapsed'], no_access_count=totals['none'],
            pending_requests=totals['pendingRequests'],
            tabs=tabs(self.request, 'access', [
                ('active', 'Active', totals['active']),
                ('lapsed', 'Lapsed', totals['lapsed']),
                ('none', 'No membership', totals['none']),
            ], total=totals['students']),
        )
        return context


class StudentDetailView(LoginRequiredMixin, InnerspaceMixin, TemplateView):
    template_name = 'innerspace/student_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            student, payments, access_requests = self.api.student(kwargs['pk'])
        except InnerspaceRefused as exc:
            raise Http404(str(exc)) from exc
        context.update(
            student=student,
            membership=student.membership,
            payments=payments,
            history=AccessGrantLog.objects.filter(student_id=student.pk).select_related('performed_by')[:20],
            access_form=AccessForm(current_level=student.access_level, initial={'duration': 'lifetime', 'currency': 'GHS'}),
            revoke_form=RevokeForm(),
            set_level_form=SetLevelForm(initial={'access_level': student.access_level}),
            access_requests=access_requests,
            pending_request=next((r for r in access_requests if r.is_pending), None),
            can_manage=self.request.user.has_perm(MANAGE_PERM),
        )
        return context


class ActionView(LoginRequiredMixin, PermissionRequiredMixin, InnerspaceMixin, View):
    """Base for POST-only changes. Refusals and outages become messages, not error pages."""

    permission_required = MANAGE_PERM
    raise_exception = True
    http_method_names = ['post']

    def post(self, request, pk):
        try:
            self.perform(request, pk)
        except InnerspaceRefused as exc:
            messages.error(request, str(exc))
        except InnerspaceUnavailable as exc:
            messages.error(request, f'Nothing was changed. {exc}')
        return redirect(self.success_url(request, pk))

    def success_url(self, request, pk):
        return reverse('innerspace:student_detail', args=[pk])

    def perform(self, request, pk):
        raise NotImplementedError


def _form_errors(form):
    return ' '.join(
        f'{field}: {" ".join(errors)}' if field != '__all__' else ' '.join(errors)
        for field, errors in form.errors.items()
    )


def _granted_message(student, entry, verb):
    who = student.email or student.display_name or 'student'
    membership = student.membership
    if membership.expires_at is None:
        message = f'Lifetime access {verb} {who}.'
    else:
        message = f'Access {verb} {who} until {timezone.localtime(membership.expires_at):%d %b %Y}.'
    # Say the level out loud when it moved. A change staff cannot see happen is
    # a change they cannot trust.
    if entry.previous_level and entry.previous_level != entry.new_level:
        message += (f' Moved from the {AccessLevel(entry.previous_level).label} path to '
                    f'{student.get_access_level_display()} — this takes effect on their next page load.')
    return message


class AccessChangeView(ActionView):
    service = None
    verb = ''

    def perform(self, request, pk):
        form = AccessForm(request.POST)
        if not form.is_valid():
            messages.error(request, _form_errors(form))
            return
        data = form.cleaned_data
        student, entry = self.service(
            pk, actor=request.user, access_level=data.get('access_level') or None,
            amount=data.get('amount'), currency=data.get('currency') or 'GHS',
            receipt_ref=data.get('receipt_ref', ''), note=data.get('note', ''), client=self.api,
            **form.duration_fields(),
        )
        messages.success(request, _granted_message(student, entry, self.verb))


class GrantAccessView(AccessChangeView):
    service = staticmethod(services.grant_access)
    verb = 'granted to'


class ExtendAccessView(AccessChangeView):
    service = staticmethod(services.extend_access)
    verb = 'extended to'


class RevokeAccessView(ActionView):
    def perform(self, request, pk):
        form = RevokeForm(request.POST)
        form.is_valid()
        student, _ = services.revoke_access(pk, actor=request.user, note=form.cleaned_data.get('note', ''), client=self.api)
        messages.warning(
            request,
            f'Access revoked for {student.email or student.display_name}. This takes effect the next time they '
            'sign in — an open session keeps working until their token refreshes.',
        )


class SetLevelView(ActionView):
    """Change a student's level directly, without going through a request."""

    def perform(self, request, pk):
        form = SetLevelForm(request.POST)
        if not form.is_valid():
            messages.error(request, _form_errors(form))
            return
        level = form.cleaned_data['access_level']
        student, entry = services.set_access_level(pk, actor=request.user, access_level=level,
                                                   note=form.cleaned_data.get('note', ''), client=self.api)
        if entry is None:
            messages.info(request, f'{student.email or student.display_name} is already on the {AccessLevel(level).label} path.')
        else:
            messages.success(request, f'{student.email or student.display_name} moved to the {AccessLevel(level).label} path.')


class AccessRequestListView(LoginRequiredMixin, InnerspaceMixin, ListView):
    """The approval queue: students asking to move up a level."""

    template_name = 'innerspace/access_request_list.html'
    context_object_name = 'requests'
    paginate_by = PAGE_SIZE

    def status(self):
        status = self.request.GET.get('status', AccessRequestStatus.PENDING)
        return status if status in AccessRequestStatus.values or status == 'all' else AccessRequestStatus.PENDING

    def get_queryset(self):
        results, self.totals = self.api.access_requests(status=self.status(), page=self.page_number(), page_size=PAGE_SIZE)
        return results

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        totals = self.totals
        context.update(
            status_filter=self.status(),
            statuses=AccessRequestStatus.choices,
            pending_count=totals.get('PENDING', 0),
            can_manage=self.request.user.has_perm(MANAGE_PERM),
            review_form=ReviewRequestForm(),
            tabs=tabs(self.request, 'status', [
                (value, label, totals.get(value, 0)) for value, label in AccessRequestStatus.choices
            ] + [('all', 'All', sum(totals.values()))], all_label=None, default=AccessRequestStatus.PENDING),
        )
        return context


class RequestDecisionView(ActionView):
    """POST-only approve/decline on a single request."""

    approve = True

    def success_url(self, request, pk):
        target = request.POST.get('next', '')
        if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return target
        return reverse('innerspace:request_list')

    def perform(self, request, pk):
        form = ReviewRequestForm(request.POST)
        form.is_valid()
        access_request = services.decide_access_request(pk, actor=request.user, approve=self.approve,
                                                        note=form.cleaned_data.get('note', ''), client=self.api)
        student = access_request.student
        who = student.email or student.display_name
        if self.approve:
            messages.success(request, f'{who} is now on the {student.get_access_level_display()} path. It takes effect '
                                      'the next time they open a page — no need for them to sign out.')
        else:
            messages.warning(request, f'Request from {who} declined. Their access level is unchanged.')
        _notify_student(request, access_request, approved=self.approve)


class ApproveRequestView(RequestDecisionView):
    approve = True


class DeclineRequestView(RequestDecisionView):
    approve = False


def _notify_student(request, access_request, approved):
    """Tell the student what happened. Never block the decision on email."""
    from .notifications import send_access_request_decision

    try:
        send_access_request_decision(access_request, approved=approved)
    except Exception as exc:  # noqa: BLE001 - the decision is already committed
        messages.warning(request, f'The change was saved, but the notification email failed to send: {exc}')
