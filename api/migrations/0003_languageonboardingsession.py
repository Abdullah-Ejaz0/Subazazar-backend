from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0002_ensure_userpreference_table'),
    ]

    operations = [
        migrations.CreateModel(
            name='LanguageOnboardingSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('preferred_language', models.CharField(max_length=30)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
            ],
        ),
    ]
