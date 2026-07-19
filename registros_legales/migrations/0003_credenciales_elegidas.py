from django.contrib.auth.hashers import make_password
from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower


def preparar_credenciales_existentes(apps, schema_editor):
    Registro = apps.get_model('registros_legales', 'RegistroLegalEstudiante')
    usados = set()
    for registro in Registro.objects.order_by('id'):
        base = (registro.documento or f'estudiante-{registro.id}').strip()
        username = base
        consecutivo = 2
        while username.lower() in usados:
            username = f'{base}-{consecutivo}'
            consecutivo += 1
        usados.add(username.lower())
        registro.usuario_solicitado = username
        registro.password_hash = make_password(registro.documento or username)
        registro.save(update_fields=['usuario_solicitado', 'password_hash'])


class Migration(migrations.Migration):
    dependencies = [('registros_legales', '0002_registrolegalestudiante_plan_interes')]

    operations = [
        migrations.AddField(
            model_name='registrolegalestudiante',
            name='usuario_solicitado',
            field=models.CharField(max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='registrolegalestudiante',
            name='password_hash',
            field=models.CharField(editable=False, max_length=128, null=True),
        ),
        migrations.RunPython(preparar_credenciales_existentes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='registrolegalestudiante',
            name='usuario_solicitado',
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name='registrolegalestudiante',
            name='password_hash',
            field=models.CharField(editable=False, max_length=128),
        ),
        migrations.AddConstraint(
            model_name='registrolegalestudiante',
            constraint=models.UniqueConstraint(
                Lower('usuario_solicitado'),
                condition=~Q(estado='RECHAZADO'),
                name='registro_username_activo_unico_sin_mayusculas',
            ),
        ),
    ]
