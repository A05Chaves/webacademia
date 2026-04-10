

from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
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

    def __str__(self):
        return f"{self.username} - {self.rol}"