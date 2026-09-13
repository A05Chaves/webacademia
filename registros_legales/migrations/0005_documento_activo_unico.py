from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower


NOTA_DUPLICADO = (
    'Registro rechazado automáticamente al aplicar el control de documentos: '
    'existía otra solicitud vigente con el mismo documento.'
)


def depurar_registros_vigentes_duplicados(apps, schema_editor):
    Registro = apps.get_model('registros_legales', 'RegistroLegalEstudiante')
    grupos = {}

    for registro in Registro.objects.exclude(estado='RECHAZADO').order_by('id'):
        llave = (registro.documento or '').strip().lower()
        grupos.setdefault(llave, []).append(registro)

    for registros in grupos.values():
        if len(registros) < 2:
            continue

        aprobados = [registro for registro in registros if registro.estado == 'APROBADO']
        conservar = aprobados[0] if aprobados else registros[0]
        for registro in registros:
            if registro.pk == conservar.pk:
                continue
            observacion = (registro.observacion_admin or '').strip()
            registro.estado = 'RECHAZADO'
            registro.observacion_admin = (
                f'{observacion}\n{NOTA_DUPLICADO}'.strip()
            )
            registro.save(update_fields=['estado', 'observacion_admin'])


class Migration(migrations.Migration):
    dependencies = [('registros_legales', '0004_fecha_diligenciamiento_automatica')]

    operations = [
        migrations.RunPython(
            depurar_registros_vigentes_duplicados,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='registrolegalestudiante',
            constraint=models.UniqueConstraint(
                Lower('documento'),
                condition=~Q(estado='RECHAZADO'),
                name='registro_documento_activo_unico_sin_mayusculas',
            ),
        ),
    ]
