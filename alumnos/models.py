from django.conf import settings
from django.db import models


class Alumno(models.Model):
    class Disciplinas(models.TextChoices):
        TAEKWONDO = 'TAEKWONDO', 'Taekwondo'
        KARATE = 'KARATE', 'Karate'
        JUDO = 'JUDO', 'Judo'
        BOXEO = 'BOXEO', 'Boxeo'
        MMA = 'MMA', 'MMA'
        OTRA = 'OTRA', 'Otra'

    class Estados(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        PROXIMO_VENCER = 'PROXIMO_VENCER', 'Próximo a vencer'
        VENCIDO = 'VENCIDO', 'Vencido'
        SUSPENDIDO = 'SUSPENDIDO', 'Suspendido'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_alumno'
    )
    documento = models.CharField(max_length=20, unique=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    disciplina = models.CharField(
        max_length=20,
        choices=Disciplinas.choices,
        default=Disciplinas.OTRA
    )
    grado = models.CharField(max_length=50, blank=True, null=True)
    nombre_acudiente = models.CharField(max_length=150, blank=True, null=True)
    telefono_acudiente = models.CharField(max_length=20, blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=Estados.choices,
        default=Estados.ACTIVO
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Alumno'
        verbose_name_plural = 'Alumnos'
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        nombre = f"{self.user.first_name} {self.user.last_name}".strip()
        return nombre if nombre else self.user.username
