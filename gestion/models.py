from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
import uuid

# Create your models here.


class ConfiguracionHome(models.Model):
    video_promo_url = models.URLField(
        verbose_name='URL video promo YouTube',
        blank=True,
        null=True
    )

    video_promo_archivo = models.FileField(
        upload_to='videos_home/',
        blank=True,
        null=True,
        verbose_name='Video promo MP4'
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

    def clean(self):

        if self.playlist_youtube_url:

            if "list=RD" in self.playlist_youtube_url:
                raise ValidationError({
                    'playlist_youtube_url':
                    'No se permiten enlaces tipo Radio/Mix. Utilice una playlist real de YouTube.'
                })

            if "playlist?list=" not in self.playlist_youtube_url:
                raise ValidationError({
                    'playlist_youtube_url':
                    'Debe ingresar una playlist de YouTube válida.'
                })

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


def estado_tv_inicial():
    return {
        'mode': 'overview',
        'duration': 300,
        'remaining': 300,
        'running': False,
        'started_at': None,
        'red_name': 'COMPETIDOR ROJO',
        'blue_name': 'COMPETIDOR AZUL',
        'red_points': 0,
        'blue_points': 0,
        'red_advantages': 0,
        'blue_advantages': 0,
        'red_penalties': 0,
        'blue_penalties': 0,
    }


class SesionTV(models.Model):
    propietario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sesiones_tv',
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    codigo = models.CharField(max_length=6, unique=True)
    estado = models.JSONField(default=estado_tv_inicial)
    activa = models.BooleanField(default=True)
    expira_en = models.DateTimeField()
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creada']

    @property
    def vigente(self):
        return self.activa and self.expira_en > timezone.now()

    def __str__(self):
        return f'Modo TV {self.codigo}'
