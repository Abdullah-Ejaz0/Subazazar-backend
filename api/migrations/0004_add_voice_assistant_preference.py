from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0003_languageonboardingsession'),
    ]

    operations = [
        migrations.AddField(
            model_name='languageonboardingsession',
            name='voice_assistant_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userpreference',
            name='voice_assistant_enabled',
            field=models.BooleanField(default=False),
        ),
    ]
