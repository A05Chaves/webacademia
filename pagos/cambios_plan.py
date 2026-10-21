from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from notificaciones.models import Notificacion
from planes.models import Suscripcion
from .models import Pago


def pago_mensualidad_pendiente(alumno):
    return Pago.objects.filter(alumno=alumno, estado=Pago.Estados.PENDIENTE, tipo__in=[Pago.Tipos.MENSUALIDAD, Pago.Tipos.PROMOCION]).order_by('fecha_reporte', 'pk').first() if alumno else None


def ultima_cobertura(alumno):
    return Suscripcion.objects.filter(alumno=alumno).exclude(estado__in=['SUSPENDIDA', 'PENDIENTE_PAGO']).order_by('-fecha_vencimiento', '-pk').first() if alumno else None


def suscripcion_referencia(alumno):
    if not alumno:
        return None
    hoy = timezone.localdate()
    suscripciones = Suscripcion.objects.filter(alumno=alumno).exclude(
        estado__in=['SUSPENDIDA', 'PENDIENTE_PAGO']
    ).select_related('plan')
    vigente = suscripciones.filter(fecha_inicio__lte=hoy, fecha_vencimiento__gte=hoy).order_by('-fecha_inicio', '-pk').first()
    return vigente or suscripciones.filter(fecha_inicio__lte=hoy).order_by('-fecha_vencimiento', '-pk').first() or suscripciones.order_by('fecha_inicio').first()


def registrar_solicitud_cambio(pago):
    anterior = suscripcion_referencia(pago.alumno)
    if anterior and anterior.plan_id != pago.plan_id:
        pago.cambio_plan_solicitado = True
        pago.plan_anterior = anterior.plan


def enviar_notificacion_cambio(notificacion_id):
    aviso = Notificacion.objects.select_related('usuario').get(pk=notificacion_id)
    if aviso.estado == Notificacion.Estados.ENVIADA:
        return
    try:
        if not aviso.usuario.email:
            raise ValueError('El usuario no tiene un correo registrado.')
        enviados = send_mail(aviso.titulo, aviso.mensaje, settings.DEFAULT_FROM_EMAIL, [aviso.usuario.email], fail_silently=False)
        if not enviados:
            raise ValueError('El servicio de correo no confirmó el envío.')
    except Exception as error:
        aviso.estado = Notificacion.Estados.FALLIDA
        aviso.error_envio = str(error)[:1000]
    else:
        aviso.estado = Notificacion.Estados.ENVIADA
        aviso.fecha_envio = timezone.now()
        aviso.error_envio = ''
    aviso.save(update_fields=['estado', 'error_envio', 'fecha_envio', 'actualizado'])


def notificar_cambio_plan(pago, resultado=False):
    if not pago.cambio_plan_solicitado or not pago.alumno_id:
        return
    tipo = Notificacion.Tipos.CAMBIO_PLAN_RESULTADO if resultado else Notificacion.Tipos.CAMBIO_PLAN_SOLICITADO
    usuario = pago.alumno.user
    nombre = usuario.get_full_name() or usuario.username
    anterior = pago.plan_anterior.nombre if pago.plan_anterior_id else 'Sin plan anterior'
    nuevo = pago.plan
    if resultado:
        aprobado = pago.estado == Pago.Estados.APROBADO
        titulo = 'Cambio de plan aprobado' if aprobado and pago.suscripcion_id else ('Cambio de plan pendiente de cobertura' if aprobado else 'Cambio de plan rechazado')
    else:
        titulo = 'Solicitud de cambio de plan pendiente de revisión'
    limites = ('Acceso ilimitado' if nuevo.asistencia_ilimitada else f'Clases por semana: {nuevo.clases_semana}. Clases por mes: {nuevo.clases_mes}.')
    mensaje = f'{titulo}\n\nEstudiante: {nombre}\nPago: #{pago.pk}\nPlan anterior: {anterior}\nPlan solicitado: {nuevo.nombre}\n{limites}\nMensualidades solicitadas: {pago.mensualidades}\nValor reportado: $ {pago.valor:,.0f}\n'
    if resultado and pago.estado == Pago.Estados.APROBADO and pago.suscripcion_id:
        mensaje += f'El nuevo plan aplica desde el {pago.suscripcion.fecha_inicio:%d/%m/%Y} hasta el {pago.suscripcion.fecha_vencimiento:%d/%m/%Y}. Hasta esa fecha de inicio se conserva la cobertura vigente.\n'
    elif resultado and pago.estado == Pago.Estados.APROBADO:
        mensaje += 'Se aprobó el abono, pero no se habilitó cobertura nueva. El cambio de plan aún no entra en vigor.\n'
    elif resultado:
        mensaje += f'El cambio no se aplicó. Observación: {pago.observacion_admin or "Sin observación"}.\n'
    else:
        mensaje += 'Esta es una solicitud, no una aprobación. El plan actual no cambia hasta que la administración apruebe y comience la nueva cobertura.\n'
    destinatarios = {usuario.pk: usuario}
    if not resultado:
        administradores = get_user_model().objects.filter(is_active=True).filter(Q(rol='ADMIN') | Q(is_superuser=True))
        destinatarios.update({u.pk: u for u in administradores})
    for receptor in destinatarios.values():
        aviso, creado = Notificacion.objects.get_or_create(usuario=receptor, pago=pago, tipo=tipo, canal=Notificacion.Canales.EMAIL, defaults={'titulo': titulo, 'mensaje': mensaje, 'fecha_programada': timezone.now()})
        if creado:
            transaction.on_commit(lambda pk=aviso.pk: enviar_notificacion_cambio(pk))
