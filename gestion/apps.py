from django.apps import AppConfig


class GestionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestion'

    def ready(self):
        # Registra el cierre seguro de las sesiones del Modo TV.
        from . import signals  # noqa: F401
