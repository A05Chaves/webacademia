import django.db.models.deletion
from django.db import migrations, models


def vincular_eventos_existentes(apps, schema_editor):
    Movimiento = apps.get_model('finanzas', 'MovimientoFinanciero')
    for movimiento in Movimiento.objects.filter(
        pago__inscripcion_evento__isnull=False,
        evento__isnull=True,
    ).select_related('pago__inscripcion_evento'):
        movimiento.evento_id = movimiento.pago.inscripcion_evento.evento_id
        movimiento.save(update_fields=['evento'])


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0002_categoriafinanciera_movimientofinanciero_categoria'),
        ('pagos', '0013_unificar_academia_galeras'),
    ]

    operations = [
        migrations.AddField(
            model_name='movimientofinanciero',
            name='evento',
            field=models.ForeignKey(
                blank=True,
                help_text='Evento específico que originó este ingreso o gasto.',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='movimientos_financieros',
                to='pagos.evento',
            ),
        ),
        migrations.RunPython(
            vincular_eventos_existentes,
            migrations.RunPython.noop,
        ),
    ]
