from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower


class Migration(migrations.Migration):

    dependencies = [
        ('instructores', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='instructor',
            name='foto',
            field=models.ImageField(
                blank=True, null=True, upload_to='instructores/fotos/'
            ),
        ),
        migrations.CreateModel(
            name='SolicitudRegistroProfesor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombres', models.CharField(max_length=100)),
                ('apellidos', models.CharField(max_length=100)),
                ('documento', models.CharField(max_length=20)),
                ('celular', models.CharField(max_length=20)),
                ('correo', models.EmailField(blank=True, max_length=254)),
                ('especialidad', models.CharField(max_length=100)),
                ('foto', models.ImageField(blank=True, null=True, upload_to='registros_profesores/fotos/')),
                ('usuario_solicitado', models.CharField(max_length=150)),
                ('password_hash', models.CharField(editable=False, max_length=128)),
                ('estado', models.CharField(choices=[('PENDIENTE', 'Pendiente de aprobación'), ('APROBADO', 'Aprobado'), ('RECHAZADO', 'Rechazado')], default='PENDIENTE', max_length=20)),
                ('observacion_admin', models.TextField(blank=True)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('actualizado', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Solicitud de registro de profesor',
                'verbose_name_plural': 'Solicitudes de registro de profesores',
                'ordering': ['-creado'],
            },
        ),
        migrations.AddConstraint(
            model_name='solicitudregistroprofesor',
            constraint=models.UniqueConstraint(
                Lower('documento'), condition=~Q(estado='RECHAZADO'),
                name='solicitud_profesor_documento_activo_unico',
            ),
        ),
        migrations.AddConstraint(
            model_name='solicitudregistroprofesor',
            constraint=models.UniqueConstraint(
                Lower('usuario_solicitado'), condition=~Q(estado='RECHAZADO'),
                name='solicitud_profesor_usuario_activo_unico',
            ),
        ),
    ]
