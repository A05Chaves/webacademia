from django.db import migrations


def nombre_propio(valor):
    return valor.strip().title() if valor else valor


def normalizar_nombres(apps, schema_editor):
    Usuario = apps.get_model('usuarios', 'Usuario')
    Alumno = apps.get_model('alumnos', 'Alumno')
    RegistroLegal = apps.get_model(
        'registros_legales', 'RegistroLegalEstudiante'
    )

    configuraciones = (
        (Usuario, ('first_name', 'last_name')),
        (Alumno, ('nombre_acudiente',)),
        (
            RegistroLegal,
            (
                'nombres', 'apellidos', 'contacto_emergencia_nombre',
                'nombre_acudiente',
            ),
        ),
    )
    for modelo, campos in configuraciones:
        actualizados = []
        for objeto in modelo.objects.only('pk', *campos).iterator():
            cambio = False
            for campo in campos:
                valor_actual = getattr(objeto, campo)
                valor_nuevo = nombre_propio(valor_actual)
                if valor_nuevo != valor_actual:
                    setattr(objeto, campo, valor_nuevo)
                    cambio = True
            if cambio:
                actualizados.append(objeto)
        if actualizados:
            modelo.objects.bulk_update(actualizados, campos, batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('gestion', '0006_configuracionhome_orden_video_promocional'),
        ('alumnos', '0005_alumno_foto_perfil'),
        ('usuarios', '0003_usuario_username_modificado_and_more'),
        ('registros_legales', '0003_credenciales_elegidas'),
    ]

    operations = [
        migrations.RunPython(normalizar_nombres, migrations.RunPython.noop),
    ]
