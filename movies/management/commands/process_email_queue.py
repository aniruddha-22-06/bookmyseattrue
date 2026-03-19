import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from movies.email_queue import process_single_email_task
from movies.models import EmailDeliveryTask


class Command(BaseCommand):
    help = 'Process booking confirmation email queue with retry support.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Process eligible emails once and exit.')
        parser.add_argument('--interval', type=int, default=10, help='Polling interval in seconds for daemon mode.')
        parser.add_argument('--batch-size', type=int, default=20, help='Max emails per cycle.')

    def handle(self, *args, **options):
        once = options['once']
        interval = max(1, options['interval'])
        batch_size = max(1, options['batch_size'])

        self.stdout.write(self.style.SUCCESS('Email queue processor started'))
        while True:
            processed = self._process_batch(batch_size=batch_size)
            self.stdout.write(f'Processed {processed} email task(s) at {timezone.now().isoformat()}')
            if once:
                break
            time.sleep(interval)

    def _process_batch(self, batch_size):
        now = timezone.now()
        processed = 0
        eligible_ids = list(
            EmailDeliveryTask.objects.filter(
                status__in=[EmailDeliveryTask.STATUS_PENDING, EmailDeliveryTask.STATUS_PROCESSING],
                next_attempt_at__lte=now,
                attempt_count__lt=F('max_attempts'),
            )
            .order_by('next_attempt_at', 'id')
            .values_list('id', flat=True)[:batch_size]
        )

        for task_id in eligible_ids:
            with transaction.atomic():
                task = EmailDeliveryTask.objects.select_for_update().get(id=task_id)
                if process_single_email_task(task):
                    processed += 1
        return processed
