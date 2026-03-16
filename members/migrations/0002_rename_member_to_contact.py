from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0001_initial'),
        ('consultations', '0001_initial'),
        ('staff_mgmt', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Member',
            new_name='Contact',
        ),
        migrations.RenameField(
            model_name='datafile',
            old_name='member',
            new_name='contact',
        ),
        migrations.AlterField(
            model_name='contact',
            name='is_member',
            field=models.BooleanField(default=False),
        ),
        migrations.RemoveConstraint(
            model_name='contact',
            name='unique_member_name_phone',
        ),
        migrations.AddConstraint(
            model_name='contact',
            constraint=models.UniqueConstraint(fields=['full_name', 'phone'], name='unique_contact_name_phone'),
        ),
    ]
