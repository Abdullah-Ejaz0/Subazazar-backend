from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0005_scanimageupload'),
    ]

    operations = [
        migrations.CreateModel(
            name='SoilHealthCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('land_name', models.CharField(blank=True, default='', max_length=120)),
                ('ph', models.FloatField()),
                ('nitrogen', models.FloatField()),
                ('hydrogen', models.FloatField()),
                ('phosphate', models.FloatField()),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user_preference',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='soil_health_cards',
                        to='api.userpreference',
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
