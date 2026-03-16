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
- **Paces Bootstrap 5** frontend template (static assets in `/Users/kami/websites/Paces`)
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
| `/admin/` | Django Admin | admin |

## Database

PostgreSQL database `jcf_management`. Connection configured via `DATABASE_URL` in `.env`.

## Environment Variables (`.env`)

```
DEBUG=True
SECRET_KEY=<secret>
DATABASE_URL=postgres://localhost:5432/jcf_management
```

## Template Pattern

All pages extend `layouts/dashboard.html` which extends `base.html`. Override these blocks:

- `{% block title %}` — page title
- `{% block page_title %}` — heading shown on page
- `{% block breadcrumb %}` — breadcrumb items
- `{% block content %}` — main content
- `{% block extra_css %}` — additional CSS
- `{% block extra_js %}` — additional JS

Auth pages extend `layouts/auth.html` and override `{% block auth_content %}`.
