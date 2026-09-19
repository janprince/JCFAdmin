"""
Emails sent to Innerspace students from this admin.

Django is the actor when a level request is reviewed, so it is also the sender.
Routing this back through the Next.js app would mean an authenticated webhook
and a second failure mode for no benefit.

Every send is best-effort — the decision is already committed to the database
before we get here, and a mail outage must never make it look otherwise. The
caller surfaces failures as a warning rather than an error.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

SITE_URL = getattr(settings, 'INNERSPACE_SITE_URL', 'https://drbaffourjan.com')


def send_access_request_decision(access_request, approved):
    """Tell a student that their level request was approved or declined."""
    student = access_request.student
    email = (student.email or '').strip()
    if not email:
        logger.info('Access request %s: student has no email, skipping', access_request.pk)
        return False

    first_name = student.first_name or 'there'
    level = student.get_access_level_display()

    if approved:
        subject = 'Your access has been opened'
        # Deep-link to the course they were blocked on, when we know it.
        destination = (
            f'{SITE_URL}/student/courses/{access_request.course_slug}'
            if access_request.course_slug
            else f'{SITE_URL}/student/courses'
        )
        body = (
            f'Hello {first_name},\n\n'
            f'Your request has been reviewed and your access has been raised to '
            f'the {level} path.\n\n'
            f'Everything at that level and below is now open to you:\n'
            f'{destination}\n\n'
            f'{_note_block(access_request.review_note)}'
            f'Warmly,\n'
            f"Dr. Baffour Jan's team"
        )
    else:
        subject = 'About your access request'
        body = (
            f'Hello {first_name},\n\n'
            f'Thank you for asking about moving further along the path. For now '
            f'we would like you to stay with the {level} teachings a little '
            f'longer — the material is sequenced deliberately, and there is more '
            f'to draw from where you are.\n\n'
            f'{_note_block(access_request.review_note)}'
            f'You are welcome to ask again when you feel ready.\n\n'
            f'Warmly,\n'
            f"Dr. Baffour Jan's team"
        )

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    logger.info('Access request %s: notified %s', access_request.pk, email)
    return True


def _note_block(note):
    note = (note or '').strip()
    return f'A note from the team:\n{note}\n\n' if note else ''
