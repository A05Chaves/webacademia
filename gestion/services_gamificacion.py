from django.db import IntegrityError, transaction

from clases.models import AsistenciaClase

from .models import BilleteraMonedas, ConfiguracionClases, MovimientoMonedas


@transaction.atomic
def premiar_asistencia(asistencia, habilitada=True):
    """Entrega una sola recompensa por asistencia y devuelve el resultado visible."""
    if (
        not habilitada
        or not asistencia.alumno_id
        or asistencia.estado != AsistenciaClase.Estados.CONFIRMADA
    ):
        return {'monedas': 0, 'saldo': None}

    configuracion = ConfiguracionClases.cargar()
    monedas = configuracion.monedas_por_asistencia
    if not configuracion.gamificacion_activa or monedas <= 0:
        return {'monedas': 0, 'saldo': None}

    billetera, _ = BilleteraMonedas.objects.get_or_create(
        usuario=asistencia.alumno.user
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
                tipo=MovimientoMonedas.Tipos.ASISTENCIA,
                cantidad=monedas,
                saldo_resultante=nuevo_saldo,
                descripcion=(
                    f'Asistencia a {asistencia.clase.titulo or asistencia.clase.get_disciplina_display()} '
                    f'del {asistencia.fecha_clase:%d/%m/%Y}.'
                ),
            )
    except IntegrityError:
        return {'monedas': 0, 'saldo': billetera.saldo}

    billetera.saldo = nuevo_saldo
    billetera.save(update_fields=['saldo', 'actualizada'])
    return {'monedas': monedas, 'saldo': nuevo_saldo}
