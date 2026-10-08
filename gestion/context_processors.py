from .models import BilleteraMonedas
from notificaciones.models import Notificacion


def gamificacion_usuario(request):
    if not request.user.is_authenticated:
        return {}
    billetera, _ = BilleteraMonedas.objects.get_or_create(usuario=request.user)
    es_estudiante = hasattr(request.user, 'perfil_alumno')
    notificacion = None
    if es_estudiante:
        notificacion = Notificacion.objects.filter(
            usuario=request.user,
            tipo=Notificacion.Tipos.RECOMPENSA,
            estado=Notificacion.Estados.PENDIENTE,
            canal=Notificacion.Canales.INTERNA,
        ).order_by('fecha_programada', 'id').first()
    return {
        'billetera_monedas_usuario': billetera,
        'notificacion_recompensa_pendiente': notificacion,
        'consultar_notificaciones_recompensa': es_estudiante,
    }
