from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import IntegrityError, transaction

from alumnos.models import Alumno


User = get_user_model()


def _es_usuario_huerfano_del_registro(user, registro):
    """Reconoce un usuario creado por este mismo registro antes de un fallo."""
    return (
        user.password == registro.password_hash
        and not hasattr(user, 'perfil_alumno')
        and not hasattr(user, 'perfil_instructor')
    )


def crear_alumno_desde_registro(registro):
    username = registro.usuario_solicitado

    try:
        # El usuario y su ficha de alumno son una sola operación. Si cualquiera
        # de las dos creaciones falla, no debe quedar un usuario huérfano.
        with transaction.atomic():
            user = User.objects.filter(username__iexact=username).first()
            if user and not _es_usuario_huerfano_del_registro(user, registro):
                return None, None, 'El nombre de usuario elegido ya no está disponible.'

            if Alumno.objects.filter(documento=registro.documento).exists():
                return None, None, 'Ya existe un alumno con este documento.'

            if user is None:
                user = User(
                    username=username,
                    password=registro.password_hash,
                    first_name=registro.nombres,
                    last_name=registro.apellidos,
                    email=registro.correo or '',
                    telefono=registro.celular,
                    debe_cambiar_password=False,
                )
                user.save()

            alumno = Alumno.objects.create(
                user=user,
                foto=registro.foto,
                documento=registro.documento,
                fecha_nacimiento=registro.fecha_nacimiento,
                direccion=registro.direccion,
                nombre_acudiente=registro.nombre_acudiente,
                documento_acudiente=registro.documento_acudiente,
                parentesco_acudiente=registro.parentesco_acudiente,
                telefono_acudiente=registro.celular_acudiente,
                estado='PENDIENTE',
            )
    except IntegrityError:
        return None, None, (
            'No fue posible crear el estudiante porque el usuario o el '
            'documento ya están registrados.'
        )

    return alumno, None, None


def enviar_correo_bienvenida_alumno(registro):
    if not registro.correo:
        return

    send_mail(
        subject='Registro aprobado - Galeras BJJ',
        message=(
            f'Hola {registro.nombres},\n\n'
            'Tu registro en Galeras BJJ fue aprobado correctamente.\n\n'
            'Tus datos de acceso son:\n'
            f'Usuario: {registro.usuario_solicitado}\n'
            'Utiliza la contraseña que elegiste durante el registro.\n\n'
            'Link de acceso:\n'
            'https://bjj.lu-a.com/\n\n'
            'Bienvenido a la academia.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[registro.correo],
        fail_silently=False,
    )
