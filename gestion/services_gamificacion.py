from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from clases.models import AsistenciaClase
from notificaciones.models import Notificacion

from .models import (
    BilleteraMonedas, ConfiguracionClases, MovimientoMonedas,
    RecompensaOtorgada, TipoRecompensa,
)


@transaction.atomic
def premiar_asistencia(asistencia, habilitada=True):
    """Entrega una sola recompensa por asistencia y devuelve el resultado visible."""
    if (
        not habilitada
        or asistencia.estado != AsistenciaClase.Estados.CONFIRMADA
        or not (asistencia.alumno_id or asistencia.instructor_id)
    ):
        return {'monedas': 0, 'saldo': None}

    configuracion = ConfiguracionClases.cargar()
    es_profesor = bool(asistencia.instructor_id)
    monedas = (
        configuracion.monedas_por_asistencia_profesor
        if es_profesor else configuracion.monedas_por_asistencia
    )
    if not configuracion.gamificacion_activa or monedas <= 0:
        return {'monedas': 0, 'saldo': None}

    usuario = (
        asistencia.instructor.user
        if es_profesor else asistencia.alumno.user
    )
    billetera, _ = BilleteraMonedas.objects.get_or_create(
        usuario=usuario
    )
    billetera = BilleteraMonedas.objects.select_for_update().get(pk=billetera.pk)
    existente = MovimientoMonedas.objects.filter(asistencia=asistencia).first()
    if existente:
        return {'monedas': 0, 'saldo': billetera.saldo}

    nuevo_saldo = billetera.saldo + monedas
    try:
        with transaction.atomic():
            MovimientoMonedas.objects.create(
                billetera=billetera,
                asistencia=asistencia,
                tipo=(
                    MovimientoMonedas.Tipos.ASISTENCIA_PROFESOR
                    if es_profesor else MovimientoMonedas.Tipos.ASISTENCIA
                ),
                cantidad=monedas,
                saldo_resultante=nuevo_saldo,
                descripcion=(
                    f'{"Asistencia como profesor" if es_profesor else "Asistencia"} a '
                    f'{asistencia.clase.titulo or asistencia.clase.get_disciplina_display()} '
                    f'del {asistencia.fecha_clase:%d/%m/%Y}.'
                ),
            )
    except IntegrityError:
        return {'monedas': 0, 'saldo': billetera.saldo}

    billetera.saldo = nuevo_saldo
    billetera.save(update_fields=['saldo', 'actualizada'])
    return {'monedas': monedas, 'saldo': nuevo_saldo}


def progresos_recompensas(alumno_ids):
    """Devuelve las recompensas visibles que todavía no cerraron su ciclo."""
    resultado = {alumno_id: [] for alumno_id in alumno_ids}
    filas = RecompensaOtorgada.objects.filter(
        alumno_id__in=alumno_ids,
        canjeada=False,
    ).values(
        'alumno_id', 'recompensa_id', 'recompensa__nombre',
        'recompensa__simbolo', 'recompensa__imagen',
        'recompensa__cantidad_para_bono',
    ).annotate(cantidad=Count('id')).order_by(
        'recompensa__orden', 'recompensa__nombre'
    )
    for fila in filas:
        fila['imagen'] = fila.pop('recompensa__imagen') or ''
        fila['nombre'] = fila.pop('recompensa__nombre')
        fila['simbolo'] = fila.pop('recompensa__simbolo')
        fila['meta'] = fila.pop('recompensa__cantidad_para_bono')
        resultado.setdefault(fila.pop('alumno_id'), []).append(fila)
    return resultado


@transaction.atomic
def otorgar_recompensa(asistencia, recompensa, otorgada_por, motivo=''):
    """Entrega el premio, acredita monedas y cierra el ciclo si corresponde."""
    if not asistencia.alumno_id:
        return None, 'Las recompensas solo pueden entregarse a estudiantes.'
    if asistencia.estado != AsistenciaClase.Estados.CONFIRMADA:
        return None, 'La asistencia del estudiante no está confirmada.'

    recompensa = TipoRecompensa.objects.select_for_update().get(pk=recompensa.pk)
    if not recompensa.activa:
        return None, 'Esta recompensa se encuentra inactiva.'
    if RecompensaOtorgada.objects.filter(
        recompensa=recompensa,
        asistencia=asistencia,
    ).exists():
        return None, 'Este premio ya fue entregado al estudiante en esta clase.'

    billetera, _ = BilleteraMonedas.objects.get_or_create(
        usuario=asistencia.alumno.user
    )
    billetera = BilleteraMonedas.objects.select_for_update().get(pk=billetera.pk)
    entrega = RecompensaOtorgada.objects.create(
        recompensa=recompensa,
        alumno=asistencia.alumno,
        asistencia=asistencia,
        otorgada_por=otorgada_por,
        nombre_snapshot=recompensa.nombre,
        simbolo_snapshot=recompensa.simbolo,
        imagen_snapshot=recompensa.imagen.name if recompensa.imagen else '',
        monedas_otorgadas=recompensa.valor_monedas,
        motivo=motivo.strip(),
    )

    if recompensa.valor_monedas:
        billetera.saldo += recompensa.valor_monedas
        MovimientoMonedas.objects.create(
            billetera=billetera,
            recompensa_otorgada=entrega,
            tipo=MovimientoMonedas.Tipos.RECOMPENSA,
            cantidad=recompensa.valor_monedas,
            saldo_resultante=billetera.saldo,
            descripcion=f'Recompensa: {recompensa.nombre}.',
            registrado_por=otorgada_por,
        )

    progreso = RecompensaOtorgada.objects.filter(
        alumno=asistencia.alumno,
        recompensa=recompensa,
        canjeada=False,
    ).count()
    bono = 0
    if recompensa.cantidad_para_bono and progreso >= recompensa.cantidad_para_bono:
        bono = recompensa.monedas_bono
        ahora = timezone.now()
        RecompensaOtorgada.objects.filter(
            alumno=asistencia.alumno,
            recompensa=recompensa,
            canjeada=False,
        ).update(canjeada=True, canjeada_en=ahora)
        entrega.bono_otorgado = bono
        entrega.canjeada = True
        entrega.canjeada_en = ahora
        entrega.save(update_fields=['bono_otorgado', 'canjeada', 'canjeada_en'])
        progreso = 0
        if bono:
            billetera.saldo += bono
            MovimientoMonedas.objects.create(
                billetera=billetera,
                recompensa_otorgada=entrega,
                tipo=MovimientoMonedas.Tipos.BONO_RECOMPENSA,
                cantidad=bono,
                saldo_resultante=billetera.saldo,
                descripcion=(
                    f'Bono por completar {recompensa.cantidad_para_bono} '
                    f'{recompensa.nombre}.'
                ),
                registrado_por=otorgada_por,
            )

    billetera.save(update_fields=['saldo', 'actualizada'])
    detalle_bono = (
        f' Además completaste el ciclo y recibiste {bono} monedas adicionales.'
        if bono else ''
    )
    detalle_motivo = f' Motivo: {motivo.strip()}.' if motivo.strip() else ''
    Notificacion.objects.create(
        usuario=asistencia.alumno.user,
        tipo=Notificacion.Tipos.RECOMPENSA,
        titulo=f'{recompensa.simbolo} ¡Recibiste {recompensa.nombre}!',
        mensaje=(
            f'Tu profesor te otorgó {recompensa.nombre}. '
            f'Ganaste {recompensa.valor_monedas} monedas.'
            f'{detalle_bono}{detalle_motivo}'
        ),
        fecha_programada=timezone.now(),
        canal=Notificacion.Canales.INTERNA,
    )
    return {
        'entrega': entrega,
        'monedas': recompensa.valor_monedas,
        'bono': bono,
        'saldo': billetera.saldo,
        'progreso': progreso,
    }, None
