from django.conf import settings
from django.db import models


class Notificacion(models.Model):
    class Tipos(models.TextChoices):
        RECORDATORIO_PAGO = 'RECORDATORIO_PAGO', 'Recordatorio de pago'
        VENCIMIENTO = 'VENCIMIENTO', 'Vencimiento'
        MORA = 'MORA', 'Mora'
        PAGO_APROBADO = 'PAGO_APROBADO', 'Pago aprobado'
        PAGO_RECHAZADO = 'PAGO_RECHAZADO', 'Pago rechazado'

    class Estados(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        ENVIADA = 'ENVIADA', 'Enviada'
        FALLIDA = 'FALLIDA', 'Fallida'
        CANCELADA = 'CANCELADA', 'Cancelada'

    class Canales(models.TextChoices):
        INTERNA = 'INTERNA', 'Interna'
        EMAIL = 'EMAIL', 'Correo electrónico'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificaciones'
    )
    tipo = models.CharField(
        max_length=30,
        choices=Tipos.choices
    )
    titulo = models.CharField(max_length=150)
    mensaje = models.TextField()
    fecha_programada = models.DateTimeField()
    fecha_envio = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=Estados.choices,
        default=Estados.PENDIENTE
    )
    canal = models.CharField(
        max_length=20,
        choices=Canales.choices,
        default=Canales.INTERNA
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-fecha_programada']

    def __str__(self):
        return f"{self.titulo} - {self.usuario}"
