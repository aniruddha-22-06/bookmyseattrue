from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('movies', '0010_genre_language_filtering'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailDeliveryTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient_email', models.EmailField(max_length=254)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('sent', 'Sent'), ('failed', 'Failed')], default='pending', max_length=12)),
                ('attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('max_attempts', models.PositiveSmallIntegerField(default=5)),
                ('last_error', models.TextField(blank=True)),
                ('context', models.JSONField(blank=True, default=dict)),
                ('next_attempt_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('payment', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='email_task', to='movies.payment')),
            ],
        ),
        migrations.AddIndex(
            model_name='emaildeliverytask',
            index=models.Index(fields=['status', 'next_attempt_at'], name='email_status_next_idx'),
        ),
        migrations.AddIndex(
            model_name='emaildeliverytask',
            index=models.Index(fields=['created_at'], name='email_created_idx'),
        ),
    ]
