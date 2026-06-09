from django.db import models

# Create your models here.


class ConfiguracionHome(models.Model):
    video_promo_url = models.URLField(
        verbose_name='URL video promo YouTube',
        blank=True,
        null=True
    )

    playlist_youtube_url = models.URLField(
        verbose_name='URL playlist YouTube',
        blank=True,
        null=True
    )

    activo = models.BooleanField(default=True)

    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración Home'
        verbose_name_plural = 'Configuración Home'

    def __str__(self):
        return 'Configuración Home'

# CLASE PARA GESTION DE CONFIGURACION DE ADMINISTRACION


class ConfiguracionNotificacion(models.Model):
    dias_antes_vencimiento = models.PositiveIntegerField(
        default=5
    )

    enviar_correo = models.BooleanField(
        default=True
    )

    mensaje_vencimiento = models.TextField(
        default='Tu suscripción está próxima a vencer. Por favor realiza tu renovación para continuar entrenando.'
    )

    activo = models.BooleanField(
        default=True
    )

    actualizado = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = 'Configuración de notificación'
        verbose_name_plural = 'Configuración de notificaciones'

    def __str__(self):
        return f'Notificar {self.dias_antes_vencimiento} días antes'

# MODELO PARA CONFIGURAR HORARIOS


class DiaHorario(models.Model):
    nombre = models.CharField(max_length=20, unique=True)
    orden = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return self.nombre


class HoraHorario(models.Model):
    hora = models.TimeField(unique=True)
    orden = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['orden', 'hora']

    def __str__(self):
        return self.hora.strftime('%H:%M')
