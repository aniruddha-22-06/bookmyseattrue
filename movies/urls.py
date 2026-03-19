from django.urls import path

from . import views

urlpatterns = [
    path('', views.movie_list, name='movie_list'),
    path('<int:movie_id>/theaters', views.theater_list, name='theater_list'),
    path('<int:movie_id>/trailer/open/', views.open_trailer, name='open_trailer'),
    path('theater/<int:theater_id>/seats/book/', views.book_seats, name='book_seats'),
    path('payment/checkout/', views.payment_checkout, name='payment_checkout'),
    path('payment/lock-status/', views.payment_lock_status, name='payment_lock_status'),
    path('payment/verify/', views.verify_payment, name='verify_payment'),
    path('payment/cancel/', views.cancel_payment, name='cancel_payment'),
    path('payment/webhook/razorpay/', views.razorpay_webhook, name='razorpay_webhook'),
    path('admin-analytics/', views.admin_analytics_dashboard, name='admin_analytics_dashboard'),
    path('admin-analytics/api/', views.admin_analytics_api, name='admin_analytics_api'),
]

