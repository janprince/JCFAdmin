# Foundation Join page integration

The public website's `/join` page now connects to the Foundation API. It collects details, receives confirmation that they were saved, then shows the existing Telegram invitation. Staff review does not gate that invitation.

## API contract

`POST /api/join-foundation/` accepts JSON without authentication:

```json
{
  "name": "Sample Joiner",
  "email": "joiner@example.com",
  "country": "Ghana",
  "region": "Greater Accra",
  "phone": ""
}
```

| Field | Requirement |
|---|---|
| name | Required; trimmed; maximum 150 characters |
| email | Required valid email; trimmed/lowercased; maximum 254 characters |
| country | Required country name; trimmed; maximum 100 characters |
| region | Optional region/state; maximum 100 characters |
| phone | Optional; maximum 40 input characters; valid international number beginning with + when provided; normalized to E.164 |

Success is HTTP 201 with `{ "status": "registered" }`, returned only after persistence. Invalid data returns HTTP 400 with field-specific errors. The frontend retains inputs on errors and only displays the Telegram invitation after the explicit registered acknowledgement. A timeout can mean the write succeeded but the response was lost; resubmission is safe.

The endpoint deduplicates normalized email addresses with a database uniqueness constraint. Repeated submissions return the same acknowledgement and do not overwrite the original name, location, phone or staff-review status. This prevents an unauthenticated submitter from changing another person's record simply by knowing their email. There is no public list/detail/edit endpoint, and responses reveal neither record IDs nor stored personal details. Unknown input fields cannot set internal review state.

The model is `website.FoundationRegistration`. Its data is separate from `JoinCentreRequest`; `/api/join-centre/` and its centre-specific approval workflow continue unchanged. Foundation registration does not create a staff account, contact/member, newsletter subscription, or approval email. It does not verify email ownership or confirm membership in Telegram.

## Admin workflow

Open **Inbox → Foundation registrations** or the overview's new-registration queue. Admin, Administrator and Secretary roles can use this area; Media Operations cannot read its records or call its review action.

- Search by name, email, country or region.
- Filter by country and New/Reviewed status.
- Use **Mark reviewed** to record the staff member and timestamp. The action requires CSRF-protected POST and is idempotent.
- Use the adjacent **Centre join requests** tab for centre-specific enrolment requests.

Reviewing is an inbox action, not membership approval. The overview count includes only unreviewed registrations. Neither the admin page nor the API asserts that the visitor actually joined Telegram.

## Deployment and configuration

1. Deploy the backend first and run `python manage.py migrate --database=default`. The new schema is in `website/0002_foundationregistration.py`. Apply any pending account/role migration too. Never migrate the Prisma-owned Inner Space database.
2. Configure `CORS_ALLOWED_ORIGINS` with the exact public-site origins. Defaults now include `https://www.jancosmicfoundation.org` and `https://jancosmicfoundation.org`, as well as localhost port 3000. An environment override replaces the default list.
3. Rebuild/deploy the public site with the correct `NEXT_PUBLIC_API_URL` (normally `https://admin.jancosmicfoundation.org/api`). The `/join-foundation/` path is fixed in the client. The old `NEXT_PUBLIC_JOIN_FOUNDATION_PATH` switch is no longer read.
4. Check the form, database persistence, Telegram handoff and inbox against the deployed environment with a controlled registration.

`FOUNDATION_REGISTRATION_RATE` defaults to `20/hour` per identified client IP. This is application throttling using Django's cache. Multi-worker deployments should configure a shared cache and trusted proxy/edge rate limits. As the [DRF documentation](https://www.django-rest-framework.org/api-guide/throttling/) explains, its cache-based throttling is approximate and does not provide denial-of-service protection. It is not a replacement for deployment-level abuse controls.

No existing centre data is migrated or reclassified. No production records, emails, credentials or Telegram memberships were changed during implementation. The migration was applied only to the isolated SQLite preview database.

## Verification

- 34 backend tests passed: the previous 24 plus 10 registration integration tests.
- 22 frontend tests, TypeScript and ESLint passed.
- Migration consistency and `git diff --check` passed.
- Real browser test against the local API: invalid phone feedback preserved inputs; retry without the optional phone saved the registration and focused the Telegram confirmation; matching details then appeared in the admin inbox.
- Tests cover payload validation, optional fields, phone normalization, retries, no record disclosure or unintended enrolment, centre compatibility, inbox roles/filters/review, CSRF, throttling and CORS.

Use `website/test_foundation_registration.py` for API/admin regression coverage and the public site's `tests/giving-and-joining.test.mjs` for client acknowledgement and error handling.
