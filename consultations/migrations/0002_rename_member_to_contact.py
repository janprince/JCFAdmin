from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0001_initial'),
        ('members', '0002_rename_member_to_contact'),
    ]

    operations = [
        migrations.RenameField(
            model_name='consultation',
            old_name='member',
            new_name='contact',
        ),
    ]
