"""
Verify that the Django models still line up with the Prisma-owned schema.

The Innerspace database is migrated from the drbaffourjan repo, so a schema
change there can silently break this admin. Run this after any Prisma
migration — and in CI if you like — to find out before a member of staff does.

    python manage.py innerspace_check
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from innerspace.models import InnerspaceModel, Membership, MembershipStatus, Payment, Student
from innerspace.routers import INNERSPACE_DB

MODELS = [Student, Membership, Payment]

# Columns we deliberately do not map. Password hashes have no business being
# loaded into an admin page, and nothing here needs to read them.
IGNORED_COLUMNS = {
    'users': {'password'},
}


class Command(BaseCommand):
    help = 'Check the Innerspace database connection and model/column mapping.'

    def handle(self, *args, **options):
        if INNERSPACE_DB not in connections:
            raise CommandError(
                'No "innerspace" database configured. '
                'Set INNERSPACE_DATABASE_URL in .env.'
            )

        connection = connections[INNERSPACE_DB]
        try:
            connection.ensure_connection()
        except Exception as exc:
            raise CommandError(f'Cannot connect to the Innerspace database: {exc}')
        self.stdout.write(self.style.SUCCESS('Connected to the Innerspace database.'))

        problems = 0
        for model in MODELS:
            problems += self.check_model(connection, model)

        problems += self.check_enum_binding()
        problems += self.check_migrations_blocked()

        if problems:
            raise CommandError(f'{problems} problem(s) found.')
        self.stdout.write(self.style.SUCCESS('All checks passed.'))

    # ------------------------------------------------------------------

    def check_model(self, connection, model):
        table = model._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT column_name, is_nullable, column_default '
                'FROM information_schema.columns WHERE table_name = %s',
                [table],
            )
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

        if not columns:
            self.stdout.write(self.style.ERROR(f'{table}: table not found.'))
            return 1

        problems = 0
        expected = {field.column for field in model._meta.local_fields}
        missing = expected - set(columns)
        if missing:
            self.stdout.write(self.style.ERROR(
                f'{table}: model expects columns that do not exist: {sorted(missing)}'
            ))
            problems += 1

        extra = set(columns) - expected - IGNORED_COLUMNS.get(table, set())
        if extra:
            self.stdout.write(self.style.WARNING(
                f'{table}: database has columns the model does not map: {sorted(extra)}'
            ))

        # The trap that `updatedAt` sets: a NOT NULL column with no database
        # default, mapped to a Django field that is happy to send NULL. Every
        # insert would be rejected by Postgres. Fields that are simply required
        # are not interesting here — the service layer always sets those, and a
        # miss surfaces immediately as an IntegrityError.
        for name, (is_nullable, default) in columns.items():
            if name not in expected or is_nullable == 'YES' or default is not None:
                continue
            field = next(f for f in model._meta.local_fields if f.column == name)
            if field.null:
                self.stdout.write(self.style.ERROR(
                    f'{table}.{name}: column is NOT NULL with no default, but the '
                    f'model field allows null. Inserts will fail.'
                ))
                problems += 1

        if not problems:
            self.stdout.write(f'{table}: {len(expected)} columns mapped correctly.')
        return problems

    def check_enum_binding(self):
        """Prove that a plain Python string still compares against a PG enum.

        This works because Django's psycopg3 backend binds parameters client
        side. If someone ever turns on OPTIONS['server_side_binding'], this is
        the check that catches it.
        """
        try:
            Membership.objects.filter(status=MembershipStatus.ACTIVE).exists()
        except Exception as exc:
            self.stdout.write(self.style.ERROR(
                f'Enum comparison failed — is server_side_binding enabled? {exc}'
            ))
            return 1
        self.stdout.write('Enum parameter binding works.')
        return 0

    def check_migrations_blocked(self):
        from django.db import router

        for model in MODELS:
            if router.allow_migrate(INNERSPACE_DB, model._meta.app_label,
                                    model_name=model._meta.model_name) is not False:
                self.stdout.write(self.style.ERROR(
                    'The router is NOT blocking migrations against the Innerspace '
                    'database. Check DATABASE_ROUTERS in settings.'
                ))
                return 1
        self.stdout.write('Migrations are blocked against the Innerspace database.')
        return 0
