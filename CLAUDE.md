# JCF Management Dashboard

Django management system for Jan Cosmic Foundation (JCF). Rebuilt from legacy Django 4 + Bootstrap "Hyper" app into Django 6 + PostgreSQL + Paces Bootstrap 5 admin template.

## Quick Start

```bash
source .venv/bin/activate
python manage.py runserver
```

- **Login:** `admin@jcf.org` / `admin123`
- **Admin:** `/admin/`

## Tech Stack

- **Django 6.0.3** (Python 3.13) with PostgreSQL
- **Paces Bootstrap 5** admin template (static assets in `static/paces/`)
- **Paces Bootstrap 5** frontend template (static assets in `/Users/kami/websites/Paces`) -> Remember this is the frontend templates we are using for this project
- **Key packages:** django-environ, django-phonenumber-field, Pillow

## Project Structure

```
config/              # Django project (settings, urls, wsgi)
accounts/            # Custom User (email login), Profile, auth backend, signals
members/             # Member, DataFile — member/student records + file attachments
consultations/       # Consultation — booking & scheduling for spiritual master
inquiries/           # Inquiry — inline on member detail page (subject, remark, guidance)
staff_mgmt/          # Worker, Representative — foundation staff & reps
teachings/           # Teaching — spiritual content tracking (topic, format, language, status)
dashboard/           # Analytics view with ApexCharts
innerspace/          # Innerspace student platform — SECOND, Prisma-owned database
templates/           # Project-level templates
  base.html          # HTML skeleton (CSS/JS)
  layouts/           # dashboard.html (topbar+sidebar+footer), auth.html (login)
  partials/          # _topbar.html, _sidebar.html, _footer.html, _messages.html
  accounts/          # login.html
  dashboard/         # analytics.html
  members/           # member_list.html, member_form.html, member_detail.html
  consultations/     # consultation_list.html, consultation_form.html
  staff/             # staff_list.html, staff_form.html
  teachings/         # teaching_list.html, teaching_form.html
  404.html, 500.html
static/paces/        # Paces template assets (css, js, plugins, images)
```

## Architecture Decisions

- **Custom User model** (`accounts.User`) with `USERNAME_FIELD = 'email'` — login via email
- **Email auth backend** (`accounts.backends.EmailBackend`) + default `ModelBackend`
- **Profile auto-created** via post_save signal on User
- **Class-based views** throughout — ListView, CreateView, UpdateView, DetailView, DeleteView
- **Inquiries** are inline on member detail page (modals for add/edit)
- **PhoneNumberField** for phone validation (replaces plain CharField)
- **`father_name`/`mother_name`** (was `f_name`/`m_name` in legacy)
- **`salary`** is `DecimalField` (was CharField in legacy app)
- **`scheduled_date`** on Consultation (avoid shadowing Python `date`)
- **`format`** on Teaching (was `type`/`content_type` — avoid shadowing builtins)

## Common Commands

```bash
source .venv/bin/activate
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py shell
python manage.py check
python manage.py innerspace_check   # verify the Innerspace DB mapping
```

## URL Structure

| Path | View | App |
|------|------|-----|
| `/` | Redirect → `/dashboard/` | config |
| `/login/` | LoginView | accounts |
| `/logout/` | LogoutView | accounts |
| `/dashboard/` | AnalyticsView | dashboard |
| `/members/` | MemberListView | members |
| `/members/students/` | StudentListView | members |
| `/members/add/` | MemberCreateView | members |
| `/members/<pk>/` | MemberDetailView | members |
| `/members/<pk>/edit/` | MemberUpdateView | members |
| `/members/<pk>/delete/` | MemberDeleteView | members |
| `/members/<pk>/files/` | add_datafiles | members |
| `/consultations/` | ConsultationListView | consultations |
| `/consultations/book/` | ConsultationCreateView | consultations |
| `/consultations/<pk>/edit/` | ConsultationUpdateView | consultations |
| `/consultations/<pk>/complete/` | mark_complete | consultations |
| `/consultations/<pk>/delete/` | delete_consultation | consultations |
| `/inquiries/add/<pk>/` | add_inquiry | inquiries |
| `/inquiries/<pk>/edit/` | update_inquiry | inquiries |
| `/inquiries/<pk>/delete/` | delete_inquiry | inquiries |
| `/staff/` | StaffListView | staff_mgmt |
| `/staff/add/` | StaffCreateView | staff_mgmt |
| `/staff/<pk>/edit/` | StaffUpdateView | staff_mgmt |
| `/teachings/` | TeachingListView | teachings |
| `/teachings/add/` | TeachingCreateView | teachings |
| `/teachings/<pk>/edit/` | TeachingUpdateView | teachings |
| `/innerspace/students/` | StudentListView | innerspace |
| `/innerspace/students/<pk>/` | StudentDetailView | innerspace |
| `/innerspace/students/<pk>/grant/` | GrantAccessView | innerspace |
| `/innerspace/students/<pk>/extend/` | ExtendAccessView | innerspace |
| `/innerspace/students/<pk>/revoke/` | RevokeAccessView | innerspace |
| `/innerspace/students/<pk>/level/` | SetLevelView | innerspace |
| `/innerspace/requests/` | AccessRequestListView | innerspace |
| `/innerspace/requests/<pk>/approve/` | ApproveRequestView | innerspace |
| `/innerspace/requests/<pk>/decline/` | DeclineRequestView | innerspace |
| `/admin/` | Django Admin | admin |

## Database

PostgreSQL database `jcf_management`. Connection configured via `DATABASE_URL` in `.env`.

### Second database: Innerspace (`innerspace` alias)

The `innerspace` app reads and writes the **drbaffourjan.com** student platform
database — a separate Supabase Postgres instance whose schema is owned by
Prisma, in `/Users/kami/Projects/Kami/JIVA/drbaffourjan/prisma/schema.prisma`.

> ### NEVER run migrations against the Innerspace database from Django
>
> That schema belongs to Prisma. A Django migration touching it would put the
> two systems permanently out of step with each other, and `prisma migrate`
> would then see the difference as drift and offer to reset — destroying live
> student, membership and payment data.
>
> This is enforced, not merely asked for: `InnerspaceRouter.allow_migrate`
> returns `False` for every operation against the alias, and every remote model
> is `managed = False`. Do not weaken either. Schema changes are made in the
> drbaffourjan repo with `prisma migrate deploy`, then mirrored by hand into
> `innerspace/models.py` and verified with `manage.py innerspace_check`.

#### But `manage.py migrate` is still safe — and still required

The rule above is about the *database*, not the command. The `innerspace` Django
app owns one ordinary table in **JCF's own database**, and it needs migrating
like anything else.

The trap is the name. Django prefixes tables with the app label, so the audit
log is called `innerspace_accessgrantlog` — but it lives in JCF's database, not
Innerspace's. Anything the router sends to Supabase inherits `InnerspaceModel`
(`Student`, `Membership`, `Payment`, `AccessRequest`); `AccessGrantLog` is a
plain `models.Model` and stays local.

So when you see an error like `column innerspace_accessgrantlog.previous_level
does not exist`, the fix is a normal Django migration:

```bash
python manage.py migrate innerspace
```

Which command, which database:

| Change | Run from | Command | Hits |
|---|---|---|---|
| Anything in JCF's own tables, incl. `innerspace_accessgrantlog` | `JCF` | `python manage.py migrate` | JCF DB |
| Anything in the student platform schema | `drbaffourjan` | `npx prisma migrate deploy` | Innerspace DB |
| Never | `JCF` | — | Innerspace DB |

`manage.py migrate` cannot reach the Innerspace database even if pointed at it —
the router refuses. Running it is safe.

Run `python manage.py innerspace_check` after any Prisma migration — it
compares model fields against the live columns and reports drift.

Mapping rules that are easy to get wrong:

- **Table names are case-sensitive.** Only `User` is `@@map`ped (to `users`);
  `Membership` and `Payment` keep their capitals.
- **Column naming is inconsistent.** `users` is snake_case except `accessLevel`;
  `Membership` and `Payment` are camelCase throughout. Always set `db_column`.
- **`id` columns are TEXT with no database default.** Prisma generates cuids in
  the app layer, so `innerspace/cuid.py` does too.
- **`updatedAt` is NOT NULL with no default.** Every write must set it.
- **Timestamps are `timestamp(3)`, not `timestamptz`.** Use
  `PrismaDateTimeField` (`innerspace/fields.py`), which converts naive UTC from
  the database into aware datetimes and back.
- **Statuses are native Postgres enums.** They work as `CharField` only because
  Django's psycopg3 backend binds parameters client-side. Never set
  `OPTIONS['server_side_binding'] = True` on this alias.

All writes go through `innerspace/services.py`, which stamps `updatedAt`,
records a `CASH` payment, and writes an `AccessGrantLog` entry (stored in JCF's
own database, so the audit trail is independent of the student platform).

Revoking access takes effect on the student's next sign-in, not immediately —
the website carries `hasMembership` in a JWT and only re-reads the database when
that flag is false.

### Access levels

`users.accessLevel` (`BEGINNER | INTERMEDIATE | ADVANCED`) decides which courses
a student can open on the website: their own level and everything below it.
Courses above stay visible but locked, with a "request access" button that
writes an `access_requests` row — the queue at `/innerspace/requests/`.

Who gets what:

- **Paid online** → `ADVANCED`, set by the website's checkout and webhook
  handlers. The membership is sold as "lifetime access to all courses".
- **Free signup** → `BEGINNER` (the column default).
- **Enrolled at the office** → whatever staff choose in the grant modal. This
  is the main reason levels exist.

Unlike a membership change, **a level change takes effect on the student's very
next page load** — the website reads `accessLevel` from the database on every
render rather than caching it in the session token. No sign-out needed.

`approve_access_request()` refuses to lower a level; use `set_access_level()`
for that. Both live in `innerspace/services.py` and write an `AccessGrantLog`
entry with `previous_level`/`new_level`.

Decision emails to students are sent from Django (`innerspace/notifications.py`)
— it is the actor and already has a mailer. Sends are best-effort: the decision
is committed first, and a mail failure surfaces as a warning, never a rollback.

## Environment Variables (`.env`)

```
DEBUG=True
SECRET_KEY=<secret>
DATABASE_URL=postgres://localhost:5432/jcf_management
# Innerspace platform DB. Supabase session pooler or direct connection —
# not the transaction pooler. Blank disables the Innerspace pages.
INNERSPACE_DATABASE_URL=postgres://...
```

## Theme & Branding

- Paces' `saas` skin remains as a compatibility layer. The Foundation office
  direction is defined in `static/jcf/css/office.css`, loaded last. It uses
  **Public Sans**, self-hosted in `static/jcf/fonts/` with its SIL license;
  no Google Fonts request is needed. Use a single sans family for UI and headings.
- Indigo (`#393477`) actions, deep indigo (`#24243e`) navigation, white surfaces,
  a cool neutral (`#f4f5f8`) canvas, and gold (`#d3ae63`) navigation markers.
  Semantic status colors remain distinct. Light/dark modes both work.
- Sidebar and topbar colors are pinned dark/light in `base.html`, including
  cached Paces config. Match selector specificity when overriding Paces skins.
- `dashboard/navigation.py` defines task groups and resolves the most specific
  active URL. `{% office_navigation %}` renders the sidebar. The page finder
  uses those authorized navigation links; it searches pages, not records.
- Keep the shared list/form components in `static/jcf/css/ui.css`, layout in
  `shell.css`, and final visual tokens in `office.css`. Do not edit minified
  Paces assets for application styling.
- Icons are vendored Phosphor (`ph ph-*`, `ph-light ph-*`). Use descriptive
  accessible names on icon-only controls. Status colors must also have text.
- The text logo reads “JCF / Foundation office.” Login uses the existing real
  Foundation photograph (`static/paces/images/auth-jcf.jpg`).
- The overview prioritizes incoming work, consultations, giving, gatherings,
  and draft publishing. Financial totals must be grouped by currency.
- General donations have a null cause. Centre requests and general Foundation
  registrations are different workflows; the latter API remains outstanding.
- Forms with `_form_actions.html` get unsaved-change feedback. Errors and
  warnings remain until dismissed; only success feedback auto-dismisses.
- Review rationale, validation, and remaining priorities are documented in
  `docs/admin-experience-review-2026-09-23.md`. Regression tests live in
  `dashboard/test_office.py`.

## Template Pattern

All pages extend `layouts/dashboard.html` which extends `base.html`. Override these blocks:

- `{% block title %}` — browser tab title
- `{% block page_title %}` — heading shown on page
- `{% block page_subtitle %}` — optional one-line description under the heading
- `{% block page_actions %}` — buttons on the right of the page header
- `{% block breadcrumb %}` — `<li>` items (Dashboard › Parent › Current). Only the
  parent is shown, as a "‹ Parent" back link, and only on nested pages
- `{% block content %}` — main content
- `{% block extra_css %}` — additional CSS
- `{% block extra_js %}` — additional JS

Page patterns — copy the nearest existing page rather than starting fresh:

- **List:** `members/contact_list.html`. One `.card.jcf-list`: `_tabs.html`
  (tabs built in the view with `dashboard.listing.tabs()` / `count_by()`) →
  `.jcf-toolbar` form (`_search.html`, `{% keep_params 'status' %}`, selects
  that submit on change, no Search button) → `.jcf-table` → pager.
  Rows use `_person.html`, `_row_menu.html`, `_empty_row.html`.
- **Small create forms** live in a modal on the list page (`teachings/teaching_list.html`);
  add `data-jcf-open` when `form.errors` so it re-opens after a failed POST.
- **Form page:** `.jcf-form` with `section.card` blocks, or `.jcf-form-grid`
  (main + sticky side column) for rich content (`events/event_form.html`).
  Render fields with `partials/_field.html`; end with `_form_actions.html`.
- **Grid of cards:** `.jcf-grid` of `.jcf-tile` (`centres/centre_list.html`).
- **Delete confirmation:** set `template_name = 'confirm_delete.html'` on a DeleteView.
- Confirm prompts use `data-confirm="…"` (handled in `static/jcf/js/ui.js`),
  not inline `onclick`.

Auth pages extend `layouts/auth.html` and override `{% block auth_content %}`.

## Portal accounts and role policy

- Staff directory records and portal accounts are separate. Account management lives at `/staff/access/`; optional `Profile.worker` links them.
- `accounts/access.py` is the authoritative role policy; `accounts/middleware.py` enforces portal routes and first-login password setup. Add a policy entry when adding protected modules/routes.
- Admin manages portal access; Administrator manages all operational areas; Secretary manages community, inbox and consultations; Media Operations manages publishing/content. Django admin is reserved for system superusers.
- Navigation, dashboard sections and Inner Space action permissions derive from that policy. Never rely only on hiding a link.
- Password reset/deactivation are CSRF-protected POSTs. Account changes are audited; no plaintext password logging or email. New/reset initial passwords must be changed on first sign-in.
- Apply the accounts migration to the default Foundation DB when deploying. See `docs/portal-access.md` for rollout, legacy-account behavior and validation; regression tests are in `accounts/test_portal_access.py`.
