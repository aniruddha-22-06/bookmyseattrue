# Admin Analytics Dashboard Report

## Feature Summary
- Secure admin-only analytics dashboard page at `/movies/admin-analytics/`.
- Secure admin-only analytics API at `/movies/admin-analytics/api/`.
- Real-time metrics (cached 60 seconds): daily/weekly/monthly revenue, popular movies, busiest theaters, peak booking hours, cancellation metrics.
- Database-level aggregation using ORM `annotate/aggregate` (no full-table materialization in Python).
- Query optimization with composite indexes for `Booking` and `Payment`.
- In-memory cache configured via Django cache backend with automatic invalidation on booking/payment/seat/theater updates.

## Role-Based Access
- Access allowed only for:
  - `is_staff` users
  - `is_superuser` users
  - users in group `analytics_admin`
- Unauthorized API calls return `401`/`403`.

## Admin Credentials Used for Demo
- Username: `analytics_admin`
- Email: `aniruddhaa719@gmail.com`
- Password: `ani2006`

To create or reset this user locally:
- `python manage.py seed_admin_analytics_user --reset-password`

Note: Passwords are stored by Django using one-way password hashing in the auth table, not in plaintext.

## Scale Target
- Designed to run analytics over 50,000+ booking records through DB-side aggregations and indexing.