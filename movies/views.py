import hashlib
import hmac
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .analytics import get_admin_analytics_snapshot
from .authz import admin_analytics_api_required, admin_analytics_required
from .email_queue import send_booking_confirmation_email
from .models import Booking, Genre, Language, Movie, Payment, PaymentWebhookEvent, Seat, Theater
from .seat_locking import acquire_seat_locks, release_expired_seat_locks, release_seat_locks_for_user, seats_with_invalid_lock_for_user
from .trailer_security import build_watch_url, extract_youtube_video_id


def _parse_multi_select_ints(raw_values):
    ids = set()
    for raw in raw_values:
        for part in str(raw).split(','):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
    return sorted(ids)


def _apply_movie_filters(queryset, search_query='', genre_ids=None, language_ids=None):
    genre_ids = genre_ids or []
    language_ids = language_ids or []

    if search_query:
        queryset = queryset.filter(name__icontains=search_query)
    if genre_ids:
        queryset = queryset.filter(genres__id__in=genre_ids)
    if language_ids:
        queryset = queryset.filter(languages__id__in=language_ids)
    return queryset


def movie_list(request):
    search_query = (request.GET.get('search') or '').strip()
    selected_genre_ids = _parse_multi_select_ints(request.GET.getlist('genres'))
    selected_language_ids = _parse_multi_select_ints(request.GET.getlist('languages'))
    sort_key = (request.GET.get('sort') or 'name_asc').strip()

    sort_map = {
        'name_asc': 'name',
        'name_desc': '-name',
        'rating_desc': '-rating',
        'rating_asc': 'rating',
        'newest': '-id',
    }
    order_by_field = sort_map.get(sort_key, 'name')

    base_movies = Movie.objects.all()
    filtered_movies = _apply_movie_filters(
        queryset=base_movies,
        search_query=search_query,
        genre_ids=selected_genre_ids,
        language_ids=selected_language_ids,
    ).distinct()

    movie_qs = filtered_movies.order_by(order_by_field, 'id').prefetch_related('genres', 'languages')
    paginator = Paginator(movie_qs, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Dynamic facet counts: keep all active filters except the facet being counted.
    genre_scope = _apply_movie_filters(
        queryset=base_movies,
        search_query=search_query,
        genre_ids=[],
        language_ids=selected_language_ids,
    )
    language_scope = _apply_movie_filters(
        queryset=base_movies,
        search_query=search_query,
        genre_ids=selected_genre_ids,
        language_ids=[],
    )

    genres = (
        Genre.objects.annotate(
            movie_count=Count(
                'movies',
                filter=Q(movies__id__in=genre_scope.values('id')),
                distinct=True,
            )
        )
        .filter(movie_count__gt=0)
        .order_by('name')
    )

    languages = (
        Language.objects.annotate(
            movie_count=Count(
                'movies',
                filter=Q(movies__id__in=language_scope.values('id')),
                distinct=True,
            )
        )
        .filter(movie_count__gt=0)
        .order_by('name')
    )

    query_without_page = request.GET.copy()
    query_without_page.pop('page', None)

    context = {
        'movies': page_obj.object_list,
        'page_obj': page_obj,
        'search_query': search_query,
        'sort_key': sort_key,
        'genres': genres,
        'languages': languages,
        'selected_genre_ids': selected_genre_ids,
        'selected_language_ids': selected_language_ids,
        'total_results': paginator.count,
        'query_without_page': query_without_page.urlencode(),
    }
    return render(request, 'movies/movie_list.html', context)


def theater_list(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    theaters = Theater.objects.filter(movie=movie)
    trailer_video_id = extract_youtube_video_id(movie.trailer_url or '')
    trailer_watch_url = build_watch_url(trailer_video_id) if trailer_video_id else ''
    return render(
        request,
        'movies/theater_list.html',
        {
            'movie': movie,
            'theaters': theaters,
            'trailer_video_id': trailer_video_id,
            'trailer_watch_url': trailer_watch_url,
        },
    )



def open_trailer(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    trailer_video_id = extract_youtube_video_id(movie.trailer_url or '')
    if not trailer_video_id:
        messages.error(request, 'Trailer unavailable for this movie.')
        return redirect('theater_list', movie_id=movie.id)
    return redirect(build_watch_url(trailer_video_id))
def _expire_stale_pending_payments(user=None):
    now = timezone.now()
    stale = Payment.objects.filter(status=Payment.STATUS_PENDING, expires_at__lt=now)
    if user is not None:
        stale = stale.filter(user=user)

    stale.update(
        status=Payment.STATUS_EXPIRED,
        verification_source=Payment.SOURCE_SYSTEM,
        gateway_status='timeout',
        failure_reason='Payment timed out before completion.',
    )
    release_expired_seat_locks(now=now)


def _lock_and_finalize_payment(
    payment_id,
    source,
    provider_payment_id,
    provider_order_id,
    gateway_status,
    signature_verified,
    allow_expired=False,
):
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment_id)

        if payment.status == Payment.STATUS_PAID:
            return True, 'already_paid', payment

        if payment.status in {Payment.STATUS_FAILED, Payment.STATUS_CANCELLED}:
            return False, 'non_retriable_state', payment

        if payment.status == Payment.STATUS_EXPIRED and not allow_expired:
            return False, 'payment_expired', payment

        if provider_order_id and payment.razorpay_order_id and provider_order_id != payment.razorpay_order_id:
            payment.status = Payment.STATUS_FAILED
            payment.gateway_status = 'order_mismatch'
            payment.failure_reason = 'Order mismatch during verification.'
            payment.verification_source = source
            payment.provider_signature_verified = signature_verified
            payment.save(update_fields=[
                'status', 'gateway_status', 'failure_reason', 'verification_source',
                'provider_signature_verified', 'updated_at',
            ])
            return False, 'order_mismatch', payment

        seats = list(Seat.objects.select_for_update().filter(id__in=payment.seat_ids, theater=payment.theater))
        if len(seats) != len(payment.seat_ids):
            payment.status = Payment.STATUS_FAILED
            payment.gateway_status = 'invalid_seat_selection'
            payment.failure_reason = 'One or more seats are invalid.'
            payment.verification_source = source
            payment.provider_signature_verified = signature_verified
            payment.save(update_fields=[
                'status', 'gateway_status', 'failure_reason', 'verification_source',
                'provider_signature_verified', 'updated_at',
            ])
            return False, 'invalid_seats', payment

        already_booked = [seat.seat_number for seat in seats if seat.is_booked]
        if already_booked:
            payment.status = Payment.STATUS_FAILED
            payment.gateway_status = 'already_booked'
            payment.failure_reason = f"Seats already booked: {', '.join(already_booked)}"
            payment.verification_source = source
            payment.provider_signature_verified = signature_verified
            payment.save(update_fields=[
                'status', 'gateway_status', 'failure_reason', 'verification_source',
                'provider_signature_verified', 'updated_at',
            ])
            return False, 'already_booked', payment

        invalid_lock_seats = seats_with_invalid_lock_for_user(seats, payment.user)
        if invalid_lock_seats:
            payment.status = Payment.STATUS_FAILED
            payment.gateway_status = 'seat_lock_expired_or_missing'
            payment.failure_reason = f"Seat lock expired or missing for: {', '.join(invalid_lock_seats)}"
            payment.verification_source = source
            payment.provider_signature_verified = signature_verified
            payment.save(update_fields=[
                'status', 'gateway_status', 'failure_reason', 'verification_source',
                'provider_signature_verified', 'updated_at',
            ])
            return False, 'seat_lock_expired_or_missing', payment

        for seat in seats:
            try:
                Booking.objects.create(user=payment.user, seat=seat, movie=payment.movie, theater=payment.theater)
                seat.is_booked = True
                seat.locked_by = None
                seat.lock_expires_at = None
                seat.save(update_fields=['is_booked', 'locked_by', 'lock_expires_at'])
            except IntegrityError:
                payment.status = Payment.STATUS_FAILED
                payment.gateway_status = 'booking_integrity_error'
                payment.failure_reason = f'Seat {seat.seat_number} could not be booked.'
                payment.verification_source = source
                payment.provider_signature_verified = signature_verified
                payment.save(update_fields=[
                    'status', 'gateway_status', 'failure_reason', 'verification_source',
                    'provider_signature_verified', 'updated_at',
                ])
                return False, 'booking_integrity_error', payment

        payment.status = Payment.STATUS_PAID
        payment.gateway_status = gateway_status or 'captured'
        payment.failure_reason = ''
        payment.verification_source = source
        payment.provider_signature_verified = signature_verified
        payment.razorpay_payment_id = provider_payment_id or payment.razorpay_payment_id
        payment.razorpay_order_id = provider_order_id or payment.razorpay_order_id
        payment.save(update_fields=[
            'status', 'gateway_status', 'failure_reason', 'verification_source', 'provider_signature_verified',
            'razorpay_payment_id', 'razorpay_order_id', 'updated_at',
        ])

        seat_numbers = [seat.seat_number for seat in seats]
        transaction.on_commit(lambda: send_booking_confirmation_email(payment, seat_numbers))

        return True, 'paid', payment


@login_required(login_url='/login/')
def book_seats(request, theater_id):
    theater = get_object_or_404(Theater, id=theater_id)
    seats = Seat.objects.filter(theater=theater)
    now = timezone.now()

    if request.method == 'POST':
        release_expired_seat_locks()
        selected_seat_ids = [int(seat_id) for seat_id in request.POST.getlist('seats') if seat_id.isdigit()]
        if not selected_seat_ids:
            return render(
                request,
                'movies/seat_selection.html',
                {'theaters': theater, 'seats': seats, 'error': 'No seat selected', 'now': now},
            )

        ok, error, lock_expires_at = acquire_seat_locks(
            theater=theater,
            seat_ids=selected_seat_ids,
            user=request.user,
        )
        if not ok:
            return render(
                request,
                'movies/seat_selection.html',
                {
                    'theaters': theater,
                    'seats': seats,
                    'error': error,
                    'now': now,
                },
            )

        request.session['pending_booking'] = {
            'theater_id': theater.id,
            'seat_ids': sorted({int(seat_id) for seat_id in selected_seat_ids}),
            'lock_expires_at': lock_expires_at.isoformat(),
        }
        return redirect('payment_checkout')

    return render(request, 'movies/seat_selection.html', {'theaters': theater, 'seats': seats, 'now': now})


@login_required(login_url='/login/')
def payment_checkout(request):
    _expire_stale_pending_payments(user=request.user)
    release_expired_seat_locks()

    pending = request.session.get('pending_booking')
    if not pending:
        return redirect('movie_list')

    theater = get_object_or_404(Theater, id=pending['theater_id'])
    seat_ids = sorted([int(x) for x in pending.get('seat_ids', [])])
    selected_seats = list(Seat.objects.filter(id__in=seat_ids, theater=theater))
    if not selected_seats or len(selected_seats) != len(seat_ids):
        return redirect('book_seats', theater_id=theater.id)

    already_booked = [seat.seat_number for seat in selected_seats if seat.is_booked]
    if already_booked:
        messages.error(request, f"Seats already booked: {', '.join(already_booked)}")
        return redirect('book_seats', theater_id=theater.id)

    invalid_lock_seats = seats_with_invalid_lock_for_user(selected_seats, request.user)
    if invalid_lock_seats:
        messages.error(request, f"Seat lock expired for: {', '.join(invalid_lock_seats)}. Please reselect seats.")
        return redirect('book_seats', theater_id=theater.id)

    seat_numbers = [seat.seat_number for seat in selected_seats]
    amount_paise = len(selected_seats) * settings.SEAT_PRICE_INR * 100
    payment_mock_mode = getattr(settings, 'PAYMENT_MOCK_MODE', False)

    if not payment_mock_mode and (not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET):
        return render(
            request,
            'movies/payment_checkout.html',
            {
                'gateway_error': 'Razorpay keys are missing. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in environment.',
                'theater': theater,
                'seat_numbers': seat_numbers,
                'amount_inr': amount_paise / 100,
            },
        )

    reusable_payment = (
        Payment.objects.filter(
            user=request.user,
            movie=theater.movie,
            theater=theater,
            seat_ids=seat_ids,
            amount_paise=amount_paise,
            status=Payment.STATUS_PENDING,
            expires_at__gt=timezone.now(),
        )
        .order_by('-created_at')
        .first()
    )

    if payment_mock_mode:
        payment = reusable_payment or Payment.objects.create(
            user=request.user,
            movie=theater.movie,
            theater=theater,
            seat_ids=seat_ids,
            amount_paise=amount_paise,
            metadata={'seat_numbers': seat_numbers, 'mock_mode': True},
        )
        if not payment.razorpay_order_id:
            payment.razorpay_order_id = f'mock_order_{payment.id}'
        payment.gateway_status = 'mock_order_created'
        earliest_lock_expiry = min([seat.lock_expires_at for seat in selected_seats if seat.lock_expires_at])
        payment.expires_at = earliest_lock_expiry
        payment.save(update_fields=['razorpay_order_id', 'gateway_status', 'expires_at', 'updated_at'])
        order_id = payment.razorpay_order_id
    elif reusable_payment and reusable_payment.razorpay_order_id:
        payment = reusable_payment
        earliest_lock_expiry = min([seat.lock_expires_at for seat in selected_seats if seat.lock_expires_at])
        payment.expires_at = earliest_lock_expiry
        payment.save(update_fields=['expires_at', 'updated_at'])
        order_id = payment.razorpay_order_id
    else:
        import razorpay

        payment = reusable_payment or Payment.objects.create(
            user=request.user,
            movie=theater.movie,
            theater=theater,
            seat_ids=seat_ids,
            amount_paise=amount_paise,
            metadata={'seat_numbers': seat_numbers},
        )

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        order_data = {
            'amount': amount_paise,
            'currency': 'INR',
            'payment_capture': 1,
            'receipt': payment.idempotency_key,
            'notes': {
                'payment_db_id': str(payment.id),
                'idempotency_key': payment.idempotency_key,
                'user_id': str(request.user.id),
            },
        }
        try:
            order = client.order.create(order_data)
        except Exception as exc:
            payment.status = Payment.STATUS_FAILED
            payment.gateway_status = 'order_create_failed'
            payment.failure_reason = 'Razorpay order creation/authentication failed.'
            payment.verification_source = Payment.SOURCE_SYSTEM
            payment.save(update_fields=['status', 'gateway_status', 'failure_reason', 'verification_source', 'updated_at'])
            return render(
                request,
                'movies/payment_checkout.html',
                {
                    'gateway_error': f'Razorpay authentication failed: {str(exc)}' if settings.DEBUG else 'Razorpay authentication failed. Please set valid TEST key id/secret.',
                    'theater': theater,
                    'seat_numbers': seat_numbers,
                    'amount_inr': amount_paise / 100,
                },
            )

        order_id = order['id']
        payment.razorpay_order_id = order_id
        payment.gateway_status = 'order_created'
        earliest_lock_expiry = min([seat.lock_expires_at for seat in selected_seats if seat.lock_expires_at])
        payment.expires_at = earliest_lock_expiry
        payment.save(update_fields=['razorpay_order_id', 'gateway_status', 'expires_at', 'updated_at'])

    return render(
        request,
        'movies/payment_checkout.html',
        {
            'theater': theater,
            'seat_numbers': seat_numbers,
            'amount_inr': amount_paise / 100,
            'amount_paise': amount_paise,
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'razorpay_order_id': order_id,
            'payment_db_id': payment.id,
            'payment_idempotency_key': payment.idempotency_key,
            'payment_expires_at': payment.expires_at,
            'payment_mock_mode': payment_mock_mode,
        },
    )


@login_required(login_url='/login/')
def verify_payment(request):
    _expire_stale_pending_payments(user=request.user)
    release_expired_seat_locks()

    if request.method != 'POST':
        messages.error(request, 'Invalid payment request.')
        return redirect('movie_list')

    payment_db_id = request.POST.get('payment_db_id')
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_order_id = request.POST.get('razorpay_order_id')
    razorpay_signature = request.POST.get('razorpay_signature')

    payment = get_object_or_404(Payment, id=payment_db_id, user=request.user)

    if payment.status == Payment.STATUS_PAID:
        messages.success(request, 'Payment already verified. Seats already booked.')
        request.session.pop('pending_booking', None)
        return redirect('profile')

    if payment.status in {Payment.STATUS_CANCELLED, Payment.STATUS_FAILED, Payment.STATUS_EXPIRED}:
        messages.error(request, f'Payment cannot be verified in current state: {payment.status}.')
        return redirect('payment_checkout')

    if getattr(settings, 'PAYMENT_MOCK_MODE', False):
        mock_payment_id = razorpay_payment_id or f'mock_payment_{payment.id}'
        mock_order_id = razorpay_order_id or payment.razorpay_order_id or f'mock_order_{payment.id}'
        ok, reason, _ = _lock_and_finalize_payment(
            payment_id=payment.id,
            source=Payment.SOURCE_SYSTEM,
            provider_payment_id=mock_payment_id,
            provider_order_id=mock_order_id,
            gateway_status='mock_captured',
            signature_verified=True,
            allow_expired=False,
        )
        if ok:
            request.session.pop('pending_booking', None)
            messages.success(request, 'Mock payment successful and seats booked.')
            return redirect('profile')
        messages.error(request, f'Payment could not be finalized: {reason}.')
        return redirect('payment_checkout')

    if not razorpay_payment_id or not razorpay_order_id or not razorpay_signature:
        payment.status = Payment.STATUS_FAILED
        payment.gateway_status = 'missing_callback_fields'
        payment.failure_reason = 'Missing payment callback fields.'
        payment.verification_source = Payment.SOURCE_CALLBACK
        payment.save(update_fields=['status', 'gateway_status', 'failure_reason', 'verification_source', 'updated_at'])
        messages.error(request, 'Payment verification failed due to missing callback fields.')
        return redirect('payment_checkout')

    try:
        import razorpay

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        client.utility.verify_payment_signature(
            {
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_order_id': razorpay_order_id,
                'razorpay_signature': razorpay_signature,
            }
        )
    except Exception:
        payment.status = Payment.STATUS_FAILED
        payment.gateway_status = 'signature_verification_failed'
        payment.failure_reason = 'Razorpay callback signature verification failed.'
        payment.verification_source = Payment.SOURCE_CALLBACK
        payment.provider_signature_verified = False
        payment.save(update_fields=[
            'status', 'gateway_status', 'failure_reason', 'verification_source',
            'provider_signature_verified', 'updated_at',
        ])
        messages.error(request, 'Payment signature verification failed.')
        return redirect('payment_checkout')

    ok, reason, _ = _lock_and_finalize_payment(
        payment_id=payment.id,
        source=Payment.SOURCE_CALLBACK,
        provider_payment_id=razorpay_payment_id,
        provider_order_id=razorpay_order_id,
        gateway_status='captured',
        signature_verified=True,
        allow_expired=False,
    )

    if ok:
        request.session.pop('pending_booking', None)
        messages.success(request, 'Payment successful and seats booked.')
        return redirect('profile')

    messages.error(request, f'Payment could not be finalized: {reason}.')
    return redirect('payment_checkout')


@login_required(login_url='/login/')
def cancel_payment(request):
    if request.method != 'POST':
        return redirect('payment_checkout')

    payment_db_id = request.POST.get('payment_db_id')
    reason = request.POST.get('cancel_reason', 'User closed payment modal')

    payment = get_object_or_404(Payment, id=payment_db_id, user=request.user)
    if payment.status == Payment.STATUS_PENDING:
        payment.status = Payment.STATUS_CANCELLED
        payment.gateway_status = 'cancelled_by_user'
        payment.failure_reason = reason[:500]
        payment.verification_source = Payment.SOURCE_CALLBACK
        payment.save(update_fields=['status', 'gateway_status', 'failure_reason', 'verification_source', 'updated_at'])
        release_seat_locks_for_user(request.user, payment.seat_ids)

    messages.info(request, 'Payment was cancelled. You can retry checkout.')
    return redirect('payment_checkout')


@login_required(login_url='/login/')
def payment_lock_status(request):
    _expire_stale_pending_payments(user=request.user)
    release_expired_seat_locks()

    payment_db_id = request.GET.get('payment_db_id')
    if not payment_db_id or not payment_db_id.isdigit():
        return JsonResponse({'ok': False, 'error': 'invalid_payment_id'}, status=400)

    payment = get_object_or_404(Payment, id=int(payment_db_id), user=request.user)

    seats = list(Seat.objects.filter(id__in=payment.seat_ids, theater=payment.theater))
    now = timezone.now()
    invalid_lock_seats = seats_with_invalid_lock_for_user(seats, request.user, now=now)

    if payment.status == Payment.STATUS_PENDING and invalid_lock_seats:
        payment.status = Payment.STATUS_EXPIRED
        payment.gateway_status = 'seat_lock_expired'
        payment.failure_reason = f"Seat lock expired or missing for: {', '.join(invalid_lock_seats)}"
        payment.verification_source = Payment.SOURCE_SYSTEM
        payment.save(update_fields=['status', 'gateway_status', 'failure_reason', 'verification_source', 'updated_at'])

    return JsonResponse(
        {
            'ok': True,
            'payment_status': payment.status,
            'expires_at': payment.expires_at.isoformat() if payment.expires_at else None,
            'server_time': now.isoformat(),
            'invalid_lock_seats': invalid_lock_seats,
        }
    )


@admin_analytics_required
def admin_analytics_dashboard(request):
    return render(request, 'movies/admin_analytics_dashboard.html')


@admin_analytics_api_required
def admin_analytics_api(request):
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    snapshot = get_admin_analytics_snapshot()
    return JsonResponse(snapshot, status=200)


@csrf_exempt
def razorpay_webhook(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Only POST is allowed')

    webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
    if not webhook_secret:
        return HttpResponse('Webhook secret not configured', status=503)

    signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
    if not signature:
        return HttpResponseBadRequest('Missing webhook signature')

    body = request.body
    expected_signature = hmac.new(webhook_secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        return HttpResponseBadRequest('Invalid webhook signature')

    try:
        payload = json.loads(body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest('Invalid JSON payload')

    event_type = payload.get('event', 'unknown')
    payload_hash = hashlib.sha256(body).hexdigest()
    provider_event_id = request.META.get('HTTP_X_RAZORPAY_EVENT_ID') or payload_hash

    existing_event = PaymentWebhookEvent.objects.filter(provider_event_id=provider_event_id).first()
    if existing_event:
        return JsonResponse({'status': 'duplicate_ignored'})

    payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
    order_entity = payload.get('payload', {}).get('order', {}).get('entity', {})

    provider_order_id = payment_entity.get('order_id') or order_entity.get('id') or ''
    provider_payment_id = payment_entity.get('id') or ''
    gateway_status = payment_entity.get('status') or event_type
    failure_reason = payment_entity.get('error_description') or ''

    payment = None
    if provider_order_id:
        payment = Payment.objects.filter(razorpay_order_id=provider_order_id).order_by('-id').first()
    if not payment and provider_payment_id:
        payment = Payment.objects.filter(razorpay_payment_id=provider_payment_id).order_by('-id').first()

    PaymentWebhookEvent.objects.create(
        provider_event_id=provider_event_id,
        event_type=event_type,
        signature_verified=True,
        payload_hash=payload_hash,
        payment=payment,
    )

    if not payment:
        return JsonResponse({'status': 'ok', 'message': 'payment_not_found'})

    payment.webhook_event_count += 1
    payment.save(update_fields=['webhook_event_count', 'updated_at'])

    if event_type in {'payment.captured', 'order.paid'}:
        _lock_and_finalize_payment(
            payment_id=payment.id,
            source=Payment.SOURCE_WEBHOOK,
            provider_payment_id=provider_payment_id,
            provider_order_id=provider_order_id,
            gateway_status=gateway_status,
            signature_verified=True,
            allow_expired=True,
        )
    elif event_type == 'payment.failed':
        if payment.status != Payment.STATUS_PAID:
            payment.status = Payment.STATUS_FAILED
            payment.gateway_status = gateway_status
            payment.failure_reason = failure_reason or 'Payment failed as per gateway webhook.'
            payment.verification_source = Payment.SOURCE_WEBHOOK
            payment.provider_signature_verified = True
            payment.save(update_fields=[
                'status', 'gateway_status', 'failure_reason', 'verification_source',
                'provider_signature_verified', 'updated_at',
            ])
    else:
        payment.gateway_status = gateway_status
        payment.verification_source = Payment.SOURCE_WEBHOOK
        payment.provider_signature_verified = True
        payment.save(update_fields=['gateway_status', 'verification_source', 'provider_signature_verified', 'updated_at'])

    return JsonResponse({'status': 'ok'})


