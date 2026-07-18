from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver

from .models import SesionTV


@receiver(user_logged_out)
def cerrar_sesiones_tv_al_salir(sender, request, user, **kwargs):
    """Invalida los códigos TV del profesor cuando cierra su sesión."""
    if user and getattr(user, 'is_authenticated', False):
        SesionTV.objects.filter(propietario=user, activa=True).update(activa=False)
