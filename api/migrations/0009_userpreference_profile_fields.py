from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0008_expertcommunitypost'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreference',
            name='full_name',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='userpreference',
            name='location',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='userpreference',
            name='profile_photo',
            field=models.ImageField(blank=True, null=True, upload_to='profiles/%Y/%m/%d/'),
        ),
    ]
