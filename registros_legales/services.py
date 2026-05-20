from django.contrib.auth import get_user_model

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
        estado='SUSPENDIDO',
    )

    return alumno, password_temporal, None
