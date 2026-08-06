from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone


class ConsentimientoFirmado(models.Model):
    class Tipos(models.TextChoices):
        ADULTO = 'ADULTO', 'Adulto'
        MENOR = 'MENOR', 'Menor de edad'

    tipo = models.CharField(max_length=20, choices=Tipos.choices)
    nombre_estudiante = models.CharField(max_length=150)
    documento_estudiante = models.CharField(
        max_length=30, blank=True, null=True)
    nombre_acudiente = models.CharField(max_length=150, blank=True, null=True)
    documento_acudiente = models.CharField(
        max_length=30, blank=True, null=True)
    texto_aceptado = models.TextField()
    firma_base64 = models.TextField()
    fecha_firma = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.nombre_estudiante} - {self.tipo}"


class ClaseCortesia(models.Model):
    class TiposPersona(models.TextChoices):
        ADULTO = 'ADULTO', 'Adulto'
        MENOR = 'MENOR', 'Menor de edad'

    clase = models.ForeignKey(
        'clases.ClaseProgramada',
        on_delete=models.CASCADE,
        related_name='cortesias',
        blank=True,
        null=True,
    )

    fecha_clase = models.DateField(
        blank=True,
        null=True,
        verbose_name='Fecha de la clase solicitada',
    )

    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    documento = models.CharField(max_length=30, blank=True, null=True)
    telefono = models.CharField(max_length=30)
    correo = models.EmailField(blank=True, null=True)
    edad = models.PositiveIntegerField()

    tipo_persona = models.CharField(
        max_length=20,
        choices=TiposPersona.choices
    )

    eps = models.CharField(max_length=150, blank=True, null=True)

    condicion_medica = models.TextField(
        blank=True,
        null=True,
        verbose_name='Discapacidad, lesión o enfermedad importante'
    )

    nombre_acudiente = models.CharField(max_length=150, blank=True, null=True)
    documento_acudiente = models.CharField(
        max_length=30, blank=True, null=True)
    telefono_acudiente = models.CharField(max_length=30, blank=True, null=True)

    parentesco_acudiente = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    consentimiento = models.OneToOneField(
        ConsentimientoFirmado,
        on_delete=models.PROTECT,
        related_name='clase_cortesia'
    )

    contactado = models.BooleanField(default=False)

    contactado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='cortesias_contactadas',
    )

    asistio = models.BooleanField(default=False)

    asistencia_confirmada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='cortesias_asistencia_confirmada',
    )

    fecha_confirmacion_asistencia = models.DateTimeField(blank=True, null=True)

    se_convirtio = models.BooleanField(default=False)

    alumno_convertido = models.ForeignKey(
        'alumnos.Alumno',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='cortesias_origen',
    )

    fecha_conversion = models.DateTimeField(blank=True, null=True)

    cantidad_correos_seguimiento = models.PositiveSmallIntegerField(default=0)

    fecha_ultimo_correo = models.DateTimeField(blank=True, null=True)

    observacion_seguimiento = models.TextField(
        blank=True,
        null=True
    )

    fecha_contacto = models.DateTimeField(
        blank=True,
        null=True
    )

    fecha_registro = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.nombres} {self.apellidos} - Cortesía"


class ConfiguracionSeguimientoCortesia(models.Model):
    asunto = models.CharField(
        max_length=180,
        default='Queremos verte nuevamente en Galeras BJJ',
    )
    mensaje = models.TextField(
        default=(
            'Gracias por acompañarnos en tu clase de cortesía. '
            'Nos gustaría invitarte a continuar entrenando con nosotros.'
        )
    )
    publicidad = models.ImageField(
        upload_to='cortesias/publicidad/',
        blank=True,
        null=True,
    )
    dias_espera = models.PositiveSmallIntegerField(
        default=3,
        validators=[MaxValueValidator(365)],
        verbose_name='Días después de la clase para el primer correo',
    )
    intervalo_dias = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        verbose_name='Intervalo mínimo entre correos',
    )
    maximo_envios = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name='Máximo de correos por persona',
    )
    activo = models.BooleanField(default=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Seguimiento de cortesías por correo'
        verbose_name_plural = 'Seguimiento de cortesías por correo'

    @classmethod
    def cargar(cls):
        configuracion, _ = cls.objects.get_or_create(pk=1)
        return configuracion

    def __str__(self):
        return 'Seguimiento de cortesías por correo'
