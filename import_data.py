#!/usr/bin/env python
"""
Import data from old JCF_management_app (msystem.person, msystem.request)
into new JCF project (members.Contact, members.Inquiry).

Usage:
    python manage.py shell < import_data.py
    # OR
    python manage.py runscript import_data  (if django-extensions installed)
"""

import json
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from datetime import datetime, timezone
from members.models import Contact, Inquiry

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


def normalize_phone(raw_phone):
    """
    Convert old plain phone strings (e.g. '0242860012') to E.164 format
    for PhoneNumberField. Assumes Ghana (+233) if no country code present.
    Returns empty string if input is empty/None.
    """
    if not raw_phone or not raw_phone.strip():
        return ""
    phone = raw_phone.strip()
    # Remove spaces, dashes, dots
    phone = phone.replace(" ", "").replace("-", "").replace(".", "")
    # If it starts with 0 and looks like a Ghanaian number, prepend +233
    if phone.startswith("0") and len(phone) == 10:
        phone = "+233" + phone[1:]
    # If it's already got a + prefix, keep it
    elif not phone.startswith("+"):
        # Try adding +233 for Ghanaian numbers without prefix
        if len(phone) == 9:
            phone = "+233" + phone
        else:
            # Keep as-is and let validation handle it
            phone = "+" + phone
    return phone


def run():
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    # Extract only person and request records
    persons = [item for item in data if item["model"] == "msystem.person"]
    requests = [item for item in data if item["model"] == "msystem.request"]

    print(f"Found {len(persons)} persons and {len(requests)} requests in dump.")

    # Map old PK -> new Contact PK
    old_pk_to_new_pk = {}
    created_count = 0
    skipped_count = 0
    error_count = 0

    # --- Import Persons -> Contacts ---
    for item in persons:
        old_pk = item["pk"]
        fields = item["fields"]

        phone = normalize_phone(fields.get("phone", ""))
        telephone = normalize_phone(fields.get("telephone", ""))

        contact_data = {
            "full_name": fields.get("full_name", ""),
            "gender": fields.get("gender", ""),
            "date_of_birth": fields.get("date_of_birth") or None,
            "phone": phone,
            "telephone": telephone,
            "email": "",  # not in old model
            "profession": fields.get("profession", ""),
            "religion": fields.get("religion", "N/A"),
            "residence": fields.get("residence", ""),
            "hometown": fields.get("hometown", ""),
            "country": fields.get("country", "Ghana"),
            "father_name": fields.get("f_name", ""),
            "mother_name": fields.get("m_name", ""),
            "referral": fields.get("referral", ""),
            "is_member": fields.get("is_client", False),
            "is_student": fields.get("is_student", False),
            "is_active": True,
        }

        try:
            # Check for existing contact with same name+phone to avoid duplicates
            contact, was_created = Contact.objects.get_or_create(
                full_name=contact_data["full_name"],
                phone=contact_data["phone"],
                defaults=contact_data,
            )
            old_pk_to_new_pk[old_pk] = contact.pk

            if was_created:
                # Override created_at with old date_added
                date_added = fields.get("date_added")
                if date_added:
                    Contact.objects.filter(pk=contact.pk).update(
                        created_at=datetime.fromisoformat(date_added).replace(
                            tzinfo=timezone.utc
                        )
                    )
                created_count += 1
            else:
                skipped_count += 1

        except Exception as e:
            error_count += 1
            print(f"  ERROR importing person pk={old_pk} ({fields.get('full_name')}): {e}")

    print(f"\nContacts: {created_count} created, {skipped_count} skipped (duplicates), {error_count} errors")

    # --- Import Requests -> Inquiries ---
    inq_created = 0
    inq_skipped = 0
    inq_errors = 0

    for item in requests:
        fields = item["fields"]
        old_person_pk = fields["person"]

        new_contact_pk = old_pk_to_new_pk.get(old_person_pk)
        if new_contact_pk is None:
            inq_skipped += 1
            print(f"  SKIP request pk={item['pk']}: person pk={old_person_pk} not found in mapping")
            continue

        try:
            Inquiry.objects.create(
                contact_id=new_contact_pk,
                subject=fields.get("request_info", ""),
                remark=fields.get("remark", ""),
                guidance=fields.get("solution", ""),
            )
            inq_created += 1
        except Exception as e:
            inq_errors += 1
            print(f"  ERROR importing request pk={item['pk']}: {e}")

    print(f"Inquiries: {inq_created} created, {inq_skipped} skipped, {inq_errors} errors")
    print("\nDone!")


if __name__ == "__main__":
    run()
else:
    # When piped via: python manage.py shell < import_data.py
    run()
