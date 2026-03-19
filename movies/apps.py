from django.apps import AppConfig


class MoviesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'movies'

    def ready(self):
        # Registers cache invalidation signals for analytics.
        from . import signals  # noqa: F401
