from django.db import migrations, models

SEED = [
    ('Student Platform', 'https://www.drbaffourjan.com', 'platform', 'students', 'Inner Space courses and lessons for enrolled students.', 1),
    ('Foundation Website', 'https://www.jancosmicfoundation.org', 'platform', 'everyone', 'Public home of the Foundation: events, centres, giving and joining.', 2),
]


def seed(apps, schema_editor):
    DigitalResource = apps.get_model('resources', 'DigitalResource')
    for title, url, category, audience, description, position in SEED:
        DigitalResource.objects.get_or_create(url=url, defaults=dict(
            title=title, category=category, audience=audience, description=description, position=position))


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='DigitalResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=120)),
                ('url', models.URLField(max_length=500, verbose_name='Link')),
                ('category', models.CharField(choices=[('platform', 'Platforms & websites'), ('lessons', 'Lessons & courses'), ('media', 'Social media & channels'), ('forms', 'Forms & tools'), ('other', 'Other')], default='platform', max_length=20)),
                ('audience', models.CharField(choices=[('everyone', 'Everyone'), ('students', 'Students'), ('members', 'Members'), ('staff', 'Service team')], default='everyone', max_length=20, verbose_name='Who uses it')),
                ('language', models.CharField(blank=True, help_text='Only if the content is in one language, e.g. English or Twi.', max_length=40)),
                ('description', models.CharField(blank=True, help_text='One line on what it is or when to share it.', max_length=255)),
                ('share_privately', models.BooleanField(default=False, help_text='For unlisted lessons and private links. Shown as a reminder beside the link.', verbose_name='Share only with its audience')),
                ('position', models.PositiveSmallIntegerField(default=0, help_text='Lower numbers appear first within their group.')),
                ('is_active', models.BooleanField(default=True, verbose_name='Show on the resources page')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['position', 'title']},
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
