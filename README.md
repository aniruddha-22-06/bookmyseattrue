# BOOKMYSEAT

Movie ticket booking system with secure payments, concurrency-safe seat locking, admin analytics, and trailer embeds.

## Features
- Multi-select filtering by genre and language with dynamic facet counts.
- Pagination + sorting for large catalogs.
- Concurrency-safe seat reservation with 2-minute locks + auto release.
- Razorpay integration with idempotency + secure webhook verification.
- Async booking confirmation emails with retry queue.
- Admin analytics dashboard with cached DB aggregations.
- Secure YouTube trailer embeds with validation + lazy loading.

## Tech Stack
- Django
- SQLite (local) / Postgres (production)
- Razorpay (payment gateway)

## Local Setup
```powershell
cd e:\bookmyseattrailer\bookmyseattrailer\bookmyseattrailer\BOOKMYSEAT\BOOKMYSEAT\BOOKMYSEAT
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_recent_movies
python manage.py runserver
```

## Background Workers (separate terminals)
```powershell
python manage.py release_expired_reservations --interval 15
python manage.py process_email_queue --interval 10
```

## Environment Variables (.env)
```ini
DJANGO_SECRET_KEY=your_secret
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000

# Payments
PAYMENT_MOCK_MODE=True
RAZORPAY_KEY_ID=rzp_test_xxx
RAZORPAY_KEY_SECRET=xxx
RAZORPAY_WEBHOOK_SECRET=xxx

# Email (SMTP)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_gmail_app_password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=your_email@gmail.com
```

## Admin Analytics Login
Create/reset admin user:
```powershell
python manage.py seed_admin_analytics_user --reset-password
```
Default admin username is `admin` and the default password is `ani@2006`.

## Render Deploy (quick)
- Root Directory: `BOOKMYSEAT/BOOKMYSEAT/BOOKMYSEAT`
- Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
- Start: `gunicorn bookmyseat.wsgi`
- Add background workers:
  - `python manage.py release_expired_reservations --interval 15`
  - `python manage.py process_email_queue --interval 10 --batch-size 25`

## Notes
- For internship/demo: use `PAYMENT_MOCK_MODE=True` or Razorpay test keys.
- Emails require a valid SMTP app password.
