from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0006_soilhealthcard'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuestionPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_text', models.TextField()),
                ('crop_disease', models.CharField(max_length=120)),
                ('photo', models.ImageField(blank=True, null=True, upload_to='question_posts/%Y/%m/%d/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user_preference',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='question_posts',
                        to='api.userpreference',
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
