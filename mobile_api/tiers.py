"""The app's two tiers: guests, and signed-in students.

There used to be three — guest, member, student — and the rules for who
could see and open what were re-derived in six modules, each slightly
differently. There are two now, and the rules live here.

`is_member` has NOT been removed from Contact. It is a JCFAdmin CRM flag,
written by the public website at registration and counted on the
dashboard, and it still marks an approved contact. It is no longer an app
tier: a contact who is approved by either flag gets the student
experience, so nobody who could use the app before is locked out now.
"""

PUBLIC = 'public'
STUDENTS = 'students'


def is_approved(contact):
    """Whether this contact may open gated content.

    Either flag, because both mean "JCF has approved this person" — only
    the app's reading of them changed.
    """
    return bool(contact is not None
                and contact.is_active
                and (contact.is_student or contact.is_member))


def attendable_audiences(contact):
    """What this caller may actually open."""
    return [PUBLIC, STUDENTS] if is_approved(contact) else [PUBLIC]


def visible_audiences(contact):
    """What this caller may see listed.

    The same as what they may open. With three tiers a guest was shown
    member-tier content locked, as a reason to sign in, while
    students-only content was hidden outright. Collapsing the two gated
    tiers into one forced a choice, and this is the strict side of it:
    a guest is never told that gated content exists.

    So a guest's feed is public content only, and the locked-teaser
    prompt no longer appears there. `access.allowed` still carries the
    locked state for everything else — a direct link, a stale cache, or
    a signed-in contact whose approval has lapsed.
    """
    return attendable_audiences(contact)


def may_open(audience, contact):
    """Whether this caller may open a thing with this audience."""
    return audience == PUBLIC or is_approved(contact)
