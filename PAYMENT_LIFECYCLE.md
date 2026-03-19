# Payment Lifecycle, Idempotency, and Webhook Security (Razorpay)

## 1. End-to-End Lifecycle
1. User selects seats and submits.
2. Server runs a DB transaction with row-level seat lock (`SELECT ... FOR UPDATE`) and marks selected seats as `locked_by=user` with `lock_expires_at = now + 2 minutes`.
3. Server creates/reuses a `Payment` in `pending` state with the same expiry as seat lock.
4. Server sends Razorpay `order_id` to frontend.
5. User completes payment in Razorpay Checkout.
6. Frontend posts callback payload (`payment_id`, `order_id`, `signature`) to server `/movies/payment/verify/`.
7. Server verifies Razorpay signature server-side.
8. On success, server re-locks payment + seats in one DB transaction, verifies lock ownership/expiry, creates bookings, marks seats booked, and clears lock fields.
9. Payment status moves to `paid`.
10. Independent Razorpay webhook is also processed at `/movies/payment/webhook/razorpay/` for eventual consistency and recovery.

## 2. Idempotency Design
- `Payment.idempotency_key` is unique.
- During checkout refresh/retry, server reuses an existing pending payment for the same user+movie+theater+seat set and amount.
- Razorpay order `receipt` is set to this idempotency key.
- Booking finalization uses DB row lock (`select_for_update`) on payment and seats.
- If same callback/webhook arrives again, finalized `paid` payment is treated as already processed.

## 3. Webhook Security
- Webhook endpoint is CSRF-exempt but **HMAC verified** using `RAZORPAY_WEBHOOK_SECRET`.
- Signature header: `X-Razorpay-Signature`.
- Raw body HMAC SHA-256 is compared with constant-time `hmac.compare_digest`.
- Invalid signature is rejected with `400`.

## 4. Duplicate Webhook / Replay Protection
- Event ID: `X-Razorpay-Event-Id` (fallback to payload hash).
- Stored in `PaymentWebhookEvent.provider_event_id` (unique).
- Replayed/duplicate events are detected and ignored safely.

## 5. Success, Failure, Cancellation, Timeout
- Success: `status=paid`, seats booked atomically.
- Failure (signature mismatch, seat conflict, invalid fields): `status=failed` with reason.
- Cancellation (user dismiss/cancel): `status=cancelled` and seat locks are released.
- Timeout: stale pending payments auto-marked `expired`.
- Expired lock release: scheduler process `python manage.py release_expired_reservations --interval 15` continuously clears expired seat locks with no user refresh required.
- Webhook can still recover captured payment if provider confirms capture after client timeout.

## 6. Partial Failure Handling
- Seat booking and payment status update run inside one DB transaction.
- If seat lock/booking fails, payment marked failed with detailed `failure_reason`.
- This prevents silent half-success states.

## 7. Fraud and Tampering Mitigation
- No trust in frontend callback alone.
- Server verifies provider signatures.
- Order mismatch checks (`provider order_id` vs stored order).
- Duplicate/replay controls on both callback path (idempotent finalization) and webhook path (unique event tracking).

## 8. Required Environment Variables
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`

## 9. Webhook Setup (Razorpay Dashboard)
- URL: `https://<your-domain>/movies/payment/webhook/razorpay/`
- Events: at minimum `payment.captured`, `payment.failed`, `order.paid`
- Secret: same value as `RAZORPAY_WEBHOOK_SECRET`

## 10. Quick Verification Checklist
- Trigger payment success: seats should book exactly once and lock should clear.
- Simulate two users selecting same seat within milliseconds: only one user acquires seat lock; the other receives seat-locked error.
- Refresh/re-submit callback: no duplicate booking.
- Send same webhook twice: second should be ignored.
- Invalid webhook signature: should fail with 400.
- Leave payment pending > timeout window: payment becomes `expired` and seat lock is auto-released by scheduler.

## 11. Consistency Model (What Guarantees We Provide)
- Seat selection and payment finalization use **strong consistency per seat row** inside a single database transaction (`transaction.atomic` + `select_for_update`).
- This gives linearizable behavior for concurrent seat updates on the same row: two overlapping requests cannot both pass lock checks and book the same seat.
- Global system behavior is **eventually consistent** for asynchronous gateway updates (webhook vs callback), resolved via idempotency keys and replay-safe webhook event table.

## 12. Live Timeout + Cross-Device Polling
- Checkout page shows a live countdown timer for seat lock expiry (`MM:SS`).
- Browser polls `/movies/payment/lock-status/?payment_db_id=<id>` every 5 seconds.
- Endpoint validates current user ownership and lock validity for all seats.
- If lock expires or becomes invalid on another device/session, frontend disables pay action and redirects user back to seat selection.

## 13. Automated Booking Confirmation Email (Async + Retry)
- After payment is finalized as `paid`, server enqueues one `EmailDeliveryTask` (1:1 with payment) in DB via `transaction.on_commit`.
- Booking API response is not blocked by SMTP call; delivery is handled by background worker:
  - `python manage.py process_email_queue --interval 10`
  - Or one-shot: `python manage.py process_email_queue --once`
- Email content uses Django template engine:
  - `templates/emails/booking_confirmation_subject.txt`
  - `templates/emails/booking_confirmation.txt`
  - `templates/emails/booking_confirmation.html`
- Retry policy: exponential backoff (`2^attempt * 30s`, max 1 hour), up to `max_attempts` (default 5).
- Failures are logged (`movies.email` logger) and tracked in admin via `EmailDeliveryTask`.

## 14. Fraud / Replay Attack Mitigation Summary
- Frontend callback is never trusted alone; server validates Razorpay callback signature.
- Webhook requests require HMAC signature (`X-Razorpay-Signature`) against raw body.
- Duplicate webhook replays are ignored using unique `provider_event_id`.
- Payment row locking + idempotent state transitions prevent double booking from repeated callbacks/webhooks.
- Order ID mismatch is explicitly rejected and marked failed.
