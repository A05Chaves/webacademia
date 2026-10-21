from django.core.management.base import BaseCommand
from notificaciones.models import Notificacion
from pagos.cambios_plan import enviar_notificacion_cambio


class Command(BaseCommand):
    help = 'Reintenta correos pendientes o fallidos de cambios de plan.'

    def handle(self, *args, **options):
        ids = list(Notificacion.objects.filter(tipo__in=['CAMBIO_PLAN_SOLICITADO', 'CAMBIO_PLAN_RESULTADO'], canal='EMAIL', estado__in=['PENDIENTE', 'FALLIDA']).values_list('pk', flat=True))
        for pk in ids:
            enviar_notificacion_cambio(pk)
        self.stdout.write(f'Notificaciones procesadas: {len(ids)}')
