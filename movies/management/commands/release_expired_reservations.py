import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from movies.seat_locking import release_expired_seat_locks


class Command(BaseCommand):
    help = 'Releases expired seat reservations periodically.'

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=int, default=15, help='Polling interval in seconds.')
        parser.add_argument('--run-once', action='store_true', help='Run one cleanup pass and exit.')

    def handle(self, *args, **options):
        interval = max(5, options['interval'])
        run_once = options['run_once']

        while True:
            released = release_expired_seat_locks()
            self.stdout.write(
                f"[{timezone.now().isoformat()}] released_expired_seat_locks={released}"
            )
            if run_once:
                break
            time.sleep(interval)
