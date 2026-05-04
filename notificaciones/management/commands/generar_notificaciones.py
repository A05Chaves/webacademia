from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from planes.models import Suscripcion
from notificaciones.models import Notificacion


class Command(BaseCommand):
    help = 'Genera notificaciones automáticas de vencimiento de mensualidades.'

    def handle(self, *args, **kwargs):
        hoy = timezone.now().date()
        ahora = timezone.now()

        dias_aviso = [7, 3, 1]
        total_creadas = 0

        suscripciones = Suscripcion.objects.select_related(
            'alumno__user',
            'plan'
        ).filter(
            estado__in=['ACTIVA', 'VENCIDA']
        )

        for suscripcion in suscripciones:
            alumno = suscripcion.alumno
            usuario = alumno.user
            dias_restantes = (suscripcion.fecha_vencimiento - hoy).days

            if dias_restantes in dias_aviso:
                titulo = 'Recordatorio de mensualidad'
                mensaje = (
                    f'Tu mensualidad vence en {dias_restantes} día(s). '
                    f'Fecha de vencimiento: {suscripcion.fecha_vencimiento}.'
                )
                tipo = 'RECORDATORIO_PAGO'

            elif dias_restantes == 0:
                titulo = 'Mensualidad vence hoy'
                mensaje = (
                    f'Tu mensualidad vence hoy. '
                    f'Fecha de vencimiento: {suscripcion.fecha_vencimiento}.'
                )
                tipo = 'VENCIMIENTO'

            elif dias_restantes < 0:
                titulo = 'Mensualidad vencida'
                mensaje = (
                    f'Tu mensualidad está vencida desde '
                    f'{suscripcion.fecha_vencimiento}.'
                )
                tipo = 'MORA'

            else:
                continue

            existe = Notificacion.objects.filter(
                usuario=usuario,
                tipo=tipo,
                fecha_programada__date=hoy,
                mensaje=mensaje
            ).exists()

            if not existe:
                Notificacion.objects.create(
                    usuario=usuario,
                    tipo=tipo,
                    titulo=titulo,
                    mensaje=mensaje,
                    fecha_programada=ahora,
                    estado='PENDIENTE',
                    canal='INTERNA'
                )
                total_creadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Notificaciones creadas: {total_creadas}'
            )
        )
