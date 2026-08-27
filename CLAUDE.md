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

**Django never migrates that database.** `InnerspaceRouter.allow_migrate`
returns `False` for every operation against the alias, and all its models are
`managed = False`. Schema changes are made in the drbaffourjan repo with
`prisma migrate deploy`, then mirrored by hand into `innerspace/models.py`.

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

- **Skin:** Paces ships ~25 CSS skins selected by `data-skin` on `<html>`. This
  app is pinned to **`saas`** (Poppins, `#f2f6fb` body, `#0a74ff` primary).
  `static/paces/js/config.js` restores a cached config from `sessionStorage`, so
  `base.html` re-pins the skin in an inline script after it runs — changing only
  the `<html>` attribute would leave existing sessions on the old skin.
- **Logo is text, not an image.** `templates/partials/_brand.html` (full
  wordmark) and `_brand_mark.html` (monogram, condensed sidebar) are included in
  the sidebar, topbar, and login page. Styles live in `static/jcf/css/brand.css`,
  loaded after `app.min.css`. The `logo.png` / `logo-black.png` / `logo-sm.png`
  files are no longer referenced.
- **Login side photo:** `static/paces/images/auth-jcf.jpg` (JCF training
  programme). `brand.css` also lightens Paces' `.auth-overlay`, which is built
  for a caption we don't render and otherwise greys the photo out.

## Template Pattern

All pages extend `layouts/dashboard.html` which extends `base.html`. Override these blocks:

- `{% block title %}` — page title
- `{% block page_title %}` — heading shown on page
- `{% block breadcrumb %}` — breadcrumb items
- `{% block content %}` — main content
- `{% block extra_css %}` — additional CSS
- `{% block extra_js %}` — additional JS

Auth pages extend `layouts/auth.html` and override `{% block auth_content %}`.
