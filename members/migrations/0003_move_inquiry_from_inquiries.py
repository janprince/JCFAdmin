from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Move Inquiry model from inquiries app to members app."""

    dependencies = [
        ('members', '0002_rename_member_to_contact'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Inquiry',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('subject', models.TextField(blank=True)),
                        ('remark', models.TextField(blank=True)),
                        ('guidance', models.TextField(blank=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inquiries', to='members.contact')),
                    ],
                    options={
                        'verbose_name_plural': 'inquiries',
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE inquiries_inquiry RENAME TO members_inquiry',
                    reverse_sql='ALTER TABLE members_inquiry RENAME TO inquiries_inquiry',
                ),
            ],
        ),
    ]
