from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from movies.email_queue import process_single_email_task
from movies.models import Booking, Genre, Language, Movie, Payment, Seat, Theater
from movies.seat_locking import acquire_seat_locks, release_expired_seat_locks
from movies.views import _lock_and_finalize_payment


class SeatLockingTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        image = SimpleUploadedFile('poster.jpg', b'filecontent', content_type='image/jpeg')
        self.movie = Movie.objects.create(
            name='Concurrency Test Movie',
            image=image,
            rating='8.1',
            cast='Actor 1, Actor 2',
            description='Test movie',
        )
        self.theater = Theater.objects.create(
            name='Concurrency Theater',
            movie=self.movie,
            show_time=timezone.now() + timedelta(hours=1),
        )
        self.seat = Seat.objects.create(theater=self.theater, seat_number='A1')
        self.user_one = User.objects.create_user(username='u1', password='pass12345')
        self.user_two = User.objects.create_user(username='u2', password='pass12345')
        self.client = Client()

    def test_concurrent_lock_attempt_prevents_double_selection(self):
        ok1, _, _ = acquire_seat_locks(self.theater, [self.seat.id], self.user_one)
        ok2, msg2, _ = acquire_seat_locks(self.theater, [self.seat.id], self.user_two)

        self.assertTrue(ok1)
        self.assertFalse(ok2)
        self.assertIn('locked by another user', msg2)

    def test_expired_lock_is_released_by_cleanup(self):
        self.seat.locked_by = self.user_one
        self.seat.lock_expires_at = timezone.now() - timedelta(seconds=1)
        self.seat.save(update_fields=['locked_by', 'lock_expires_at'])

        released = release_expired_seat_locks()
        self.seat.refresh_from_db()

        self.assertEqual(released, 1)
        self.assertIsNone(self.seat.locked_by)
        self.assertIsNone(self.seat.lock_expires_at)

    def test_payment_finalization_requires_valid_user_lock(self):
        payment = Payment.objects.create(
            user=self.user_one,
            movie=self.movie,
            theater=self.theater,
            seat_ids=[self.seat.id],
            amount_paise=20000,
            razorpay_order_id='order_test_1',
        )

        ok, reason, updated_payment = _lock_and_finalize_payment(
            payment_id=payment.id,
            source=Payment.SOURCE_SYSTEM,
            provider_payment_id='pay_test_1',
            provider_order_id='order_test_1',
            gateway_status='captured',
            signature_verified=True,
            allow_expired=False,
        )

        self.assertFalse(ok)
        self.assertEqual(reason, 'seat_lock_expired_or_missing')
        self.assertEqual(updated_payment.status, Payment.STATUS_FAILED)

    def test_lock_status_endpoint_returns_pending_with_valid_lock(self):
        self.seat.locked_by = self.user_one
        self.seat.lock_expires_at = timezone.now() + timedelta(minutes=2)
        self.seat.save(update_fields=['locked_by', 'lock_expires_at'])

        payment = Payment.objects.create(
            user=self.user_one,
            movie=self.movie,
            theater=self.theater,
            seat_ids=[self.seat.id],
            amount_paise=20000,
            status=Payment.STATUS_PENDING,
            expires_at=timezone.now() + timedelta(minutes=2),
        )

        self.client.force_login(self.user_one)
        response = self.client.get(reverse('payment_lock_status'), {'payment_db_id': payment.id})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['payment_status'], Payment.STATUS_PENDING)
        self.assertEqual(payload['invalid_lock_seats'], [])

    def test_lock_status_endpoint_expires_payment_when_lock_missing(self):
        payment = Payment.objects.create(
            user=self.user_one,
            movie=self.movie,
            theater=self.theater,
            seat_ids=[self.seat.id],
            amount_paise=20000,
            status=Payment.STATUS_PENDING,
            expires_at=timezone.now() + timedelta(minutes=2),
        )

        self.client.force_login(self.user_one)
        response = self.client.get(reverse('payment_lock_status'), {'payment_db_id': payment.id})

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payment.status, Payment.STATUS_EXPIRED)
        self.assertEqual(payload['payment_status'], Payment.STATUS_EXPIRED)
        self.assertIn('A1', payload['invalid_lock_seats'])

    @override_settings(PAYMENT_MOCK_MODE=True)
    def test_mock_mode_verify_payment_books_seat(self):
        self.seat.locked_by = self.user_one
        self.seat.lock_expires_at = timezone.now() + timedelta(minutes=2)
        self.seat.save(update_fields=['locked_by', 'lock_expires_at'])

        payment = Payment.objects.create(
            user=self.user_one,
            movie=self.movie,
            theater=self.theater,
            seat_ids=[self.seat.id],
            amount_paise=20000,
            status=Payment.STATUS_PENDING,
            expires_at=timezone.now() + timedelta(minutes=2),
            razorpay_order_id='mock_order_1',
        )

        self.client.force_login(self.user_one)
        response = self.client.post(reverse('verify_payment'), {'payment_db_id': payment.id})

        self.assertEqual(response.status_code, 302)
        payment.refresh_from_db()
        self.seat.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_PAID)
        self.assertEqual(payment.gateway_status, 'mock_captured')
        self.assertTrue(self.seat.is_booked)
        self.assertEqual(Booking.objects.filter(seat=self.seat).count(), 1)


class AdminAnalyticsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        image = SimpleUploadedFile('poster.jpg', b'filecontent', content_type='image/jpeg')
        self.movie = Movie.objects.create(
            name='Analytics Movie',
            image=image,
            rating='8.2',
            cast='Actor 1, Actor 2',
            description='Analytics movie',
        )
        self.theater = Theater.objects.create(
            name='Analytics Theater',
            movie=self.movie,
            show_time=timezone.now() + timedelta(hours=2),
        )
        self.seat1 = Seat.objects.create(theater=self.theater, seat_number='A1', is_booked=True)
        self.seat2 = Seat.objects.create(theater=self.theater, seat_number='A2')
        self.staff_user = User.objects.create_user(
            username='staff_analytics',
            password='pass12345',
            is_staff=True,
        )
        self.normal_user = User.objects.create_user(username='normal_analytics', password='pass12345')

    def test_admin_analytics_dashboard_forbidden_for_non_admin_user(self):
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('admin_analytics_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_admin_analytics_api_returns_aggregated_metrics_for_staff(self):
        booking = Booking.objects.create(
            user=self.staff_user,
            seat=self.seat1,
            movie=self.movie,
            theater=self.theater,
        )
        Booking.objects.filter(id=booking.id).update(booked_at=timezone.now() - timedelta(hours=1))

        paid_payment = Payment.objects.create(
            user=self.staff_user,
            movie=self.movie,
            theater=self.theater,
            seat_ids=[self.seat1.id],
            amount_paise=50000,
            status=Payment.STATUS_PAID,
        )
        Payment.objects.filter(id=paid_payment.id).update(created_at=timezone.now() - timedelta(hours=1))

        Payment.objects.create(
            user=self.staff_user,
            movie=self.movie,
            theater=self.theater,
            seat_ids=[self.seat2.id],
            amount_paise=25000,
            status=Payment.STATUS_CANCELLED,
        )

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('admin_analytics_api'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn('revenue', payload)
        self.assertIn('most_popular_movies', payload)
        self.assertIn('busiest_theaters', payload)
        self.assertIn('peak_booking_hours', payload)
        self.assertIn('cancellation', payload)
        self.assertGreaterEqual(payload['revenue']['daily_inr'], 500.0)
        self.assertEqual(payload['most_popular_movies'][0]['movie__name'], self.movie.name)
        self.assertGreaterEqual(payload['cancellation']['cancellation_rate_percent'], 50.0)

    def test_admin_analytics_cache_invalidation_after_payment_update(self):
        payment = Payment.objects.create(
            user=self.staff_user,
            movie=self.movie,
            theater=self.theater,
            seat_ids=[self.seat2.id],
            amount_paise=25000,
            status=Payment.STATUS_PENDING,
        )

        self.client.force_login(self.staff_user)
        first = self.client.get(reverse('admin_analytics_api')).json()
        self.assertEqual(first['cancellation']['cancelled_payments'], 0)

        payment.status = Payment.STATUS_CANCELLED
        payment.save(update_fields=['status', 'updated_at'])

        second = self.client.get(reverse('admin_analytics_api')).json()
        self.assertEqual(second['cancellation']['cancelled_payments'], 1)


class MovieFilteringTests(TestCase):
    def _create_movie(self, name, rating='8.0'):
        image = SimpleUploadedFile(f'{name}.jpg', b'filecontent', content_type='image/jpeg')
        return Movie.objects.create(
            name=name,
            image=image,
            rating=rating,
            cast='Actor 1, Actor 2',
            description='Filter test movie',
        )

    def test_multi_select_filter_by_genre_and_language(self):
        action = Genre.objects.create(name='Action', slug='action')
        drama = Genre.objects.create(name='Drama', slug='drama')
        comedy = Genre.objects.create(name='Comedy', slug='comedy')
        hindi = Language.objects.create(name='Hindi', code='hi')
        english = Language.objects.create(name='English', code='en')

        m1 = self._create_movie('Action Hindi', '8.2')
        m1.genres.add(action)
        m1.languages.add(hindi)

        m2 = self._create_movie('Drama Hindi', '7.5')
        m2.genres.add(drama)
        m2.languages.add(hindi)

        m3 = self._create_movie('Comedy English', '9.0')
        m3.genres.add(comedy)
        m3.languages.add(english)

        response = self.client.get(
            reverse('movie_list'),
            {
                'genres': [action.id, drama.id],
                'languages': [hindi.id],
            },
        )

        self.assertEqual(response.status_code, 200)
        movies = list(response.context['movies'])
        movie_names = {m.name for m in movies}
        self.assertSetEqual(movie_names, {'Action Hindi', 'Drama Hindi'})

    def test_dynamic_filter_counts_respect_other_active_filters(self):
        action = Genre.objects.create(name='Action', slug='action')
        drama = Genre.objects.create(name='Drama', slug='drama')
        hindi = Language.objects.create(name='Hindi', code='hi')
        english = Language.objects.create(name='English', code='en')

        m1 = self._create_movie('Movie 1')
        m1.genres.add(action)
        m1.languages.add(hindi)

        m2 = self._create_movie('Movie 2')
        m2.genres.add(drama)
        m2.languages.add(hindi)

        m3 = self._create_movie('Movie 3')
        m3.genres.add(action)
        m3.languages.add(english)

        response = self.client.get(reverse('movie_list'), {'languages': [hindi.id]})
        self.assertEqual(response.status_code, 200)

        genre_counts = {g.name: g.movie_count for g in response.context['genres']}
        self.assertEqual(genre_counts['Action'], 1)
        self.assertEqual(genre_counts['Drama'], 1)

    def test_sorting_and_pagination_with_filters(self):
        action = Genre.objects.create(name='Action', slug='action')
        hindi = Language.objects.create(name='Hindi', code='hi')

        for i in range(12):
            movie = self._create_movie(f'Movie {i}', rating=f'{(i % 9) + 1}.0')
            movie.genres.add(action)
            movie.languages.add(hindi)

        response = self.client.get(
            reverse('movie_list'),
            {
                'genres': [action.id],
                'languages': [hindi.id],
                'sort': 'rating_desc',
                'page': 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.number, 2)
        self.assertTrue(page_obj.has_previous())
        self.assertGreater(page_obj.paginator.count, 9)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='no-reply@test.local',
)
class BookingEmailQueueTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        image = SimpleUploadedFile('poster.jpg', b'filecontent', content_type='image/jpeg')
        self.movie = Movie.objects.create(
            name='Email Queue Movie',
            image=image,
            rating='8.1',
            cast='Actor 1, Actor 2',
            description='Email queue test movie',
        )
        self.theater = Theater.objects.create(
            name='Email Queue Theater',
            movie=self.movie,
            show_time=timezone.now() + timedelta(hours=1),
        )
        self.seat = Seat.objects.create(theater=self.theater, seat_number='A1')
        self.user = User.objects.create_user(
            username='email_user',
            email='email_user@test.local',
            password='pass12345',
        )

    def test_payment_success_enqueues_email_task(self):
        self.seat.locked_by = self.user
        self.seat.lock_expires_at = timezone.now() + timedelta(minutes=2)
        self.seat.save(update_fields=['locked_by', 'lock_expires_at'])

        payment = Payment.objects.create(
            user=self.user,
            movie=self.movie,
            theater=self.theater,
            seat_ids=[self.seat.id],
            amount_paise=20000,
            razorpay_order_id='order_email_1',
        )

        ok, _, payment = _lock_and_finalize_payment(
            payment_id=payment.id,
            source=Payment.SOURCE_SYSTEM,
            provider_payment_id='pay_email_1',
            provider_order_id='order_email_1',
            gateway_status='captured',
            signature_verified=True,
            allow_expired=False,
        )
        self.assertTrue(ok)
        payment.refresh_from_db()
        self.assertEqual(payment.email_task.status, 'sent')
        self.assertEqual(payment.email_task.recipient_email, self.user.email)
        self.assertEqual(len(mail.outbox), 1)

    def test_email_task_retry_and_success(self):
        from movies.email_queue import enqueue_booking_confirmation_email

        payment = Payment.objects.create(
            user=self.user,
            movie=self.movie,
            theater=self.theater,
            seat_ids=[self.seat.id],
            amount_paise=20000,
            status=Payment.STATUS_PAID,
            razorpay_order_id='order_email_2',
            razorpay_payment_id='pay_email_2',
        )
        task = enqueue_booking_confirmation_email(payment, ['A1'])

        with patch('movies.email_queue.EmailMultiAlternatives.send', side_effect=Exception('SMTP down')):
            sent = process_single_email_task(task)
            self.assertFalse(sent)
            task.refresh_from_db()
            self.assertIn(task.status, ['pending', 'failed'])
            self.assertEqual(task.attempt_count, 1)
            self.assertTrue(task.last_error)

        task.next_attempt_at = timezone.now() - timedelta(seconds=1)
        task.save(update_fields=['next_attempt_at', 'updated_at'])
        sent = process_single_email_task(task)
        self.assertTrue(sent)
        task.refresh_from_db()
        self.assertEqual(task.status, 'sent')
        self.assertEqual(len(mail.outbox), 1)
