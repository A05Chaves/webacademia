# instructores/models.py
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class Instructor(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_instructor'
    )
    documento = models.CharField(max_length=20, unique=True)
    especialidad = models.CharField(max_length=100)
    foto = models.ImageField(
        upload_to='instructores/fotos/', blank=True, null=True
    )
    telefono = models.CharField(max_length=20, blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Instructor'
        verbose_name_plural = 'Instructores'

    def __str__(self):
        nombre = f"{self.user.first_name} {self.user.last_name}".strip()
        return nombre if nombre else self.user.username


class SolicitudRegistroProfesor(models.Model):
    class Estados(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de aprobación'
        APROBADO = 'APROBADO', 'Aprobado'
        RECHAZADO = 'RECHAZADO', 'Rechazado'

    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    documento = models.CharField(max_length=20)
    celular = models.CharField(max_length=20)
    correo = models.EmailField(blank=True)
    especialidad = models.CharField(max_length=100)
    foto = models.ImageField(
        upload_to='registros_profesores/fotos/', blank=True, null=True
    )
    usuario_solicitado = models.CharField(max_length=150)
    password_hash = models.CharField(max_length=128, editable=False)
    estado = models.CharField(
        max_length=20, choices=Estados.choices, default=Estados.PENDIENTE
    )
    observacion_admin = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado']
        verbose_name = 'Solicitud de registro de profesor'
        verbose_name_plural = 'Solicitudes de registro de profesores'
        constraints = [
            models.UniqueConstraint(
                Lower('documento'),
                condition=~Q(estado='RECHAZADO'),
                name='solicitud_profesor_documento_activo_unico',
            ),
            models.UniqueConstraint(
                Lower('usuario_solicitado'),
                condition=~Q(estado='RECHAZADO'),
                name='solicitud_profesor_usuario_activo_unico',
            ),
        ]

    def __str__(self):
        return f'{self.nombres} {self.apellidos} - {self.get_estado_display()}'
