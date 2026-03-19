from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('movies', '0011_email_delivery_task'),
    ]

    operations = [
        migrations.AddField(
            model_name='movie',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
