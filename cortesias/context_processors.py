from django.utils import timezone

from .models import ClaseCortesia


def alertas_cortesias(request):
    user = request.user
    puede_gestionar = user.is_authenticated and (
        user.is_staff or hasattr(user, 'perfil_instructor')
    )
    if not puede_gestionar:
        return {
            'puede_gestionar_cortesias': False,
            'cortesias_agendadas_pendientes': 0,
        }

    total = ClaseCortesia.objects.filter(
        clase__isnull=False,
        fecha_clase__gte=timezone.localdate(),
    ).count()
    return {
        'puede_gestionar_cortesias': True,
        'cortesias_agendadas_pendientes': total,
    }
