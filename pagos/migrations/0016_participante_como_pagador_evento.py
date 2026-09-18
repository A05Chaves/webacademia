from django.db import migrations


def usar_participante_en_pagos_evento(apps, schema_editor):
    InscripcionEvento = apps.get_model('pagos', 'InscripcionEvento')
    Pago = apps.get_model('pagos', 'Pago')
    inscripciones = InscripcionEvento.objects.exclude(pago_id=None)
    for inscripcion in inscripciones.iterator():
        Pago.objects.filter(pk=inscripcion.pago_id).update(
            pagador_nombre=inscripcion.participante_nombre,
            pagador_documento=inscripcion.participante_documento,
            pagador_correo=inscripcion.correo,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('pagos', '0015_inscripciones_rechazadas_no_bloquean'),
    ]

    operations = [
        migrations.RunPython(
            usar_participante_en_pagos_evento,
            migrations.RunPython.noop,
        ),
    ]
