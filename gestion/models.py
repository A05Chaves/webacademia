from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
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

    orden_video_promocional = models.PositiveIntegerField(
        default=10,
        verbose_name='Prioridad del video promocional',
        help_text=(
            'Los números menores aparecen primero. Por ejemplo, un seminario '
            'con prioridad 5 se mostrará antes de un video con prioridad 10.'
        ),
    )
    publicidad_tienda_activa = models.BooleanField(
        default=False, verbose_name='Mostrar publicidad de la tienda'
    )
    publicidad_tienda_titulo = models.CharField(
        max_length=120, default='Tienda Bross Fight Sports'
    )
    publicidad_tienda_texto = models.CharField(
        max_length=240, blank=True,
        default='Conoce nuestras prendas, equipos y productos deportivos.'
    )
    publicidad_tienda_imagen = models.ImageField(
        upload_to='tienda/publicidad/', blank=True, null=True,
        verbose_name='Imagen publicitaria de la tienda',
    )
    orden_publicidad_tienda = models.PositiveIntegerField(
        default=8, verbose_name='Prioridad de la publicidad de tienda',
        help_text='Los números menores aparecen primero en el carrusel.',
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


class ConfiguracionClases(models.Model):
    minutos_antes_confirmacion = models.PositiveSmallIntegerField(
        default=60,
        validators=[MaxValueValidator(180)],
        verbose_name='Minutos antes de la clase',
    )
    minutos_despues_confirmacion = models.PositiveSmallIntegerField(
        default=20,
        validators=[MaxValueValidator(180)],
        verbose_name='Minutos después de iniciar',
    )
    gamificacion_activa = models.BooleanField(
        default=True,
        verbose_name='Entregar monedas por asistencia',
    )
    monedas_por_asistencia = models.PositiveSmallIntegerField(
        default=10,
        validators=[MaxValueValidator(1000)],
        verbose_name='Monedas por asistencia',
    )
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de clases'
        verbose_name_plural = 'Configuración de clases'

    @classmethod
    def cargar(cls):
        configuracion, _ = cls.objects.get_or_create(pk=1)
        return configuracion

    def __str__(self):
        return (
            f'Confirmación: {self.minutos_antes_confirmacion} min antes / '
            f'{self.minutos_despues_confirmacion} min después'
        )


class BilleteraMonedas(models.Model):
    class Avatares(models.TextChoices):
        HUEVO = 'HUEVO', 'Huevo inicial'

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='billetera_monedas',
    )
    saldo = models.PositiveIntegerField(default=0)
    avatar = models.CharField(
        max_length=20,
        choices=Avatares.choices,
        default=Avatares.HUEVO,
    )
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Billetera de monedas'
        verbose_name_plural = 'Billeteras de monedas'

    def __str__(self):
        return f'{self.usuario} · {self.saldo} monedas'


class MovimientoMonedas(models.Model):
    class Tipos(models.TextChoices):
        ASISTENCIA = 'ASISTENCIA', 'Premio por asistencia'
        AJUSTE = 'AJUSTE', 'Ajuste administrativo'
        DESCUENTO = 'DESCUENTO', 'Descuento de monedas'

    billetera = models.ForeignKey(
        BilleteraMonedas,
        on_delete=models.PROTECT,
        related_name='movimientos',
    )
    asistencia = models.OneToOneField(
        'clases.AsistenciaClase',
        on_delete=models.PROTECT,
        related_name='premio_monedas',
        null=True,
        blank=True,
    )
    tipo = models.CharField(max_length=20, choices=Tipos.choices)
    cantidad = models.IntegerField()
    saldo_resultante = models.PositiveIntegerField()
    descripcion = models.CharField(max_length=220)
    creado = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='movimientos_monedas_registrados',
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['-creado', '-id']
        verbose_name = 'Movimiento de monedas'
        verbose_name_plural = 'Movimientos de monedas'
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(cantidad=0),
                name='movimiento_monedas_cantidad_no_cero',
            ),
        ]

    def __str__(self):
        signo = '+' if self.cantidad > 0 else ''
        return f'{self.billetera.usuario}: {signo}{self.cantidad}'


def estado_tv_inicial():
    return {
        'mode': 'overview',
        'duration': 300,
        'remaining': 300,
        'running': False,
        'started_at': None,
        'preparing': False,
        'preparation_started_at': None,
        'preparation_seconds': 5,
        'warning_done': False,
        'sound_event': None,
        'red_name': 'COMPETIDOR ROJO',
        'blue_name': 'COMPETIDOR AZUL',
        'red_points': 0,
        'blue_points': 0,
        'red_advantages': 0,
        'blue_advantages': 0,
        'red_penalties': 0,
        'blue_penalties': 0,
        'bracket': None,
        'bracket_source_category_id': None,
        'bracket_source_event_id': None,
        'next_fight': None,
        'active_match': None,
        'youtube_video_id': None,
        'youtube_visible': False,
        'youtube_size': 'small',
        'youtube_volume': 35,
        'youtube_command': None,
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
