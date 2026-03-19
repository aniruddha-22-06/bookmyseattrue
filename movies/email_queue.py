import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import EmailDeliveryTask, Payment

logger = logging.getLogger('movies.email')


def enqueue_booking_confirmation_email(payment: Payment, seat_numbers):
    if not payment.user.email:
        logger.warning('Skipping confirmation email: missing user email for payment_id=%s', payment.id)
        return None

    context = {
        'username': payment.user.username,
        'movie_name': payment.movie.name,
        'theater_name': payment.theater.name,
        'show_time': payment.theater.show_time.isoformat(),
        'seat_numbers': sorted(seat_numbers),
        'payment_id': payment.id,
        'gateway_payment_id': payment.razorpay_payment_id,
        'amount_inr': payment.amount_paise / 100,
        'booked_at': timezone.now().isoformat(),
    }

    task, created = EmailDeliveryTask.objects.get_or_create(
        payment=payment,
        defaults={
            'recipient_email': payment.user.email,
            'context': context,
        },
    )
    if not created:
        task.recipient_email = payment.user.email
        task.context = context
        task.save(update_fields=['recipient_email', 'context', 'updated_at'])
    return task


def send_booking_confirmation_email(payment: Payment, seat_numbers):
    task = enqueue_booking_confirmation_email(payment, seat_numbers)
    if not task:
        return None
    process_single_email_task(task)
    return task
def _build_email_message(task: EmailDeliveryTask):
    context = dict(task.context)
    subject = render_to_string('emails/booking_confirmation_subject.txt', context).strip()
    text_body = render_to_string('emails/booking_confirmation.txt', context)
    html_body = render_to_string('emails/booking_confirmation.html', context)

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@bookmyseat.local')
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[task.recipient_email],
    )
    message.attach_alternative(html_body, 'text/html')
    return message


def process_single_email_task(task: EmailDeliveryTask):
    now = timezone.now()
    if task.status == EmailDeliveryTask.STATUS_SENT:
        return False
    if task.next_attempt_at and task.next_attempt_at > now:
        return False
    if task.attempt_count >= task.max_attempts:
        if task.status != EmailDeliveryTask.STATUS_FAILED:
            task.status = EmailDeliveryTask.STATUS_FAILED
            task.last_error = task.last_error or 'Maximum retry attempts reached.'
            task.save(update_fields=['status', 'last_error', 'updated_at'])
        return False

    task.status = EmailDeliveryTask.STATUS_PROCESSING
    task.attempt_count += 1
    task.save(update_fields=['status', 'attempt_count', 'updated_at'])

    try:
        message = _build_email_message(task)
        message.send(fail_silently=False)
        task.status = EmailDeliveryTask.STATUS_SENT
        task.last_error = ''
        task.sent_at = timezone.now()
        task.next_attempt_at = timezone.now()
        task.save(update_fields=['status', 'last_error', 'sent_at', 'next_attempt_at', 'updated_at'])
        logger.info('Booking email sent payment_id=%s attempt=%s', task.payment_id, task.attempt_count)
        return True
    except Exception as exc:
        delay_seconds = min(2 ** task.attempt_count * 30, 3600)
        task.status = EmailDeliveryTask.STATUS_PENDING if task.attempt_count < task.max_attempts else EmailDeliveryTask.STATUS_FAILED
        task.last_error = str(exc)[:1000]
        task.next_attempt_at = timezone.now() + timedelta(seconds=delay_seconds)
        task.save(update_fields=['status', 'last_error', 'next_attempt_at', 'updated_at'])
        logger.exception(
            'Booking email failed payment_id=%s attempt=%s next_retry=%s',
            task.payment_id,
            task.attempt_count,
            task.next_attempt_at.isoformat(),
        )
        return False
