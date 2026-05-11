from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0007_questionpost'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExpertCommunityPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('target_region', models.CharField(blank=True, default='', max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user_preference',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='expert_posts',
                        to='api.userpreference',
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
