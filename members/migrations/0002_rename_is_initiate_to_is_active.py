from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='contact',
            old_name='is_initiate',
            new_name='is_active',
        ),
        migrations.AlterField(
            model_name='contact',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Active member of the foundation'),
        ),
    ]
