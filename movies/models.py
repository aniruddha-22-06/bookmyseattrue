from datetime import timedelta
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .trailer_security import validate_youtube_trailer_url


def default_idempotency_key():
    return uuid.uuid4().hex


def default_payment_expiry():
    return timezone.now() + timedelta(minutes=2)


class Movie(models.Model):
    POSTER_URLS = {
        'avengers': 'https://upload.wikimedia.org/wikipedia/en/8/8a/The_Avengers_%282012_film%29_poster.jpg',
        'avengers: endgame': 'https://upload.wikimedia.org/wikipedia/en/0/0d/Avengers_Endgame_poster.jpg',
        'inception': 'https://upload.wikimedia.org/wikipedia/en/2/2e/Inception_%282010%29_theatrical_poster.jpg',
        'interstellar': 'https://upload.wikimedia.org/wikipedia/en/b/bc/Interstellar_film_poster.jpg',
        'joker': 'https://upload.wikimedia.org/wikipedia/en/e/e1/Joker_%282019_film%29_poster.jpg',
        'spider-man': 'https://upload.wikimedia.org/wikipedia/en/0/00/Spider-Man_No_Way_Home_poster.jpg',
        'pushpa 2: the rule': 'https://upload.wikimedia.org/wikipedia/en/1/11/Pushpa_2-_The_Rule.jpg',
        'devara part 1': 'https://upload.wikimedia.org/wikipedia/en/f/f0/Devara_Part_1.jpg',
        'kalki 2898 ad': 'https://upload.wikimedia.org/wikipedia/en/4/4c/Kalki_2898_AD.jpg',
        'stree 2': 'https://upload.wikimedia.org/wikipedia/en/a/a1/Stree_2.jpg',
        'fighter': 'https://upload.wikimedia.org/wikipedia/en/d/df/Fighter_film_teaser.jpg',
        'oppenheimer': 'https://upload.wikimedia.org/wikipedia/en/4/4a/Oppenheimer_%28film%29.jpg',
        'dune': 'https://upload.wikimedia.org/wikipedia/en/a/a6/Dune_%282021_film%29.jpg',
        'the dark knight': 'https://upload.wikimedia.org/wikipedia/en/8/8a/Dark_Knight.jpg',
        'titanic': 'https://upload.wikimedia.org/wikipedia/en/2/22/Titanic_poster.jpg',
        'avatar': 'https://upload.wikimedia.org/wikipedia/en/b/b0/Avatar-Teaser-Poster.jpg',
        'bahubali: the beginning': 'https://upload.wikimedia.org/wikipedia/en/7/7e/Baahubali_The_Beginning_poster.jpg',
        'bahubali 2: the conclusion': 'https://upload.wikimedia.org/wikipedia/en/f/f9/Baahubali_the_Conclusion.jpg',
        'rrr': 'https://upload.wikimedia.org/wikipedia/en/d/d7/RRR_Poster.jpg',
        'kgf: chapter 1': 'https://upload.wikimedia.org/wikipedia/en/c/ca/K.G.F_Chapter_1_poster.jpg',
        'kgf: chapter 2': 'https://upload.wikimedia.org/wikipedia/en/5/5f/KGF_Chapter_2_poster.jpg',
    }

    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to='movies/')
    rating = models.DecimalField(max_digits=3, decimal_places=1)
    cast = models.TextField()
    description = models.TextField(blank=True, null=True)
    trailer_url = models.URLField(blank=True, null=True, validators=[validate_youtube_trailer_url])
    metadata = models.JSONField(default=dict, blank=True)
    genres = models.ManyToManyField('Genre', related_name='movies', blank=True)
    languages = models.ManyToManyField('Language', related_name='movies', blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['name'], name='movie_name_idx'),
            models.Index(fields=['rating'], name='movie_rating_idx'),
        ]

    def __str__(self):
        return self.name

    @property
    def poster_url(self):
        metadata_url = (self.metadata or {}).get('poster_url')
        if metadata_url:
            return metadata_url
        mapped_url = self.POSTER_URLS.get(self.name.strip().lower())
        if mapped_url:
            return mapped_url
        if self.image:
            return self.image.url
        return '/media/movies/download.jpeg'


class Theater(models.Model):
    name = models.CharField(max_length=255)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='theaters')
    show_time = models.DateTimeField()

    def __str__(self):
        return f'{self.name} - {self.movie.name} at {self.show_time}'


class Seat(models.Model):
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name='seats')
    seat_number = models.CharField(max_length=10)
    is_booked = models.BooleanField(default=False)
    locked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='seat_locks')
    lock_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        unique_together = ('theater', 'seat_number')

    def __str__(self):
        return f'{self.seat_number} in {self.theater.name}'


class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    seat = models.OneToOneField(Seat, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE)
    booked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['booked_at'], name='booking_booked_at_idx'),
            models.Index(fields=['movie', 'booked_at'], name='booking_movie_time_idx'),
            models.Index(fields=['theater', 'booked_at'], name='booking_theater_time_idx'),
        ]

    def __str__(self):
        return f'Booking by {self.user.username} for {self.seat.seat_number} at {self.theater.name}'


class Payment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    SOURCE_CALLBACK = 'callback'
    SOURCE_WEBHOOK = 'webhook'
    SOURCE_SYSTEM = 'system'
    SOURCE_CHOICES = [
        (SOURCE_CALLBACK, 'Client Callback'),
        (SOURCE_WEBHOOK, 'Webhook'),
        (SOURCE_SYSTEM, 'System'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE)
    seat_ids = models.JSONField(default=list)
    amount_paise = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    idempotency_key = models.CharField(max_length=64, unique=True, default=default_idempotency_key, editable=False)
    verification_source = models.CharField(max_length=12, choices=SOURCE_CHOICES, blank=True)
    provider_signature_verified = models.BooleanField(default=False)
    webhook_event_count = models.PositiveIntegerField(default=0)
    gateway_status = models.CharField(max_length=40, blank=True)
    failure_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(default=default_payment_expiry)
    razorpay_order_id = models.CharField(max_length=120, blank=True)
    razorpay_payment_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at'], name='payment_status_time_idx'),
            models.Index(fields=['movie', 'created_at'], name='payment_movie_time_idx'),
            models.Index(fields=['theater', 'created_at'], name='payment_theater_time_idx'),
            models.Index(fields=['user', 'status'], name='payment_user_status_idx'),
        ]

    def __str__(self):
        return f'Payment {self.id} - {self.user.username} - {self.status}'


class PaymentWebhookEvent(models.Model):
    provider_event_id = models.CharField(max_length=120, unique=True)
    event_type = models.CharField(max_length=120)
    signature_verified = models.BooleanField(default=False)
    payload_hash = models.CharField(max_length=64)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='webhook_events')
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.provider_event_id} - {self.event_type}'


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        indexes = [
            models.Index(fields=['name'], name='genre_name_idx'),
            models.Index(fields=['slug'], name='genre_slug_idx'),
        ]
        ordering = ['name']

    def __str__(self):
        return self.name


class Language(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)

    class Meta:
        indexes = [
            models.Index(fields=['name'], name='language_name_idx'),
            models.Index(fields=['code'], name='language_code_idx'),
        ]
        ordering = ['name']

    def __str__(self):
        return self.name


class EmailDeliveryTask(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='email_task')
    recipient_email = models.EmailField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    last_error = models.TextField(blank=True)
    context = models.JSONField(default=dict, blank=True)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'next_attempt_at'], name='email_status_next_idx'),
            models.Index(fields=['created_at'], name='email_created_idx'),
        ]

    def __str__(self):
        return f'EmailTask payment={self.payment_id} status={self.status}'
