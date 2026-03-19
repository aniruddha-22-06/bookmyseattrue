from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .analytics import invalidate_admin_analytics_cache
from .models import Booking, Payment, Seat, Theater


@receiver(post_save, sender=Booking)
@receiver(post_delete, sender=Booking)
@receiver(post_save, sender=Payment)
@receiver(post_delete, sender=Payment)
@receiver(post_save, sender=Seat)
@receiver(post_delete, sender=Seat)
@receiver(post_save, sender=Theater)
@receiver(post_delete, sender=Theater)
def clear_analytics_cache_on_data_change(**kwargs):
    invalidate_admin_analytics_cache()
