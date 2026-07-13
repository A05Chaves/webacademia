

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class Usuario(AbstractUser):
    debe_cambiar_password = models.BooleanField(
        default=True
    )
    username_modificado = models.BooleanField(
        default=False,
        help_text='Indica si ya utilizó su único cambio de nombre de usuario.'
    )

    class Roles(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador'
        ALUMNO = 'ALUMNO', 'Alumno'
        INSTRUCTOR = 'INSTRUCTOR', 'Instructor'

    telefono = models.CharField(max_length=20, blank=True, null=True)
    rol = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.ALUMNO
    )

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower('username'),
                name='usuarios_username_unico_sin_mayusculas',
            ),
        ]

    def __str__(self):
        return f"{self.username} - {self.rol}"
