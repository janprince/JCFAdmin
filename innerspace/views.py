from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import DatabaseError, connections
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView

from . import services
from .forms import AccessForm, ReviewRequestForm, RevokeForm, SetLevelForm
from .models import (
    AccessGrantLog,
    AccessLevel,
    AccessRequest,
    AccessRequestStatus,
    Membership,
    MembershipStatus,
    Payment,
    Student,
)
from .routers import INNERSPACE_DB

MANAGE_PERM = 'innerspace.manage_innerspace_access'


class InnerspaceDatabaseMixin:
    """Fail legibly when the Innerspace database is unreachable.

    These pages are the only part of JCF that depends on a second, external
    database. If the connection string is missing or the host is down, staff
    should see an explanation rather than a stack trace — and the rest of the
    admin should carry on working.
    """

    def dispatch(self, request, *args, **kwargs):
        if INNERSPACE_DB not in connections:
            return self.unavailable(
                request,
                'The Innerspace database is not configured on this server. '
                'Set INNERSPACE_DATABASE_URL and restart.',
            )
        try:
            return super().dispatch(request, *args, **kwargs)
        except DatabaseError as exc:
            return self.unavailable(
                request, f'Could not reach the Innerspace database: {exc}'
            )

    def unavailable(self, request, reason):
        return render(request, 'innerspace/unavailable.html', {'reason': reason}, status=503)


def _active_membership_q(prefix='membership__'):
    """Matches the website's own definition of active access."""
    now = timezone.now()
    return Q(**{f'{prefix}status': MembershipStatus.ACTIVE}) & (
        Q(**{f'{prefix}expires_at__isnull': True})
        | Q(**{f'{prefix}expires_at__gt': now})
    )


class StudentListView(LoginRequiredMixin, InnerspaceDatabaseMixin, ListView):
    model = Student
    template_name = 'innerspace/student_list.html'
    context_object_name = 'students'
    paginate_by = 50

    def get_queryset(self):
        qs = Student.objects.select_related('membership')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(email__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(name__icontains=q)
                | Q(phone__icontains=q)
            )

        access = self.request.GET.get('access')
        if access == 'active':
            qs = qs.filter(_active_membership_q())
        elif access == 'lapsed':
            qs = qs.filter(membership__isnull=False).exclude(_active_membership_q())
        elif access == 'none':
            qs = qs.filter(membership__isnull=True)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['access_filter'] = self.request.GET.get('access', '')
        context['can_manage'] = self.request.user.has_perm(MANAGE_PERM)

        total = Student.objects.count()
        active = Membership.objects.filter(_active_membership_q(prefix='')).count()
        context['total_count'] = total
        context['active_count'] = active
        context['no_access_count'] = total - Membership.objects.count()
        context['pending_requests'] = AccessRequest.objects.filter(
            status=AccessRequestStatus.PENDING,
        ).count()
        return context


class StudentDetailView(LoginRequiredMixin, InnerspaceDatabaseMixin, DetailView):
    model = Student
    template_name = 'innerspace/student_detail.html'
    context_object_name = 'student'

    def get_queryset(self):
        return Student.objects.select_related('membership')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object
        context['membership'] = getattr(student, 'membership', None)
        context['payments'] = Payment.objects.filter(student=student)[:20]
        context['history'] = AccessGrantLog.objects.filter(
            student_id=student.pk,
        ).select_related('performed_by')[:20]
        context['access_form'] = AccessForm(
            current_level=student.access_level,
            initial={'duration': 'lifetime', 'currency': 'GHS'},
        )
        context['revoke_form'] = RevokeForm()
        context['set_level_form'] = SetLevelForm(initial={
            'access_level': student.access_level,
        })
        context['access_requests'] = AccessRequest.objects.filter(student=student)
        context['pending_request'] = AccessRequest.objects.filter(
            student=student, status=AccessRequestStatus.PENDING,
        ).first()
        context['can_manage'] = self.request.user.has_perm(MANAGE_PERM)
        return context


class AccessActionView(LoginRequiredMixin, PermissionRequiredMixin, InnerspaceDatabaseMixin, DetailView):
    """Base for the POST-only membership actions on the student detail page."""

    model = Student
    permission_required = MANAGE_PERM
    raise_exception = True
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        student = self.get_object()
        redirect_to = redirect(reverse('innerspace:student_detail', args=[student.pk]))
        try:
            self.perform(request, student)
        except Membership.DoesNotExist as exc:
            messages.error(request, str(exc))
        except DatabaseError as exc:
            messages.error(request, f'Could not reach the Innerspace database: {exc}')
        return redirect_to

    def perform(self, request, student):
        raise NotImplementedError


class GrantAccessView(AccessActionView):

    def perform(self, request, student):
        form = AccessForm(request.POST, current_level=student.access_level)
        if not form.is_valid():
            messages.error(request, _form_errors(form))
            return

        previous_level = student.access_level
        membership = services.grant_access(
            student,
            actor=request.user,
            access_level=form.cleaned_data.get('access_level') or None,
            expires_at=form.expires_at(),
            amount=form.cleaned_data.get('amount'),
            currency=form.cleaned_data.get('currency') or 'GHS',
            receipt_ref=form.cleaned_data.get('receipt_ref', ''),
            note=form.cleaned_data.get('note', ''),
        )
        messages.success(
            request,
            _granted_message(student, membership, previous_level=previous_level),
        )


class ExtendAccessView(AccessActionView):

    def perform(self, request, student):
        form = AccessForm(request.POST, current_level=student.access_level)
        if not form.is_valid():
            messages.error(request, _form_errors(form))
            return

        duration = form.cleaned_data['duration']
        if duration == 'custom':
            # An explicit date wins; the service takes it as-is.
            months, expires_at = None, form.expires_at()
        else:
            # 'lifetime' leaves both None, which clears the expiry.
            months, expires_at = form.months, None

        previous_level = student.access_level
        membership = services.extend_access(
            student,
            actor=request.user,
            access_level=form.cleaned_data.get('access_level') or None,
            months=months,
            expires_at=expires_at,
            amount=form.cleaned_data.get('amount'),
            currency=form.cleaned_data.get('currency') or 'GHS',
            receipt_ref=form.cleaned_data.get('receipt_ref', ''),
            note=form.cleaned_data.get('note', ''),
        )
        messages.success(
            request,
            _granted_message(
                student, membership, verb='extended to', previous_level=previous_level,
            ),
        )


class RevokeAccessView(AccessActionView):

    def perform(self, request, student):
        form = RevokeForm(request.POST)
        form.is_valid()
        services.revoke_access(student, actor=request.user,
                               note=form.cleaned_data.get('note', ''))
        messages.warning(
            request,
            f'Access revoked for {student.email or student.display_name}. '
            'This takes effect the next time they sign in — an open session '
            'keeps working until their token refreshes.',
        )


def _form_errors(form):
    return ' '.join(
        f'{field}: {" ".join(errors)}' if field != '__all__' else ' '.join(errors)
        for field, errors in form.errors.items()
    )


def _granted_message(student, membership, verb='granted to', previous_level=None):
    who = student.email or student.display_name or 'student'

    if membership.expires_at is None:
        message = f'Lifetime access {verb} {who}.'
    else:
        message = (
            f'Access {verb} {who} until '
            f'{timezone.localtime(membership.expires_at):%d %b %Y}.'
        )

    # Say the level out loud when it moved. A change staff cannot see happen is
    # a change they cannot trust.
    if previous_level and previous_level != student.access_level:
        message += (
            f' Moved from the {AccessLevel(previous_level).label} path to '
            f'{student.get_access_level_display()} — this takes effect on their '
            f'next page load.'
        )
    return message


class AccessRequestListView(LoginRequiredMixin, InnerspaceDatabaseMixin, ListView):
    """The approval queue: students asking to move up a level."""

    model = AccessRequest
    template_name = 'innerspace/access_request_list.html'
    context_object_name = 'requests'
    paginate_by = 50

    def get_queryset(self):
        qs = AccessRequest.objects.select_related('student')
        status = self.request.GET.get('status', AccessRequestStatus.PENDING)
        if status and status != 'all':
            qs = qs.filter(status=status)
        # Oldest first — nobody should wait longer because someone asked later.
        return qs.order_by('created_at' if status == AccessRequestStatus.PENDING else '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', AccessRequestStatus.PENDING)
        context['statuses'] = AccessRequestStatus.choices
        context['pending_count'] = AccessRequest.objects.filter(
            status=AccessRequestStatus.PENDING,
        ).count()
        context['can_manage'] = self.request.user.has_perm(MANAGE_PERM)
        context['review_form'] = ReviewRequestForm()
        return context


class RequestActionView(LoginRequiredMixin, PermissionRequiredMixin,
                        InnerspaceDatabaseMixin, DetailView):
    """POST-only approve/decline on a single request."""

    model = AccessRequest
    permission_required = MANAGE_PERM
    raise_exception = True
    http_method_names = ['post']

    def get_queryset(self):
        return AccessRequest.objects.select_related('student')

    def post(self, request, *args, **kwargs):
        access_request = self.get_object()
        form = ReviewRequestForm(request.POST)
        form.is_valid()
        note = form.cleaned_data.get('note', '')

        try:
            self.perform(request, access_request, note)
        except ValueError as exc:
            messages.error(request, str(exc))
        except DatabaseError as exc:
            messages.error(request, f'Could not reach the Innerspace database: {exc}')

        return redirect(request.POST.get('next') or reverse('innerspace:request_list'))

    def perform(self, request, access_request, note):
        raise NotImplementedError


class ApproveRequestView(RequestActionView):

    def perform(self, request, access_request, note):
        services.approve_access_request(access_request, actor=request.user, note=note)
        student = access_request.student
        messages.success(
            request,
            f'{student.email or student.display_name} is now on the '
            f'{student.get_access_level_display()} path. It takes effect the next '
            f'time they open a page — no need for them to sign out.',
        )
        _notify_student(request, access_request, approved=True)


class DeclineRequestView(RequestActionView):

    def perform(self, request, access_request, note):
        services.decline_access_request(access_request, actor=request.user, note=note)
        messages.warning(
            request,
            f'Request from {access_request.student.email or access_request.student.display_name} '
            f'declined. Their access level is unchanged.',
        )
        _notify_student(request, access_request, approved=False)


class SetLevelView(LoginRequiredMixin, PermissionRequiredMixin,
                   InnerspaceDatabaseMixin, DetailView):
    """Change a student's level directly, without going through a request."""

    model = Student
    permission_required = MANAGE_PERM
    raise_exception = True
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        student = self.get_object()
        form = SetLevelForm(request.POST)

        if not form.is_valid():
            messages.error(request, _form_errors(form))
        else:
            level = form.cleaned_data['access_level']
            try:
                services.set_access_level(
                    student, actor=request.user, access_level=level,
                    note=form.cleaned_data.get('note', ''),
                )
                messages.success(
                    request,
                    f'{student.email or student.display_name} moved to the '
                    f'{AccessLevel(level).label} path.',
                )
            except DatabaseError as exc:
                messages.error(request, f'Could not reach the Innerspace database: {exc}')

        return redirect(reverse('innerspace:student_detail', args=[student.pk]))


def _notify_student(request, access_request, approved):
    """Tell the student what happened. Never block the decision on email."""
    from .notifications import send_access_request_decision

    try:
        send_access_request_decision(access_request, approved=approved)
    except Exception as exc:  # noqa: BLE001 - the decision is already committed
        messages.warning(
            request,
            f'The change was saved, but the notification email failed to send: {exc}',
        )
