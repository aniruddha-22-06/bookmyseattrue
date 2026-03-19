from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Case, Count, F, FloatField, Q, Sum, Value, When
from django.db.models.functions import Coalesce, ExtractHour
from django.utils import timezone

from .models import Booking, Payment, Theater


ANALYTICS_CACHE_KEY = 'admin_analytics_snapshot_v1'
ANALYTICS_CACHE_TTL_SECONDS = 60


def invalidate_admin_analytics_cache():
    cache.delete(ANALYTICS_CACHE_KEY)


def _money_inr(paise):
    if paise is None:
        return 0.0
    return float(Decimal(paise) / Decimal('100'))


def build_admin_analytics_snapshot():
    now = timezone.now()
    start_day = now - timedelta(days=1)
    start_week = now - timedelta(days=7)
    start_month = now - timedelta(days=30)

    paid_payments = Payment.objects.filter(status=Payment.STATUS_PAID)
    revenue = paid_payments.aggregate(
        daily=Coalesce(Sum('amount_paise', filter=Q(created_at__gte=start_day)), Value(0)),
        weekly=Coalesce(Sum('amount_paise', filter=Q(created_at__gte=start_week)), Value(0)),
        monthly=Coalesce(Sum('amount_paise', filter=Q(created_at__gte=start_month)), Value(0)),
    )

    popular_movies = (
        Booking.objects.values('movie_id', 'movie__name')
        .annotate(total_bookings=Count('id'))
        .order_by('-total_bookings')[:5]
    )

    busiest_theaters = (
        Theater.objects.values('id', 'name', 'movie__name')
        .annotate(
            total_seats=Count('seats', distinct=True),
            booked_seats=Count('seats', filter=Q(seats__is_booked=True), distinct=True),
        )
        .annotate(
            occupancy_rate=Case(
                When(total_seats=0, then=Value(0.0)),
                default=100.0 * F('booked_seats') / F('total_seats'),
                output_field=FloatField(),
            ),
        )
        .order_by('-occupancy_rate', '-booked_seats')[:5]
    )

    peak_booking_hours = (
        Booking.objects.annotate(hour=ExtractHour('booked_at'))
        .values('hour')
        .annotate(total_bookings=Count('id'))
        .order_by('-total_bookings', 'hour')[:5]
    )

    payment_status_counts = Payment.objects.aggregate(
        total=Count('id'),
        cancelled=Count('id', filter=Q(status=Payment.STATUS_CANCELLED)),
        failed=Count('id', filter=Q(status=Payment.STATUS_FAILED)),
        expired=Count('id', filter=Q(status=Payment.STATUS_EXPIRED)),
    )
    total_payments = payment_status_counts['total'] or 0
    cancelled = payment_status_counts['cancelled'] or 0
    failed = payment_status_counts['failed'] or 0
    expired = payment_status_counts['expired'] or 0

    cancellation_rate = (cancelled / total_payments * 100.0) if total_payments else 0.0
    failure_rate = (failed / total_payments * 100.0) if total_payments else 0.0
    timeout_rate = (expired / total_payments * 100.0) if total_payments else 0.0

    return {
        'generated_at': now.isoformat(),
        'revenue': {
            'daily_inr': _money_inr(revenue['daily']),
            'weekly_inr': _money_inr(revenue['weekly']),
            'monthly_inr': _money_inr(revenue['monthly']),
        },
        'most_popular_movies': list(popular_movies),
        'busiest_theaters': list(busiest_theaters),
        'peak_booking_hours': list(peak_booking_hours),
        'cancellation': {
            'total_payments': total_payments,
            'cancelled_payments': cancelled,
            'failed_payments': failed,
            'expired_payments': expired,
            'cancellation_rate_percent': round(cancellation_rate, 2),
            'failure_rate_percent': round(failure_rate, 2),
            'timeout_rate_percent': round(timeout_rate, 2),
        },
    }


def get_admin_analytics_snapshot():
    snapshot = cache.get(ANALYTICS_CACHE_KEY)
    if snapshot is not None:
        return snapshot
    snapshot = build_admin_analytics_snapshot()
    cache.set(ANALYTICS_CACHE_KEY, snapshot, timeout=ANALYTICS_CACHE_TTL_SECONDS)
    return snapshot
