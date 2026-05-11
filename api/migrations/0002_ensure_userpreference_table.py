from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE TABLE IF NOT EXISTS api_userpreference ("
                "id integer NOT NULL PRIMARY KEY AUTOINCREMENT, "
                "phone_number varchar(25) NOT NULL UNIQUE, "
                "preferred_language varchar(30) NOT NULL DEFAULT '', "
                "created_at datetime NOT NULL, "
                "updated_at datetime NOT NULL"
                ")"
            ),
            reverse_sql="DROP TABLE IF EXISTS api_userpreference",
        ),
    ]
