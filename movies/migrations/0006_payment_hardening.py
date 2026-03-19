# Generated manually for payment hardening

import uuid
from datetime import timedelta

import movies.models
from django.db import migrations, models
from django.utils import timezone


def set_payment_defaults(apps, schema_editor):
    Payment = apps.get_model('movies', 'Payment')
    for payment in Payment.objects.all():
        changed = False

        if not payment.idempotency_key:
            payment.idempotency_key = uuid.uuid4().hex
            changed = True

        if not payment.expires_at:
            payment.expires_at = payment.created_at + timedelta(minutes=15)
            changed = True

        if changed:
            payment.save(update_fields=['idempotency_key', 'expires_at'])


def default_payment_expiry():
    return timezone.now() + timedelta(minutes=15)


class Migration(migrations.Migration):

    dependencies = [
        ('movies', '0005_alter_movie_trailer_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='expires_at',
            field=models.DateTimeField(default=default_payment_expiry, null=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='failure_reason',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='payment',
            name='gateway_status',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='payment',
            name='idempotency_key',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='payment',
            name='provider_signature_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='payment',
            name='verification_source',
            field=models.CharField(blank=True, choices=[('callback', 'Client Callback'), ('webhook', 'Webhook'), ('system', 'System')], default='', max_length=12),
        ),
        migrations.AddField(
            model_name='payment',
            name='webhook_event_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='payment',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed'), ('cancelled', 'Cancelled'), ('expired', 'Expired')], default='pending', max_length=10),
        ),
        migrations.RunPython(set_payment_defaults, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='payment',
            name='expires_at',
            field=models.DateTimeField(default=movies.models.default_payment_expiry),
        ),
        migrations.AlterField(
            model_name='payment',
            name='idempotency_key',
            field=models.CharField(default=movies.models.default_idempotency_key, editable=False, max_length=64, unique=True),
        ),
        migrations.CreateModel(
            name='PaymentWebhookEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider_event_id', models.CharField(max_length=120, unique=True)),
                ('event_type', models.CharField(max_length=120)),
                ('signature_verified', models.BooleanField(default=False)),
                ('payload_hash', models.CharField(max_length=64)),
                ('processed_at', models.DateTimeField(auto_now_add=True)),
                ('payment', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='webhook_events', to='movies.payment')),
            ],
        ),
    ]
