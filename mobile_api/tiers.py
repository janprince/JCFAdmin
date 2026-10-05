"""The app's two tiers: guests, and signed-in students.

There used to be three — guest, member, student — and the rules for who
could see and open what were re-derived in six modules, each slightly
differently. There are two now, and the rules live here.

`Contact.is_member` is THE approval flag, because it is the only one the
web actually produces: approving a join-centre request on the website
sets it (website/views.py), and creating an Enrolment sets it too.
Nothing anywhere sets `is_student` automatically — staff tick it by hand
and the legacy import carried it in — so it is read here only as a bridge
for contacts flagged that way before this rule existed.

The app's one signed-in tier is still called "student" in the interface.
That is deliberate: the label is the product's word for the reader, and
`is_member` is the database's word for the approval. They do not have to
match, and the alternative was locking out everyone the website admits.

THE BRIDGE IS TEMPORARY. Once the hand-flagged contacts have been
reconciled — every is_student row given is_member — delete the second
half of is_approved and this paragraph with it.
"""

PUBLIC = 'public'
STUDENTS = 'students'


def is_approved(contact):
    """Whether this contact may open gated content."""
    if contact is None or not contact.is_active:
        return False
    # is_member is the flag. is_student is the bridge described above.
    return bool(contact.is_member or contact.is_student)


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
