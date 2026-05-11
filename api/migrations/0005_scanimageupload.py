from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0004_add_voice_assistant_preference'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScanImageUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='scan_uploads/%Y/%m/%d/')),
                ('source', models.CharField(choices=[('camera', 'Camera'), ('gallery', 'Gallery')], max_length=20)),
                ('analysis_status', models.CharField(default='pending', max_length=20)),
                ('analysis_result', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user_preference',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='scan_uploads',
                        to='api.userpreference',
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
