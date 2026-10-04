import django.db.models.deletion
import django.utils.timezone
import phonenumber_field.modelfields
from django.conf import settings
from django.db import migrations, models

UNITS = [
    ('Media & Communications', 'Teachings, recordings, the website and social media.', 'megaphone', ['media_operations']),
    ('IT', 'Systems, devices and the Foundation Office portal.', 'desktop', ['admin']),
    ('JCF Administration', 'The office, records, consultations and day-to-day operations.', 'briefcase', ['secretary', 'administrator']),
    ('JCF Farms', 'Cultivation, harvest and care of the Foundation’s land.', 'plant', []),
]


def seed(apps, schema_editor):
    ServiceUnit = apps.get_model('staff_mgmt', 'ServiceUnit')
    Worker = apps.get_model('staff_mgmt', 'Worker')
    for name, description, icon, roles in UNITS:
        ServiceUnit.objects.get_or_create(name=name, defaults={'description': description, 'icon': icon, 'portal_roles': roles})
    # Existing records were "people employed by the foundation": a salary
    # means full-time; a zero salary was the column default, not a stipend.
    Worker.objects.filter(allowance__gt=0).update(service_type='full_time')
    Worker.objects.exclude(allowance__gt=0).update(allowance=None)


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0001_initial'),
        ('staff_mgmt', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(name='worker', options={'verbose_name': 'service member'}),
        migrations.RenameField(model_name='worker', old_name='role', new_name='title'),
        migrations.AlterField(model_name='worker', name='title', field=models.CharField(blank=True, max_length=255, verbose_name='Service role')),
        migrations.RenameField(model_name='worker', old_name='salary', new_name='allowance'),
        migrations.AlterField(model_name='worker', name='allowance', field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name='worker', name='allowance_currency', field=models.CharField(default='GHS', max_length=3)),
        migrations.AddField(model_name='worker', name='service_type', field=models.CharField(choices=[('full_time', 'Full-time'), ('part_time', 'Part-time'), ('volunteer', 'Volunteer')], default='volunteer', max_length=20)),
        migrations.AddField(model_name='worker', name='status', field=models.CharField(choices=[('active', 'Active'), ('on_leave', 'On leave'), ('inactive', 'Inactive')], default='active', max_length=20)),
        migrations.AddField(model_name='worker', name='started_on', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='worker', name='ended_on', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='worker', name='availability', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='worker', name='skills', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='worker', name='emergency_name', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='worker', name='emergency_phone', field=phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, region=None)),
        migrations.AddField(model_name='worker', name='notes', field=models.TextField(blank=True)),
        migrations.CreateModel(
            name='ServiceUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('description', models.CharField(blank=True, help_text='One line on what this unit looks after.', max_length=255)),
                ('icon', models.CharField(choices=[('megaphone', 'Megaphone'), ('desktop', 'Computer'), ('briefcase', 'Briefcase'), ('plant', 'Plant'), ('hand-heart', 'Hand and heart'), ('bowl-food', 'Kitchen'), ('music-notes', 'Music'), ('broom', 'Upkeep'), ('car', 'Transport'), ('first-aid', 'Care'), ('book-open-text', 'Teaching'), ('users-three', 'People')], default='users-three', max_length=30)),
                ('portal_roles', models.JSONField(blank=True, default=list)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lead', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='units_led', to='staff_mgmt.worker')),
            ],
            options={'ordering': ['name']},
        ),
        migrations.AddField(model_name='worker', name='unit', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='members', to='staff_mgmt.serviceunit')),
        migrations.AddField(model_name='worker', name='other_units', field=models.ManyToManyField(blank=True, related_name='supporting_members', to='staff_mgmt.serviceunit')),
        migrations.CreateModel(
            name='ServiceEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('change', 'Change'), ('milestone', 'Milestone'), ('appreciation', 'Appreciation'), ('check_in', 'Check-in'), ('training', 'Training or retreat'), ('note', 'Note')], default='note', max_length=20)),
                ('occurred_on', models.DateField(default=django.utils.timezone.localdate)),
                ('text', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('worker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='journey', to='staff_mgmt.worker')),
            ],
            options={'ordering': ['-occurred_on', '-created_at', '-pk'], 'verbose_name_plural': 'service entries'},
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
