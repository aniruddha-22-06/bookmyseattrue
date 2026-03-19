from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .models import Seat, Theater


SEAT_LOCK_TIMEOUT = timedelta(minutes=2)


def lock_expiry(now=None):
    current = now or timezone.now()
    return current + SEAT_LOCK_TIMEOUT


def release_expired_seat_locks(now=None):
    current = now or timezone.now()
    return Seat.objects.filter(
        is_booked=False,
        lock_expires_at__isnull=False,
        lock_expires_at__lte=current,
    ).update(
        locked_by=None,
        lock_expires_at=None,
    )


def release_seat_locks_for_user(user: User, seat_ids):
    if not seat_ids:
        return 0
    return Seat.objects.filter(
        id__in=seat_ids,
        is_booked=False,
        locked_by=user,
    ).update(
        locked_by=None,
        lock_expires_at=None,
    )


def acquire_seat_locks(theater: Theater, seat_ids, user: User):
    normalized_ids = sorted({int(seat_id) for seat_id in seat_ids})
    now = timezone.now()
    expires_at = lock_expiry(now)

    with transaction.atomic():
        seats = list(
            Seat.objects.select_for_update()
            .filter(id__in=normalized_ids, theater=theater)
            .order_by('id')
        )

        if len(seats) != len(normalized_ids):
            return False, 'Invalid seat selection', None

        already_booked = [seat.seat_number for seat in seats if seat.is_booked]
        if already_booked:
            return False, f"Seats already booked: {', '.join(already_booked)}", None

        locked_by_others = [
            seat.seat_number
            for seat in seats
            if seat.locked_by_id
            and seat.locked_by_id != user.id
            and seat.lock_expires_at
            and seat.lock_expires_at > now
        ]
        if locked_by_others:
            return False, f"Seats currently locked by another user: {', '.join(locked_by_others)}", None

        for seat in seats:
            seat.locked_by = user
            seat.lock_expires_at = expires_at

        Seat.objects.bulk_update(seats, ['locked_by', 'lock_expires_at'])

    return True, '', expires_at


def seats_with_invalid_lock_for_user(seats, user: User, now=None):
    current = now or timezone.now()
    invalid = []
    for seat in seats:
        if seat.locked_by_id != user.id or not seat.lock_expires_at or seat.lock_expires_at <= current:
            invalid.append(seat.seat_number)
    return invalid
