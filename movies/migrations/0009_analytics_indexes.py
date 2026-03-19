from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('movies', '0008_seat_lock_fields'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='booking',
            index=models.Index(fields=['booked_at'], name='booking_booked_at_idx'),
        ),
        migrations.AddIndex(
            model_name='booking',
            index=models.Index(fields=['movie', 'booked_at'], name='booking_movie_time_idx'),
        ),
        migrations.AddIndex(
            model_name='booking',
            index=models.Index(fields=['theater', 'booked_at'], name='booking_theater_time_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['status', 'created_at'], name='payment_status_time_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['movie', 'created_at'], name='payment_movie_time_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['theater', 'created_at'], name='payment_theater_time_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['user', 'status'], name='payment_user_status_idx'),
        ),
    ]
