# Consultation booking form

Replaces the questionnaire the office sent on WhatsApp to people who are not yet in contacts.

## How the office uses it

1. On **Consultations** or **Consultations → Booking requests**, open **Share booking form** and choose **Copy WhatsApp message** (or **Open in WhatsApp**). The link is `/book/` on the portal's own domain; no sign-in is needed to fill it in.
2. The person answers on their phone: full name, date of birth (the day of the week is shown and stored for them; if they don't know the date they pick the day instead), profession, religion, home town/region, current residence, phone, optional email, how they heard about Dr. Jan, whether they'd like to meet in person or remotely, and an optional note.
3. The request appears under **Booking requests** with a waiting badge in the sidebar and on the overview. **Book** opens the booking form with the contact and their preferred mode already chosen; saving marks the request booked and links the consultation.
4. **Close without booking** keeps the contact. **Remove as spam** deletes the request and the contact only when this form created that contact and nothing else uses it.

## What a submission writes

| Answer | Contact field |
|---|---|
| Full name | `full_name` (extra spaces removed) |
| Date of birth / day of birth | `date_of_birth`, or `day_of_birth` when the date is unknown (`Contact.birth_weekday` gives the day either way) |
| Profession, religion | `profession`, `religion` |
| Home town / region | `hometown` |
| Current residence | `residence` |
| Telephone | `phone` (E.164; Ghanaian numbers may be typed locally, e.g. 024…) |
| How they heard | `referral`, e.g. "A friend or family member — Kofi Ofori" |

A submission is matched to an existing contact only when **both the name (ignoring case) and the phone** match — families often share a phone. A match is linked and **never changed**; staff compare the request with the contact record. Everyone else becomes a new contact. A second submission from the same name and phone while their first request is waiting is ignored.

## Abuse controls

- A hidden field catches form-filling bots; they see the thank-you page and nothing is saved.
- `CONSULTATION_REQUEST_RATE` (default `10/hour`) limits submissions per client address using Django's cache. As with the Join form, this is approximate; use a shared cache and edge rate limits in multi-worker deployments.
- The thank-you page shows only the first name and phone the person just entered, from their own session.

## Access

`/book/` is public (`booking` namespace, outside the portal middleware). Booking requests are in the `consultations` area: Admin, Administrator and Secretary. Media Operations cannot see them.

## Deploying

Run `python manage.py migrate` against the Foundation database: `members/0004_contact_day_of_birth` and `consultations/0002_booking_requests`. Regression tests: `consultations/test_booking.py`.
