"""
Database router for the Innerspace platform database.

The Innerspace (drbaffourjan.com) database is owned by Prisma and lives in a
separate Supabase Postgres instance. Django reads and writes it, but must never
own its schema — every table there is described by a Prisma migration, not a
Django one.

Two rules enforce that:

1. Models inheriting `InnerspaceModel` are read from and written to the
   `innerspace` alias.
2. `allow_migrate` returns False for anything targeting that alias, so
   `migrate` can never create, alter or drop a table in it — including by
   accident, and including Django's own contenttypes/auth tables.

Models in this app that do NOT inherit `InnerspaceModel` (the audit log) are
ordinary Django models on the default JCF database and migrate normally.
"""

INNERSPACE_DB = 'innerspace'


class InnerspaceRouter:

    @staticmethod
    def _is_remote(model):
        from innerspace.models import InnerspaceModel

        return isinstance(model, type) and issubclass(model, InnerspaceModel)

    def db_for_read(self, model, **hints):
        return INNERSPACE_DB if self._is_remote(model) else None

    def db_for_write(self, model, **hints):
        return INNERSPACE_DB if self._is_remote(model) else None

    def allow_relation(self, obj1, obj2, **hints):
        # Relations between two Innerspace models are fine (same database).
        # Anything crossing the boundary is refused rather than silently
        # producing a join that cannot work.
        remote1 = self._is_remote(type(obj1))
        remote2 = self._is_remote(type(obj2))
        if remote1 and remote2:
            return True
        if remote1 or remote2:
            return False
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == INNERSPACE_DB:
            return False
        return None
