# Portal accounts and role-based access

## Staff workflow

Open **Staff → Portal access → Add portal user**. Enter the person's name and sign-in email, optionally link a staff record, choose a role and set an initial password twice. The role summary explains the accessible areas before saving. The staff directory also offers **Set up access** beside records that have no linked account.

Share the sign-in URL, email and initial password securely with the person. No invitation email is sent and plaintext passwords are never retained in the audit history. At first sign-in, the person must enter the initial password and choose a different password. After that, the account menu includes **Change password**.

Manage an account to update its name, email, staff link or role. Reset initial password to invalidate the existing password/sessions and require password setup again. Deactivate access to prevent sign-in without deleting staff or account history; reactivation does not restore an old session. Status changes require an explicit confirmation page and a CSRF-protected POST.

## Roles

| Area | Admin | Administrator | Secretary | Media Operations |
|---|---|---|---|---|
| Contacts, members, students, centres | Manage | Manage | Manage | — |
| Messages, applications, centre requests, subscribers | Manage | Manage | Manage | — |
| Consultations | Manage | Manage | Manage | — |
| Teachings, events, writings | Manage | Manage | — | Manage |
| Website content | Manage | Manage | — | Manage |
| Initiatives and donations | Manage | Manage | — | — |
| Inner Space students and access decisions | Manage | Manage | — | — |
| Staff records, duties, salaries | Manage | Manage | — | — |
| Portal accounts and roles | Manage | — | — | — |

Every recognized role has a tailored overview and can change its own password. These are fixed roles, defined centrally in `accounts/access.py`; staff job titles remain descriptive and do not grant permissions. There are no implied read-only permissions outside the listed areas.

## Enforcement and administrator protections

- `PortalAccessMiddleware` authorizes resolved portal routes before both class and function views run. It covers GET and POST, including existing legacy actions. Unknown roles and unmapped routes inside protected modules are denied.
- Navigation, page finder and dashboard use the same policy. The dashboard does not query or render restricted record/financial sections.
- Existing Inner Space permission checks use `PortalRoleBackend` alongside the route policy. No remote student database or schema changes were made.
- Only system superusers can enter Django admin. A portal Admin role never sets `is_staff` or `is_superuser`; existing Django permission assignments cannot bypass the portal's role boundary. This is an intentional behavior change for legacy `is_staff` accounts.
- Existing superuser accounts are displayed but cannot be edited, reset or deactivated through the portal. Their own password can be changed through the account menu.
- An Admin cannot change their own role, deactivate themselves or use the administrative reset flow on themselves. This keeps at least the acting administrator available. Access mutations lock user rows and recheck the actor, so simultaneous administrator demotions cannot both proceed with stale permissions. PostgreSQL row locking is used in production; SQLite tests do not simulate concurrent row locks.
- Role/email/status changes increment a session version. Django's session authentication hash includes it, invalidating old sessions even if access is subsequently reactivated. Password changes also invalidate previous sessions; a person's own password-change flow preserves their current session using Django's authentication API.
- Password fields use Django validators and hashing, are excluded from exception reports, and do not redisplay on validation errors. Account-management responses are not cached.
- Access history records actor, target, timestamp and action. It records role changes but no passwords. It is an account-management audit trail, not a complete audit of every portal module or changes made directly through Django admin.
- Public website API routes, Paystack callbacks and their existing policies remain unchanged. This work enforces roles for the administration portal; it does not convert all inherited record-changing GET endpoints to POST.

## Rollout

Migration `accounts/0002_profile_worker_user_access_version_and_more.py` adds the optional staff link, password-setup flag, session version and access history table. Existing accounts keep their saved role, password and active state; existing passwords are not forced through setup. Existing accounts with an absent or invalid role have no portal access until an Admin assigns one. Existing superusers retain recovery access.

Apply the migration to the Foundation database before starting the updated application:

```sh
python manage.py migrate --database=default
```

Review existing role assignments before deploying, since the old labels now enforce actual access restrictions. Never migrate the Prisma-owned Inner Space database. The implementation was migrated and exercised only against the isolated local preview/test database; no live users, credentials, payments or external messages were changed.

## Verification

All 24 regression tests passed (15 account/access tests plus 9 existing office tests). Coverage includes role boundaries for GET/POST, account creation and staff linkage, password validation, duplicate email/staff prevention, privilege-field tampering, first-login enforcement, password reset and session revocation, self-lockout/system-admin protection, restricted dashboard data, role-filtered navigation, every existing portal route's policy mapping, unchanged public API access and CSRF protection. System checks, template compilation and the 27-route smoke check also passed. The preview uses synthetic records.

Django authentication behavior follows the [official Django 6.0 authentication documentation](https://docs.djangoproject.com/en/6.0/topics/auth/default/).
