# Migrations in the `innerspace` app

## Never migrate the Innerspace database from Django

The `innerspace` alias points at the **drbaffourjan.com student platform**
database. Its schema is owned by Prisma, in
`drbaffourjan/prisma/schema.prisma`.

A Django migration against it would put the two systems permanently out of step.
`prisma migrate` would then read the difference as drift and offer to reset the
database — destroying live student, membership and payment data.

This is enforced, not merely requested:

- `InnerspaceRouter.allow_migrate` returns `False` for every operation against
  the alias.
- Every remote model inherits `InnerspaceModel`, which is `managed = False`, so
  the autodetector emits no DDL for them.

**Do not weaken either.** If you find yourself editing `routers.py` to let a
migration through, stop — the change you want belongs in the Prisma schema.

## Migrations that DO belong here

The app owns one real table in **JCF's own database**: `AccessGrantLog`, the
audit trail for membership and access-level changes.

Django prefixes tables with the app label, so it is called
`innerspace_accessgrantlog` — which reads as though it lives in the Innerspace
database. It does not. `AccessGrantLog` is a plain `models.Model`; only
`InnerspaceModel` subclasses (`Student`, `Membership`, `Payment`,
`AccessRequest`) are routed to Supabase.

So changes to the audit log migrate normally:

```bash
python manage.py makemigrations innerspace
python manage.py migrate innerspace
```

Note that `makemigrations` will also record `CreateModel` operations for the
unmanaged models. That is expected Django behaviour and produces no DDL — the
operations exist only to keep migration state consistent.

## When the Prisma schema changes

1. Apply it in the drbaffourjan repo: `npx prisma migrate deploy`
   (never `migrate dev` — that schema has drifted from its migration files and
   `dev` would offer to reset).
2. Mirror the change by hand in `innerspace/models.py`, with an explicit
   `db_column` on every field.
3. Verify: `python manage.py innerspace_check`.

Mapping traps that check exists to catch: case-sensitive table names, mixed
snake_case/camelCase columns, cuid primary keys with no database default,
`updatedAt` being NOT NULL with no default, and `timestamp(3)` columns that
carry no time zone (see `innerspace/fields.py`).
