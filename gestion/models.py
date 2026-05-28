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
