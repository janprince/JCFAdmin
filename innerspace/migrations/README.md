# Migrations in the `innerspace` app

This app owns one table in **JCF's own database**: `AccessGrantLog`
(`innerspace_accessgrantlog`), the audit trail of membership and access-level
changes made from this admin. It migrates like any other JCF table:

```bash
python manage.py migrate innerspace
```

Inner Space students, memberships, payments and access requests belong to
drbaffourjan.com, which owns that database and its Prisma migrations. JCF reads
and changes them through the platform's office API (`innerspace/client.py`) and
has no connection to that database.

`0001` and `0002` once described unmanaged mirrors of the platform's tables;
`0003_remove_platform_models` deletes them from Django's state. None of the
three ever created, altered or dropped a table for those models — `sqlmigrate`
shows every operation as a no-op.
