from django.db import migrations


def preparar_comprobantes_existentes(apps, schema_editor):
    Pago = apps.get_model('pagos', 'Pago')
    for pago in Pago.objects.filter(estado='APROBADO').select_related('plan').iterator():
        if not pago.numero_comprobante:
            anio = (pago.fecha_validacion or pago.fecha_reporte).year
            pago.numero_comprobante = f'CP-{anio}-{pago.id:06d}'
        if not pago.fecha_comprobante:
            pago.fecha_comprobante = pago.fecha_validacion or pago.fecha_reporte
        if not pago.concepto_detalle:
            pago.concepto_detalle = (
                pago.plan.nombre if pago.plan_id else {
                    'EVENTO': 'Evento de academia',
                    'PROMOCION': 'Mensualidad con promoción',
                    'OTRO': 'Otro ingreso de academia',
                }.get(pago.tipo, 'Mensualidad')
            )
        pago.save(update_fields=[
            'numero_comprobante', 'fecha_comprobante', 'concepto_detalle',
        ])


class Migration(migrations.Migration):
    dependencies = [
        ('pagos', '0004_evento_pago_comprobante_hash_pago_concepto_detalle_and_more'),
    ]

    operations = [
        migrations.RunPython(
            preparar_comprobantes_existentes, migrations.RunPython.noop
        ),
    ]
