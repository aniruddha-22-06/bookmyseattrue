web: gunicorn bookmyseat.wsgi
scheduler: python manage.py release_expired_reservations --interval 15
email_worker: python manage.py process_email_queue --interval 10 --batch-size 25
