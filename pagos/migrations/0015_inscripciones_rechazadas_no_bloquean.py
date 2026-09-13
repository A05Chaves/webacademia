from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [('pagos', '0014_jornadas_evento_y_tarifa_inscripcion')]

    operations = [
        migrations.RemoveConstraint(
            model_name='inscripcionevento',
            name='inscripcion_categoria_documento_activa_unica',
        ),
        migrations.RemoveConstraint(
            model_name='inscripcionevento',
            name='inscripcion_sin_categoria_documento_activa_unica',
        ),
        migrations.RemoveConstraint(
            model_name='inscripcionevento',
            name='inscripcion_jornada_documento_activa_unica',
        ),
        migrations.AddConstraint(
            model_name='inscripcionevento',
            constraint=models.UniqueConstraint(
                fields=('evento', 'participante_documento', 'categoria_evento'),
                condition=(
                    ~Q(estado__in=('CANCELADA', 'RECHAZADA'))
                    & Q(categoria_evento__isnull=False)
                ),
                name='inscripcion_categoria_documento_activa_unica',
            ),
        ),
        migrations.AddConstraint(
            model_name='inscripcionevento',
            constraint=models.UniqueConstraint(
                fields=('evento', 'participante_documento'),
                condition=(
                    ~Q(estado__in=('CANCELADA', 'RECHAZADA'))
                    & Q(categoria_evento__isnull=True)
                    & Q(jornada__isnull=True)
                ),
                name='inscripcion_sin_categoria_documento_activa_unica',
            ),
        ),
        migrations.AddConstraint(
            model_name='inscripcionevento',
            constraint=models.UniqueConstraint(
                fields=('evento', 'participante_documento', 'jornada'),
                condition=(
                    ~Q(estado__in=('CANCELADA', 'RECHAZADA'))
                    & Q(categoria_evento__isnull=True)
                    & Q(jornada__isnull=False)
                ),
                name='inscripcion_jornada_documento_activa_unica',
            ),
        ),
    ]
