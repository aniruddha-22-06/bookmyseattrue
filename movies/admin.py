from django.contrib import admin

from .models import Booking, EmailDeliveryTask, Genre, Language, Movie, Payment, PaymentWebhookEvent, Seat, Theater


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['name', 'rating', 'cast', 'description', 'trailer_url']
    list_filter = ['genres', 'languages']
    search_fields = ['name']
    filter_horizontal = ['genres', 'languages']


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name', 'slug']


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']


@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):
    list_display = ['name', 'movie', 'show_time']


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ['theater', 'seat_number', 'is_booked']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'seat', 'movie', 'theater', 'booked_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'movie', 'theater', 'amount_paise', 'status', 'idempotency_key',
        'gateway_status', 'razorpay_order_id', 'razorpay_payment_id', 'created_at'
    ]
    readonly_fields = ['idempotency_key', 'created_at', 'updated_at']


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ['provider_event_id', 'event_type', 'signature_verified', 'payment', 'processed_at']
    readonly_fields = ['provider_event_id', 'event_type', 'payload_hash', 'processed_at']


@admin.register(EmailDeliveryTask)
class EmailDeliveryTaskAdmin(admin.ModelAdmin):
    list_display = ['payment', 'recipient_email', 'status', 'attempt_count', 'max_attempts', 'next_attempt_at', 'sent_at']
    list_filter = ['status', 'created_at']
    search_fields = ['recipient_email', 'payment__id', 'payment__razorpay_payment_id']
    readonly_fields = ['created_at', 'updated_at']
