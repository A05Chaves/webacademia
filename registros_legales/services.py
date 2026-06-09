from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from alumnos.models import Alumno


User = get_user_model()


def crear_alumno_desde_registro(registro):
    username = registro.documento
    password_temporal = registro.documento

    if User.objects.filter(username=username).exists():
        return None, None, 'Ya existe un usuario con este documento.'

    if Alumno.objects.filter(documento=registro.documento).exists():
        return None, None, 'Ya existe un alumno con este documento.'

    user = User.objects.create_user(
        username=username,
        password=password_temporal,
        first_name=registro.nombres,
        last_name=registro.apellidos,
        email=registro.correo or '',
        telefono=registro.celular,
        debe_cambiar_password=True,
    )

    alumno = Alumno.objects.create(
        user=user,
        documento=registro.documento,
        fecha_nacimiento=registro.fecha_nacimiento,
        direccion=registro.direccion,
        nombre_acudiente=registro.nombre_acudiente,
        telefono_acudiente=registro.celular_acudiente,
        estado='PENDIENTE',
    )

    return alumno, password_temporal, None

# FUNCION PARA ENVIAR CORREOS A LOS ESTUDIANTES CON SUS CREDENCIALES DE ACCESO


def enviar_correo_bienvenida_alumno(registro, password_temporal):
    if not registro.correo:
        return

    send_mail(
        subject='Registro aprobado - Galeras BJJ',
        message=(
            f'Hola {registro.nombres},\n\n'
            f'Tu registro en Galeras BJJ fue aprobado correctamente.\n\n'
            f'Tus datos de acceso son:\n'
            f'Usuario: {registro.documento}\n'
            f'Contraseña temporal: {password_temporal}\n\n'
            f'Ingresa al sistema y cambia tu contraseña al primer acceso.\n\n'
            f'Link de acceso:\n'
            f'http://127.0.0.1:8000/login/\n\n'
            f'Bienvenido a la academia.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[registro.correo],
        fail_silently=False,
    )
