from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('staff_mgmt', '0001_initial'),
        ('members', '0002_rename_member_to_contact'),
    ]

    operations = [
        migrations.RenameField(
            model_name='worker',
            old_name='member',
            new_name='contact',
        ),
        migrations.RenameField(
            model_name='representative',
            old_name='member',
            new_name='contact',
        ),
    ]
