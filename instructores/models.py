# instructores/models.py
from django.conf import settings
from django.db import models


class Instructor(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_instructor'
    )
    documento = models.CharField(max_length=20, unique=True)
    especialidad = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Instructor'
        verbose_name_plural = 'Instructores'

    def __str__(self):
        nombre = f"{self.user.first_name} {self.user.last_name}".strip()
        return nombre if nombre else self.user.username
